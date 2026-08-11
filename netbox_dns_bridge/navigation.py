from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuItem

information_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:catz",
    link_text=_("Catalog Zones"),
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
        (_("Information"), (information_menu_item, notify_menu_item)),
    ),
    icon_class="mdi mdi-bridge",
)
