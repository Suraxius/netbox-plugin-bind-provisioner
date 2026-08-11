from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuItem

info_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:info",
    link_text=_("Info"),
    permissions=[],
)

menu = PluginMenu(
    label=_("DNS Bridge"),
    groups=(
        (_("Information"), (info_menu_item,)),
    ),
    icon_class="mdi mdi-bridge",
)
