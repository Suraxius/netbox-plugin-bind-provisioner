import django_tables2 as tables
from django.utils.translation import gettext_lazy as _

import netbox_dns.models
from netbox.tables import NetBoxTable

from .models import CatalogZone


class CatalogZoneMemberTable(NetBoxTable):
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
