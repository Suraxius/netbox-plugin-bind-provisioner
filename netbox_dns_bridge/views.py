from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

import netbox_dns.models
from netbox.views.generic import ObjectListView

from .filtersets import ZoneFilterSet
from .forms import CatalogZoneFilterForm
from .models import CatalogZone, SeenTransferClients
from .tables import CatalogZoneTable


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class CatzOverviewView(ObjectListView):
    queryset = netbox_dns.models.Zone.objects.select_related(
        "view", "catz_identifier"
    ).order_by("view__name", "name")
    table = CatalogZoneTable
    filterset = ZoneFilterSet
    filterset_form = CatalogZoneFilterForm
    template_name = "netbox_dns_bridge/catz_overview.html"
    actions = ()

    def get_extra_context(self, request):
        context = super().get_extra_context(request)
        context["catalog_zones"] = CatalogZone.objects.select_related(
            "view"
        ).order_by("view__name")
        return context


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
