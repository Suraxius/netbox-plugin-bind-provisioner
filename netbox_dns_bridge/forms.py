from django import forms
from django.utils.translation import gettext_lazy as _

import netbox_dns.models
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from netbox_dns.choices import ZoneStatusChoices
from utilities.forms.fields import DynamicModelMultipleChoiceField

from .models import CatalogZone


class CatalogZoneForm(NetBoxModelForm):
    soa_serial = forms.IntegerField(label=_("SOA Serial"))
    soa_refresh = forms.IntegerField(label=_("Refresh"))
    soa_retry = forms.IntegerField(label=_("Retry"))
    soa_expire = forms.IntegerField(label=_("Expire"))
    soa_minimum = forms.IntegerField(label=_("Minimum"))

    view = forms.ModelChoiceField(
        queryset=netbox_dns.models.View.objects.all(),
        disabled=True,
        required=False,
        label=_("View"),
    )

    class Meta:
        model = CatalogZone
        fields = (
            "view",
            "soa_serial",
            "soa_refresh",
            "soa_retry",
            "soa_expire",
            "soa_minimum",
        )


class CatalogZoneMemberFilterForm(NetBoxModelFilterSetForm):
    model = netbox_dns.models.Zone

    q = forms.CharField(required=False, label=_("Search"))
    view = DynamicModelMultipleChoiceField(
        queryset=netbox_dns.models.View.objects.all(),
        required=False,
    )
    status = forms.MultipleChoiceField(
        choices=ZoneStatusChoices,
        required=False,
    )


class CatalogZoneFilterForm(NetBoxModelFilterSetForm):
    model = CatalogZone

    q = forms.CharField(required=False, label=_("Search"))
    view = DynamicModelMultipleChoiceField(
        queryset=netbox_dns.models.View.objects.all(),
        required=False,
    )
