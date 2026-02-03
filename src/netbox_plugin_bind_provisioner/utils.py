import os
import dns.zone
import dns.rdatatype
import dns.rdataclass
import dns.exception
import netbox_dns.models

def export_bind_zone_file(nb_zone: netbox_dns.models.Zone, file_path: str):

    # Create dnspython zone object
    dp_zone = dns.zone.Zone(origin=dns.name.from_text(nb_zone.name))

    for record in nb_zone.records.all():
        rname = record.name or "@"
        rdclass = dns.rdataclass.IN
        rdatatype = dns.rdatatype.from_text(record.type)

        # Create rdata object
        rdata = dns.rdata.from_text(rdclass, rdatatype, record.value)

        # Create rdataset
        rdataset = dns.rdataset.Rdataset(rdclass, rdatatype, record.ttl)
        rdataset.add(rdata)

        # Add to zone
        node = dp_zone.find_node(rname, create=True)
        node.rdatasets.append(rdataset)

    # Write zone to file in BIND format
    try:
        with open(file_path, "w") as f:
            dp_zone.to_file(f, sorted=True)
    except IOError as e:
        raise IOError(f"Failed to write zone file to {file_path}: {e}")

