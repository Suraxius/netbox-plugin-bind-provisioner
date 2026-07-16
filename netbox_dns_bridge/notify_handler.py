import dns.message
import dns.name
import dns.opcode
import dns.query
import dns.rdatatype
import dns.rdataclass
import dns.rrset
import dns.tsig
from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections, OperationalError
from netbox.jobs import JobRunner
from netbox_dns.models import View, Zone, Record
from .logger import get_logger
from .models import SeenTransferClients, IntegerKeyValueSetting

LOGGER = get_logger(__name__)
SETTINGS = settings.PLUGINS_CONFIG["netbox_dns_bridge"]


def _load_tsig_key(view_name: str) -> dns.tsig.Key:
    tsig_keys = SETTINGS.get("tsig_keys", {})
    if view_name not in tsig_keys:
        raise RuntimeError(f"No TSIG key configured for view '{view_name}'")

    key_data = tsig_keys[view_name]
    raw_key_name = key_data.get("keyname")
    secret = key_data.get("secret")
    algorithm = key_data.get("algorithm")
    if not algorithm:
        raise RuntimeError(
            f"Missing 'algorithm' in TSIG key configuration for view '{view_name}'"
        )

    if not raw_key_name or not secret:
        raise RuntimeError(f"Incomplete TSIG key configuration for view '{view_name}'")

    key_name = dns.name.from_text(raw_key_name, origin=None).canonicalize()
    if not key_name.is_absolute():
        key_name = key_name.concatenate(dns.name.root)

    return dns.tsig.Key(name=key_name, secret=secret, algorithm=algorithm)


class SendDNSNotify(JobRunner):
    class Meta:
        name = "Send DNS NOTIFY"

    def run(self, *args, **kwargs):
        notify_over_tcp = SETTINGS.get("notify_over_tcp", False)
        view_name = kwargs["view_name"]

        try:
            catz_serial = IntegerKeyValueSetting.objects.get(
                key="catalog-zone-soa-serial"
            ).value

            zones = [
                (kwargs["zone_name"], kwargs["soa_serial"]),
                ("catz", catz_serial),
                (f"{view_name}.catz", catz_serial),
            ]

            view = View.objects.get(name=view_name)
            tsig_key = _load_tsig_key(view_name)
            cutoff_hours = SETTINGS.get("notify_client_alive_threshold_hours", 24)
            seen_cutoff = timezone.now() - timezone.timedelta(hours=cutoff_hours)

            clients = SeenTransferClients.objects.filter(
                view=view, last_seen__gte=seen_cutoff
            )

            for zone_name, soa_serial in zones:
                zone_name = dns.name.from_text(zone_name, dns.name.root).to_text()
                msg = dns.message.make_query(zone_name, dns.rdatatype.SOA)
                msg.flags |= dns.flags.AA  # = 0
                msg.set_opcode(dns.opcode.NOTIFY)

                soa_rdata = dns.rdata.from_text(
                    dns.rdataclass.IN,
                    dns.rdatatype.SOA,
                    f"invalid. invalid. {soa_serial} 60 10 1209600 0",
                )
                soa_rrset = dns.rrset.from_rdata(zone_name, 0, soa_rdata)
                msg.authority.append(soa_rrset)
                msg.use_tsig(keyring={tsig_key.name: tsig_key}, keyname=tsig_key.name)

                for client in clients:
                    try:
                        if notify_over_tcp:
                            LOGGER.debug("Sending NOTIFY over TCP")
                            dns.query.tcp(msg, client.source_ip, port=5355, timeout=2)
                        else:
                            LOGGER.debug("Sending NOTIFY over UDP")
                            dns.query.udp(msg, client.source_ip, port=5355, timeout=2)

                        LOGGER.info(
                            f"NOTIFY sent: {client.source_ip} {view_name}/{zone_name} {soa_serial}"
                        )
                    except Exception as e:
                        LOGGER.error(
                            f"NOTIFY failed: {client.source_ip}"
                            f" {view_name}/{zone_name} {soa_serial}: {e}"
                        )

        except IntegerKeyValueSetting.DoesNotExist as e:
            LOGGER.error(f"Failed to get catalog zone serial: {e}")

        except OperationalError as e:
            LOGGER.error(f"NOTIFY failed due to unexpected error: {e}")
            close_old_connections()


class SendZoneNSNotify(JobRunner):
    """Send a NOTIFY straight to a zone's own nameservers.

    Unlike ``SendDNSNotify`` (which notifies clients that previously queried the
    transfer endpoint), this job resolves the addresses of the zone's configured
    nameservers from NetBox DNS itself and notifies each of them so they pick up
    the changed zone quickly.
    """

    class Meta:
        name = "Send DNS NOTIFY to zone nameservers"

    def run(self, *args, **kwargs):
        notify_over_tcp = SETTINGS.get("notify_over_tcp", False)
        port = SETTINGS.get("notify_ns_port", 53)
        view_name = kwargs["view_name"]
        zone_name = kwargs["zone_name"]
        soa_serial = kwargs["soa_serial"]

        try:
            zone = Zone.objects.get(pk=kwargs["zone_id"])
        except Zone.DoesNotExist:
            LOGGER.error(f"NS NOTIFY: zone id {kwargs['zone_id']} no longer exists")
            return
        except OperationalError as e:
            LOGGER.error(f"NS NOTIFY failed due to unexpected error: {e}")
            close_old_connections()
            return

        ns_targets = _resolve_zone_nameserver_ips(zone)
        if not ns_targets:
            LOGGER.warning(
                f"NS NOTIFY: no nameserver addresses found in NetBox DNS for "
                f"{view_name}/{zone_name} — skipping"
            )
            return

        try:
            tsig_key = _load_tsig_key(view_name)
        except RuntimeError as e:
            LOGGER.error(
                f"NS NOTIFY aborted for {view_name}/{zone_name}: {e}"
            )
            return

        fqdn = dns.name.from_text(zone_name, dns.name.root).to_text()
        msg = dns.message.make_query(fqdn, dns.rdatatype.SOA)
        msg.flags |= dns.flags.AA
        msg.set_opcode(dns.opcode.NOTIFY)

        soa_rdata = dns.rdata.from_text(
            dns.rdataclass.IN,
            dns.rdatatype.SOA,
            f"invalid. invalid. {soa_serial} 60 10 1209600 0",
        )
        msg.authority.append(dns.rrset.from_rdata(fqdn, 0, soa_rdata))
        msg.use_tsig(keyring={tsig_key.name: tsig_key}, keyname=tsig_key.name)

        for ip in ns_targets:
            try:
                if notify_over_tcp:
                    LOGGER.debug("Sending NS NOTIFY over TCP")
                    dns.query.tcp(msg, ip, port=port, timeout=2)
                else:
                    LOGGER.debug("Sending NS NOTIFY over UDP")
                    dns.query.udp(msg, ip, port=port, timeout=2)

                LOGGER.info(
                    f"NS NOTIFY sent: {ip} {view_name}/{fqdn} {soa_serial}"
                )
            except Exception as e:
                LOGGER.error(
                    f"NS NOTIFY failed: {ip} {view_name}/{fqdn} {soa_serial}: {e}"
                )


def _get_soa_serial(zone: Zone):
    """Return the current SOA serial of a zone parsed from its SOA record."""
    try:
        soa_record = Record.objects.filter(zone=zone, type="SOA", active=True).first()
        if soa_record is None:
            LOGGER.error(f"Zone {zone.name} has no active SOA record — skipping NOTIFY")
            return None

        return int(soa_record.value.split()[2])

    except OperationalError as e:
        LOGGER.error(f"DB ERROR while fetching SOA for zone {zone.name}: {e}")
        close_old_connections()
        return None
    except (ValueError, IndexError) as e:
        LOGGER.error(f"Failed to parse SOA serial for zone {zone.name}: {e}")
        return None


def _resolve_zone_nameserver_ips(zone: Zone) -> list:
    """Resolve the zone's nameserver hostnames to IPs using NetBox DNS records.

    For each nameserver assigned to the zone, matching active A/AAAA records
    within the same view are looked up in NetBox DNS. Returns a de-duplicated,
    order-preserving list of IP addresses.
    """
    ips = []
    try:
        nameservers = list(zone.nameservers.all())
        view = zone.view

        for nameserver in nameservers:
            fqdn = dns.name.from_text(nameserver.name, dns.name.root).to_text()
            # Match both with and without a trailing dot to be resilient against
            # how the fqdn is stored on the Record model.
            candidates = {fqdn, fqdn.rstrip(".")}

            records = Record.objects.filter(
                fqdn__in=list(candidates),
                type__in=["A", "AAAA"],
                active=True,
                zone__view=view,
            )
            for record in records:
                if record.value not in ips:
                    ips.append(record.value)

    except OperationalError as e:
        LOGGER.error(f"DB ERROR while resolving nameservers for {zone.name}: {e}")
        close_old_connections()

    return ips


def schedule(zone: Zone):
    soa_serial = _get_soa_serial(zone)
    if soa_serial is None:
        return

    SendDNSNotify.enqueue(
        zone_name=zone.name,
        view_name=zone.view.name,
        soa_serial=soa_serial,
    )


def schedule_notify_ns(zone: Zone):
    soa_serial = _get_soa_serial(zone)
    if soa_serial is None:
        return

    SendZoneNSNotify.enqueue(
        zone_id=zone.pk,
        zone_name=zone.name,
        view_name=zone.view.name,
        soa_serial=soa_serial,
    )
