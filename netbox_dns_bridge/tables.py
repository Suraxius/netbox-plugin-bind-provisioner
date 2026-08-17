import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

from netbox.tables import NetBoxTable
from netbox.tables.columns import ActionsColumn

from .models import CatalogZone, CatalogZoneMember, SeenTransferClient


class CatalogZoneMemberTable(NetBoxTable):
    name = tables.Column(linkify=True)
    zone = tables.Column(
        accessor="zone__name",
        verbose_name=_("Zone"),
        linkify=True,
    )
    view = tables.Column(
        accessor="catalog_zone__view__name",
        verbose_name=_("View"),
    )

    actions = ActionsColumn(actions=())

    class Meta(NetBoxTable.Meta):
        model = CatalogZoneMember
        fields = ("name", "zone", "view")
        default_columns = ("name", "zone", "view")


class CatalogZoneTable(NetBoxTable):
    view = tables.Column(
        accessor="view__name",
        verbose_name=_("View"),
        linkify=True,
    )
    soa_serial = tables.Column(verbose_name=_("SOA Serial"))
    soa_refresh = tables.Column(verbose_name=_("Refresh"))
    soa_retry = tables.Column(verbose_name=_("Retry"))
    soa_expire = tables.Column(verbose_name=_("Expire"))
    soa_minimum = tables.Column(verbose_name=_("Minimum"))

    actions = ActionsColumn(actions=("edit", "changelog"))

    class Meta(NetBoxTable.Meta):
        model = CatalogZone
        fields = (
            "view",
            "soa_serial",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
        )
        default_columns = (
            "view",
            "soa_serial",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
        )


class SeenTransferClientTable(NetBoxTable):
    source_ip = tables.Column(linkify=True)
    view = tables.Column(
        accessor="view__name",
        verbose_name=_("View"),
        linkify=True,
    )
    last_seen = tables.DateTimeColumn(verbose_name=_("Last Seen"))

    actions = ActionsColumn(actions=())

    class Meta(NetBoxTable.Meta):
        model = SeenTransferClient
        fields = ("source_ip", "view", "last_seen")
        default_columns = ("source_ip", "view", "last_seen")
