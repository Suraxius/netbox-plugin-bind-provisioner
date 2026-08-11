import dns.name
import dns.zone
import dns.rdatatype
import dns.rdataclass
import dns.rdataset
import netbox_dns.models
from .logger import get_logger

LOGGER = get_logger(__name__)


def build_dns_zone(nb_zone: netbox_dns.models.Zone) -> dns.zone.Zone:
    # Build DNS zone
    zone = dns.zone.Zone(nb_zone.name, dns.name.root)
    zone.rdclass = dns.rdataclass.IN

    nb_records = nb_zone.records.filter(active=True)

    rdatasets_dict = {}

    for record in nb_records:
        rdtype = dns.rdatatype.from_text(record.type)
        if not record.name:
            name = zone.origin
        elif record.name.endswith("."):
            name = dns.name.from_text(record.name)
        else:
            name = dns.name.from_text(record.name, origin=zone.origin)

        # If the record has no TTL, use the zone default
        ttl = record.ttl or nb_zone.default_ttl

        # Apply quoting for TXT records to stop tokanizer
        # from cutting it up:
        value = record.value
        if rdtype == dns.rdatatype.TXT:
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('" "', "").replace('"', '"')

            if len(value) > 255:
                # This is a bug fix for netbox. If netbox allowed for
                # an unquoted value to be larger then 255 characters,
                # it misunderstood everything behind a ; as a comment.
                chunks = [
                    '"{}"'.format(value[i : i + 255])
                    for i in range(0, len(value), 255)
                ]
                value = " ".join(chunks)
            else:
                value = f'"{value}"'

        rdata = dns.rdata.from_text(
            dns.rdataclass.IN,
            rdtype,
            value,
            relativize=False,
            origin=zone.origin,
        )

        # Initialize rdataset if it doesn't exist for this name and type
        if name not in rdatasets_dict:
            rdatasets_dict[name] = {}
        if rdtype not in rdatasets_dict[name]:
            rdatasets_dict[name][rdtype] = dns.rdataset.Rdataset(
                dns.rdataclass.IN, rdtype
            )

        # Add the rdata to the appropriate rdataset
        rdatasets_dict[name][rdtype].add(rdata, ttl)

    # Now, add all rdatasets to the zone
    for name, rdtypes in rdatasets_dict.items():
        for rdtype, rdataset in rdtypes.items():
            # Ensure rdataset has the same rdclass as the zone
            if rdataset.rdclass != zone.rdclass:
                raise ValueError(
                    f"rdataset rdclass {rdataset.rdclass} does not match "
                    f"zone rdclass {zone.rdclass}"
                )

            # Check if the rdataset has any rdata before creating an RRset
            if not rdataset:
                LOGGER.debug(f"Skipping empty rdataset for {name} {rdtype}")
                continue  # Skip empty rdataset

            # Replace the rdataset for the given name and type
            zone.replace_rdataset(name, rdataset)
    return zone


def export_bind_zone_file(nb_zone: netbox_dns.models.Zone, file_path: str):
    zone = build_dns_zone(nb_zone)

    # Write zone to file in BIND format
    try:
        with open(file_path, "w") as f:
            zone.to_file(f, sorted=True)
    except IOError as e:
        raise IOError(f"Failed to write zone file to {file_path}: {e}")
