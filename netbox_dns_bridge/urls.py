from django.urls import path

from .views import (
    CatalogZoneEditView,
    CatalogZoneListView,
    CatalogZoneMembersView,
    NotifyOverviewView,
)

urlpatterns = [
    path("catalog-zones/", CatalogZoneListView.as_view(), name="catalog_zones"),
    path(
        "catalog-zones/<int:pk>/edit/",
        CatalogZoneEditView.as_view(),
        name="catalogzone_edit",
    ),
    path(
        "catalog-zone-members/",
        CatalogZoneMembersView.as_view(),
        name="catalog_zone_members",
    ),
    path("notify/", NotifyOverviewView.as_view(), name="notify"),
]
