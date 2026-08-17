from netbox.object_actions import EditObject
from netbox.views import generic
from utilities.views import register_model_view

from .filtersets import (
    CatalogZoneFilterSet,
    CatalogZoneMemberFilterSet,
    SeenTransferClientFilterSet,
)
from .forms import (
    CatalogZoneFilterForm,
    CatalogZoneForm,
    CatalogZoneMemberFilterForm,
    SeenTransferClientFilterForm,
)
from .models import CatalogZone, CatalogZoneMember, SeenTransferClient
from .tables import (
    CatalogZoneMemberTable,
    CatalogZoneTable,
    SeenTransferClientTable,
)


@register_model_view(CatalogZone, "list", path="", detail=False)
class CatalogZoneListView(generic.ObjectListView):
    queryset = CatalogZone.objects.select_related("view").order_by("view__name")
    table = CatalogZoneTable
    filterset = CatalogZoneFilterSet
    filterset_form = CatalogZoneFilterForm
    actions = ()


@register_model_view(CatalogZone)
class CatalogZoneView(generic.ObjectView):
    queryset = CatalogZone.objects.select_related("view")
    actions = (EditObject,)


@register_model_view(CatalogZone, "edit")
class CatalogZoneEditView(generic.ObjectEditView):
    queryset = CatalogZone.objects.select_related("view")
    form = CatalogZoneForm


@register_model_view(CatalogZoneMember, "list", path="", detail=False)
class CatalogZoneMemberListView(generic.ObjectListView):
    queryset = CatalogZoneMember.objects.select_related(
        "zone", "catalog_zone__view"
    ).order_by("catalog_zone__view__name", "name")
    table = CatalogZoneMemberTable
    filterset = CatalogZoneMemberFilterSet
    filterset_form = CatalogZoneMemberFilterForm
    actions = ()


@register_model_view(CatalogZoneMember)
class CatalogZoneMemberView(generic.ObjectView):
    queryset = CatalogZoneMember.objects.select_related(
        "zone", "catalog_zone__view"
    )
    actions = ()


@register_model_view(SeenTransferClient, "list", path="", detail=False)
class SeenTransferClientListView(generic.ObjectListView):
    queryset = SeenTransferClient.objects.select_related("view").order_by("source_ip")
    table = SeenTransferClientTable
    filterset = SeenTransferClientFilterSet
    filterset_form = SeenTransferClientFilterForm
    actions = ()


@register_model_view(SeenTransferClient)
class SeenTransferClientView(generic.ObjectView):
    queryset = SeenTransferClient.objects.select_related("view")
    actions = ()
