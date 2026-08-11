from collections import OrderedDict

from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views import View

from .models import IntegerKeyValueSetting, SeenTransferClients


@method_decorator(
    user_passes_test(lambda u: u.is_superuser), name="dispatch"
)
class CatzOverviewView(View):
    template_name = "netbox_dns_bridge/catz_overview.html"

    def get(self, request):
        import netbox_dns.models

        soa_serial_obj = IntegerKeyValueSetting.objects.filter(
            key="catalog-zone-soa-serial"
        ).first()
        soa_serial = soa_serial_obj.value if soa_serial_obj else None

        zones_grouped = OrderedDict()
        for z in netbox_dns.models.Zone.objects.select_related(
            "view", "catz_identifier"
        ).order_by("view__name", "name"):
            view_name = z.view.name if z.view else ""
            view_display = view_name[0].upper() + view_name[1:] if view_name else ""
            try:
                catz_identifier = z.catz_identifier.name
            except netbox_dns.models.Zone.catz_identifier.RelatedObjectDoesNotExist:
                catz_identifier = None
            zones_grouped.setdefault(view_display, []).append(
                {
                    "name": z.name,
                    "active": z.active,
                    "catz_identifier": catz_identifier,
                }
            )

        context = {
            "soa_serial": soa_serial,
            "zones_grouped": zones_grouped,
        }
        return render(request, self.template_name, context)


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
