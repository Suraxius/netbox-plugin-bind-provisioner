from django.utils.translation import gettext_lazy as _
from netbox.plugins import PluginMenu, PluginMenuItem

catalog_zones_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:catalogzone_list",
    link_text=_("Catalog Zones"),
    permissions=["netbox_dns_bridge.view_catalogzone"],
)

catalog_zone_members_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:catalogzonemember_list",
    link_text=_("Catalog Zone Members"),
    permissions=["netbox_dns_bridge.view_catalogzonemember"],
)

seen_transfer_clients_menu_item = PluginMenuItem(
    link="plugins:netbox_dns_bridge:seentransferclient_list",
    link_text=_("Clients"),
    permissions=["netbox_dns_bridge.view_seentransferclient"],
)

menu = PluginMenu(
    label=_("DNS Bridge"),
    groups=(
        (
            _("Catalog Zone"),
            (catalog_zones_menu_item, catalog_zone_members_menu_item),
        ),
        (
            _("Notify"),
            (seen_transfer_clients_menu_item,),
        ),
    ),
    icon_class="mdi mdi-bridge",
)
