from django.views import View
from django.shortcuts import render

from .models import IntegerKeyValueSetting, SeenTransferClients


class InfoView(View):
    template_name = "netbox_dns_bridge/info.html"

    def get(self, request):
        import netbox_dns.models

        settings_rows = IntegerKeyValueSetting.objects.all().order_by("key")

        seen_clients = (
            SeenTransferClients.objects.select_related("view")
            .all()
            .order_by("source_ip")
        )

        zones = []
        for z in netbox_dns.models.Zone.objects.select_related(
            "view", "catz_identifier"
        ).order_by("name"):
            try:
                catz_identifier = z.catz_identifier.name
            except netbox_dns.models.Zone.catz_identifier.RelatedObjectDoesNotExist:
                catz_identifier = None
            zones.append(
                {
                    "name": z.name,
                    "view": z.view.name if z.view else None,
                    "active": z.active,
                    "catz_identifier": catz_identifier,
                }
            )

        context = {
            "settings_rows": settings_rows,
            "seen_clients": seen_clients,
            "zones": zones,
        }
        return render(request, self.template_name, context)
