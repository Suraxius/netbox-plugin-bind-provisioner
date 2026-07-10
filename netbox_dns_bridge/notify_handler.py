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


class SendDNSNotify(JobRunner):
    class Meta:
        name = "Send DNS NOTIFY"

    def _load_tsig_key(self, view_name: str) -> dns.tsig.Key:
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
            raise RuntimeError(
                f"Incomplete TSIG key configuration for view '{view_name}'"
            )

        key_name = dns.name.from_text(raw_key_name, origin=None).canonicalize()
        if not key_name.is_absolute():
            key_name = key_name.concatenate(dns.name.root)

        return dns.tsig.Key(name=key_name, secret=secret, algorithm=algorithm)

    def run(self, *args, **kwargs):
        notify_over_tcp = SETTINGS.get("notify_over_tcp", False)
        view_name = kwargs["view_name"]

        try:
            catz_serial = IntegerKeyValueSetting.objects.get(key="catalog-zone-soa-serial").value

            zones = [
                (kwargs["zone_name"], kwargs["soa_serial"]),
                ("catz",              catz_serial),
                (f"{view_name}.catz", catz_serial)
            ]

            view = View.objects.get(name=view_name)
            tsig_key = self._load_tsig_key(view_name)
            cutoff_hours = SETTINGS.get("notify_client_alive_threshold_hours", 24)
            seen_cutoff = timezone.now() - timezone.timedelta(hours=cutoff_hours)

            clients = SeenTransferClients.objects.filter(
                view=view, last_seen__gte=seen_cutoff
            )

            for zone_name, soa_serial in zones:
                msg = dns.message.make_query(zone_name, dns.rdatatype.SOA)
                msg.flags = 0
                msg.set_opcode(dns.opcode.NOTIFY)

                soa_rdata = dns.rdata.from_text(
                    dns.rdataclass.IN,
                    dns.rdatatype.SOA,
                    f"invalid invalid {soa_serial} 60 10 1209600 0",
                )
                soa_rrset = dns.rrset.from_rdata(
                    dns.name.from_text(zone_name, dns.name.root), 0, soa_rdata
                )
                msg.authority.append(soa_rrset)
                msg.use_tsig(keyring={tsig_key.name: tsig_key}, keyname=tsig_key.name)

                for client in clients:
                    try:
                        if notify_over_tcp:
                            LOGGER.info("Sending over TCP")
                            dns.query.tcp(msg, client.source_ip, timeout=2)
                        else:
                            LOGGER.info("Sending over UDP")
                            dns.query.udp(msg, client.source_ip, timeout=2)

                        LOGGER.info(
                            f"NOTIFY sent to {client.source_ip} for zone {zone_name}"
                        )
                    except Exception as e:
                        LOGGER.error(
                            f"NOTIFY failed for {client.source_ip} zone {zone_name}: {e}"
                        )

        except IntegerKeyValueSetting.DoesNotExist as e:
            LOGGER.error(f"Failed to get catalog zone serial: {e}")

        except OperationalError as e:
            LOGGER.error(f"NOTIFY failed due to unexpected error: {e}")
            close_old_connections()


def schedule(zone: Zone):
    try:
        soa_record = Record.objects.filter(
            zone=zone, type="SOA", active=True
        ).first()
        if soa_record is None:
            LOGGER.error(
                f"Zone {zone.name} has no active SOA record — skipping NOTIFY"
            )
            return

        soa_serial = int(soa_record.value.split()[2])

    except OperationalError as e:
        LOGGER.error(f"DB ERROR while fetching SOA for zone {zone.name}: {e}")
        close_old_connections()
        return
    except (ValueError, IndexError) as e:
        LOGGER.error(
            f"Failed to parse SOA serial for zone {zone.name}: {e}"
        )
        return

    SendDNSNotify.enqueue(
        zone_name=zone.name,
        view_name=zone.view.name,
        soa_serial=soa_serial,
    )
