import dns.name
import dns.zone
import dns.rdatatype
import dns.rdataclass
from .logger import get_logger
from netbox_dns.models import Zone
from netbox_dns.choices import ZoneStatusChoices
from netbox_dns_bridge.models import IntegerKeyValueSetting, CatalogZoneMemberIdentifier
from uuid import uuid4
from base64 import b32encode
from django.db import transaction

logger = get_logger(__name__)

_SERIAL_MAX = 0xFFFFFFFF


def init() -> None:
    _init_serial()
    _init_last_zone_update_timestamp()
    _create_missing_member_identifiers()


def _init_serial() -> None:
    try:
        IntegerKeyValueSetting.objects.get(key="catalog-zone-soa-serial")
        logger.info("Catalog zone SOA serial number loaded from database")
    except IntegerKeyValueSetting.DoesNotExist:
        IntegerKeyValueSetting.objects.create(
            key="catalog-zone-soa-serial", value=1
        )
        logger.debug("Catalog zone SOA serial number was not set in the database. Set to 1")


def _init_last_zone_update_timestamp() -> None:
    try:
        IntegerKeyValueSetting.objects.get(key="last-zone-update-timestamp")
        logger.info("Last zone update timestamp loaded from database")
    except IntegerKeyValueSetting.DoesNotExist:
        IntegerKeyValueSetting.objects.create(
            key="last-zone-update-timestamp", value=0
        )
        logger.debug("Last zone update timestamp was not set in the database. Set to 0")


def _create_missing_member_identifiers() -> None:
    existing_zone_ids = CatalogZoneMemberIdentifier.objects.values_list(
        "zone_id", flat=True
    )

    missing_zones = Zone.objects.exclude(id__in=existing_zone_ids)

    new_objects = [
        CatalogZoneMemberIdentifier(
            zone=zone,
            name=_generate_member_identifier(),
        )
        for zone in missing_zones
    ]

    for identifier in new_objects:
        logger.debug(
            f"Zone {identifier.zone} missing catz member identifier. Creating..."
        )

    CatalogZoneMemberIdentifier.objects.bulk_create(
        new_objects,
        ignore_conflicts=False,
    )


def create_zone(name, view_name) -> dns.zone.Zone:
    # Atomic transaction with row-level locking to prevent diverging state
    current_serial: int

    with transaction.atomic():
        serial_setting = IntegerKeyValueSetting.objects.select_for_update().get(
            key="catalog-zone-soa-serial"
        )
        timestamp_setting = IntegerKeyValueSetting.objects.select_for_update().get(
            key="last-zone-update-timestamp"
        )

        latest_zone = (
            Zone.objects.filter(status=ZoneStatusChoices.STATUS_ACTIVE)
            .order_by("-last_updated")
            .first()
        )

        last_zone_update = getattr(latest_zone, "last_updated", None)
        last_zone_update_ts = (
            int(last_zone_update.timestamp()) if last_zone_update else 0
        )

        # Check if any zone was updated since last call
        if timestamp_setting.value != last_zone_update_ts:
            if last_zone_update is not None:
                logger.debug(
                    f"Zone {latest_zone.name} was updated in view {latest_zone.view.name}"
                )
            # Update timestamp for next iteration
            timestamp_setting.value = last_zone_update_ts
            timestamp_setting.save()

            # Increment serial
            new_serial = serial_setting.value + 1
            if new_serial > _SERIAL_MAX:
                logger.warning(
                    f"Catalog serial {serial_setting.value} reached max — wrapping back to 1"
                )
                new_serial = 1
            serial_setting.value = new_serial
            serial_setting.save()
            logger.debug(f"Catalog zone SOA serial number is now {serial_setting.value}")

        current_serial = serial_setting.value

    # Zone origin
    origin = dns.name.from_text(name, dns.name.root)

    # Create a new empty zone
    zone = dns.zone.Zone(origin)
    zone.rdclass = dns.rdataclass.IN

    # get zones from netbox
    nb_zones = Zone.objects.filter(
        view__name=view_name, status=ZoneStatusChoices.STATUS_ACTIVE
    ).select_related("catz_identifier")

    ptr_base = dns.name.from_text("zones", origin)

    for nb_zone in nb_zones:
        ttl = 0
        qname = dns.name.from_text(nb_zone.name, dns.name.root)

        # Create PTR record
        p_name = nb_zone.catz_identifier.name

        ptr_name = dns.name.from_text(p_name, ptr_base)
        if not ptr_name.is_subdomain(origin):
            raise ValueError(
                f"Catalog zone member identifier {ptr_name.to_text()} not a subdomain"
            )
        rdata = dns.rdata.from_text(
            dns.rdataclass.IN, dns.rdatatype.PTR, qname.to_text()
        )
        rdataset = zone.find_rdataset(ptr_name, dns.rdatatype.PTR, create=True)
        rdataset.add(rdata, ttl)

        # Configure DNSSec Policy for member Zone if DNSSec is enabled
        if nb_zone.dnssec_policy:
            rid = dns.name.from_text("group", ptr_name)
            policy_name = nb_zone.dnssec_policy.name.rstrip(" ")
            group_name = f"dnssec-policy-{policy_name}"
            rdata = dns.rdata.from_text(
                dns.rdataclass.IN, dns.rdatatype.TXT, group_name
            )
            rdataset = zone.find_rdataset(rid, dns.rdatatype.TXT, create=True)
            rdataset.add(rdata, ttl)

    # SOA Record components
    ttl = 0
    rclass = dns.rdataclass.IN
    rtype = dns.rdatatype.SOA
    mname = dns.name.from_text("invalid", dns.name.root)
    rname = dns.name.from_text("invalid", dns.name.root)
    refresh = 60
    retry = 10
    expire = 1209600
    minimum = 0

    # Create SOA rdata object
    soa_rdata = dns.rdata.from_text(
        rclass,
        rtype,
        f"{mname} {rname} {current_serial} {refresh} {retry} {expire} {minimum}",
    )

    # Create Rdataset and add the RDATA to it
    soa_rdataset = dns.rdataset.Rdataset(rclass, rtype)
    soa_rdataset.add(soa_rdata, ttl)

    # Add to the origin node in the zone
    node = zone.find_node(origin, create=True)
    node.rdatasets.append(soa_rdataset)

    # NS record for catz.
    ns_name = dns.name.from_text("invalid", dns.name.root)
    ns_rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.NS, str(ns_name))
    ns_rdataset = dns.rdataset.Rdataset(dns.rdataclass.IN, dns.rdatatype.NS)
    ns_rdataset.add(ns_rdata, 0)

    # Add to node (catz. is the origin)
    ns_node = zone.find_node(origin, create=True)
    ns_node.rdatasets.append(ns_rdataset)

    # TXT record for version.catz.
    version_name = dns.name.from_text("version", origin)
    txt_rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.TXT, '"2"')

    txt_rdataset = dns.rdataset.Rdataset(dns.rdataclass.IN, dns.rdatatype.TXT)
    txt_rdataset.add(txt_rdata, 0)

    # Add to node version.catz.
    txt_node = zone.find_node(version_name, create=True)
    txt_node.rdatasets.append(txt_rdataset)

    return zone


def _generate_member_identifier() -> None:
    return b32encode(uuid4().bytes)[0:26].lower().decode("UTF-8")


def update_member_identifier(zone: Zone) -> None:
    CatalogZoneMemberIdentifier.objects.update_or_create(
        zone=zone,
        defaults={"name": _generate_member_identifier()},
    )
