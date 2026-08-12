## Unreleased
- Replace the global `IntegerKeyValueSetting` model (single `catalog-zone-soa-serial`
  value shared by all catalog zones) with a new `CatalogZone` model that has a 1:1
  foreign key to `netbox_dns.models.View` and its own `soa_serial` field. Each view's
  catalog zone now tracks and increments its SOA serial independently. Existing serials
  are preserved during migration by copying the old global value into every view's new
  `CatalogZone` row.
- Change the `CatalogZoneMemberIdentifier.name` uniqueness from globally unique to
  unique per catalog zone (`UniqueConstraint(name, catalog_zone)`). A `catalog_zone`
  foreign key has been added to the identifier model to enforce this.
- Remove the `dns-settings` management command, which was a generic get/set/list
  interface over `IntegerKeyValueSetting` (now removed).
- Defer the catalog zone SOA serial increment on zone deletion to `transaction.on_commit`, matching
  the create/modify path. Previously the increment ran immediately at `post_delete` time, so a
  rollback of the delete transaction would have left the catalog serial bumped anyway.
- Add the option to send a NOTIFY directly to a zone's own nameservers when its SOA serial number
  changes. Enable it per zone via a boolean custom field named by `notify_ns_custom_field_name`,
  globally for all zones via `notify_ns_all_zones` (default `False`), or both. Nameserver addresses
  are resolved from NetBox DNS A/AAAA records within the zone's view and the NOTIFY is signed with
  the per-view TSIG key. A companion `notify_ns_port` setting (default 53) controls the destination
  port.

## 1.0.7 - 2026-03-02
README Change - Moving private keys to global scope since Bind 9.20 view scoped keys have become unreliable and sometimes wouldnt match.

## 1.0.8 - 2026-03-12
- Change License to MIT to match the netbox-plugin-dns License. This project rests on the netbox-plugin-dns so a matching
  license makes more sense.
- Renaming Project from Netbox Plugin Bind Provisioner to Netbox DNS Bridge as new code will be contributed that allows
  data to flow in both directions (Dynamic Updates), not just out of Netbox DNS.

## 1.5.0 - 2026-04-08
- Change to versioning scheme - Now matches the major and minor version number to the one of netbox-plugin-dns. Only the minor sub version
  will be used to track incremental changes to this plugin.
