import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

import netbox_dns.models
from netbox.tables import NetBoxTable


class CatalogZoneTable(NetBoxTable):
    name = tables.Column(linkify=True)
    view = tables.Column(
        accessor="view__name",
        verbose_name=_("View"),
    )
    status = tables.Column(verbose_name=_("Status"))
    catz_identifier = tables.Column(
        accessor="catz_identifier__name",
        verbose_name=_("Catalog Zone Identifier"),
        default="—",
    )

    class Meta(NetBoxTable.Meta):
        model = netbox_dns.models.Zone
        fields = ("name", "view", "status", "catz_identifier")
        default_columns = ("name", "view", "status", "catz_identifier")
