from django import forms
from django.utils.translation import gettext_lazy as _

import netbox_dns.models
from netbox.forms import NetBoxModelFilterSetForm
from netbox_dns.choices import ZoneStatusChoices
from utilities.forms.fields import DynamicModelMultipleChoiceField


class CatalogZoneFilterForm(NetBoxModelFilterSetForm):
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
