import django_filters
from django.db.models import Q

import netbox_dns.models
from netbox.filtersets import NetBoxModelFilterSet

from .models import CatalogZone, CatalogZoneMember, SeenTransferClient


class CatalogZoneFilterSet(NetBoxModelFilterSet):
    view = django_filters.ModelMultipleChoiceFilter(
        field_name="view",
        queryset=netbox_dns.models.View.objects.all(),
    )

    class Meta:
        model = CatalogZone
        fields = ("id", "view")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(view__name__icontains=value))


class CatalogZoneMemberFilterSet(NetBoxModelFilterSet):
    catalog_zone = django_filters.ModelMultipleChoiceFilter(
        field_name="catalog_zone",
        queryset=CatalogZone.objects.all(),
    )

    class Meta:
        model = CatalogZoneMember
        fields = ("id", "catalog_zone", "zone")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(zone__name__icontains=value)
        )


class SeenTransferClientFilterSet(NetBoxModelFilterSet):
    view = django_filters.ModelMultipleChoiceFilter(
        field_name="view",
        queryset=netbox_dns.models.View.objects.all(),
    )

    class Meta:
        model = SeenTransferClient
        fields = ("id", "view", "source_ip")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(source_ip__icontains=value) | Q(view__name__icontains=value)
        )
