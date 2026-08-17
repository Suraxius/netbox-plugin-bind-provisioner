from django.urls import include, path

from utilities.urls import get_model_urls

# Import views so register_model_view decorators run.
from .views import (  # noqa: F401
    CatalogZoneEditView,
    CatalogZoneListView,
    CatalogZoneMemberListView,
    CatalogZoneMemberView,
    CatalogZoneView,
    SeenTransferClientListView,
    SeenTransferClientView,
)

urlpatterns = [
    path(
        "catalog-zones/",
        include(
            get_model_urls("netbox_dns_bridge", "catalogzone", detail=False)
        ),
    ),
    path(
        "catalog-zones/<int:pk>/",
        include(get_model_urls("netbox_dns_bridge", "catalogzone")),
    ),
    path(
        "catalog-zone-members/",
        include(
            get_model_urls("netbox_dns_bridge", "catalogzonemember", detail=False)
        ),
    ),
    path(
        "catalog-zone-members/<int:pk>/",
        include(get_model_urls("netbox_dns_bridge", "catalogzonemember")),
    ),
    path(
        "seen-transfer-clients/",
        include(
            get_model_urls("netbox_dns_bridge", "seentransferclient", detail=False)
        ),
    ),
    path(
        "seen-transfer-clients/<int:pk>/",
        include(get_model_urls("netbox_dns_bridge", "seentransferclient")),
    ),
]
