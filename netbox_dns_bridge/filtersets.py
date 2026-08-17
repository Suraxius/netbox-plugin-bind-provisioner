import django_filters
from django.db.models import Q

import netbox_dns.models
from netbox.filtersets import NetBoxModelFilterSet
from netbox_dns.choices import ZoneStatusChoices

from .models import CatalogZone


class ZoneFilterSet(NetBoxModelFilterSet):
    view = django_filters.ModelMultipleChoiceFilter(
        field_name="view",
        queryset=netbox_dns.models.View.objects.all(),
    )
    status = django_filters.MultipleChoiceFilter(
        choices=ZoneStatusChoices,
        null_value=None,
    )

    class Meta:
        model = netbox_dns.models.Zone
        fields = ("id", "name", "view", "status", "catz_identifier")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(catz_identifier__name__icontains=value)
        )


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
