from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuItem

catalog_zones_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:catalog_zones",
    link_text=_("Catalog Zones"),
    permissions=[],
    staff_only=True,
)

catalog_zone_members_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:catalog_zone_members",
    link_text=_("Catalog Zone Members"),
    permissions=[],
    staff_only=True,
)

notify_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:notify",
    link_text=_("Notify"),
    permissions=[],
    staff_only=True,
)

menu = PluginMenu(
    label=_("DNS Bridge"),
    groups=(
        (
            _("Information"),
            (catalog_zones_menu_item, catalog_zone_members_menu_item, notify_menu_item),
        ),
    ),
    icon_class="mdi mdi-bridge",
)
