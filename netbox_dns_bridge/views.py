from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

import netbox_dns.models
from netbox.views.generic import ObjectEditView, ObjectListView

from .filtersets import CatalogZoneFilterSet, ZoneFilterSet
from .forms import (
    CatalogZoneFilterForm,
    CatalogZoneForm,
    CatalogZoneMemberFilterForm,
)
from .models import CatalogZone, SeenTransferClients
from .tables import CatalogZoneMemberTable, CatalogZoneTable


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class CatalogZoneListView(ObjectListView):
    queryset = CatalogZone.objects.select_related("view").order_by("view__name")
    table = CatalogZoneTable
    filterset = CatalogZoneFilterSet
    filterset_form = CatalogZoneFilterForm
    template_name = "netbox_dns_bridge/catalog_zone_list.html"
    actions = ("edit", "export")


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class CatalogZoneEditView(ObjectEditView):
    queryset = CatalogZone.objects.select_related("view")
    form = CatalogZoneForm
    template_name = "netbox_dns_bridge/catalog_zone_edit.html"


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class CatalogZoneMembersView(ObjectListView):
    queryset = netbox_dns.models.Zone.objects.select_related(
        "view", "catz_identifier"
    ).order_by("view__name", "name")
    table = CatalogZoneMemberTable
    filterset = ZoneFilterSet
    filterset_form = CatalogZoneMemberFilterForm
    template_name = "netbox_dns_bridge/catalog_zone_members.html"
    actions = ()


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class NotifyOverviewView(View):
    template_name = "netbox_dns_bridge/notify_overview.html"

    def get(self, request):
        seen_clients = (
            SeenTransferClients.objects.select_related("view")
            .all()
            .order_by("source_ip")
        )
        context = {"seen_clients": seen_clients}
        return render(request, self.template_name, context)
