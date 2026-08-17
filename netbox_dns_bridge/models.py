from django.db import models
from django.urls import reverse

# import netbox.models
import netbox_dns.models


class CatalogZone(models.Model):
    _netbox_private = True

    view = models.OneToOneField(
        to=netbox_dns.models.View,
        on_delete=models.CASCADE,
        related_name="catalog_zone",
    )
    soa_serial = models.IntegerField(default=1)
    soa_refresh = models.IntegerField(default=60)
    soa_retry = models.IntegerField(default=10)
    soa_expire = models.IntegerField(default=1209600)
    soa_minimum = models.IntegerField(default=0)

    class Meta:
        ordering = ("view__name",)

    def __str__(self):
        return f"{self.view.name}: {self.soa_serial}"

    def get_absolute_url(self):
        return reverse("plugins:netbox_dns_bridge:catalogzone_edit", args=[self.pk])


class CatalogZoneMemberIdentifier(models.Model):
    _netbox_private = True

    name = models.CharField(
        max_length=26,
    )

    zone = models.OneToOneField(
        to=netbox_dns.models.Zone,
        on_delete=models.CASCADE,
        related_name="catz_identifier",
    )

    catalog_zone = models.ForeignKey(
        to=CatalogZone,
        on_delete=models.CASCADE,
        related_name="member_identifiers",
    )

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["name", "catalog_zone"],
                name="unique_name_per_catalog_zone",
            ),
        ]

    def __str__(self):
        return self.name


class SeenTransferClients(models.Model):
    _netbox_private = True

    source_ip = models.GenericIPAddressField()
    last_seen = models.DateTimeField()
    view = models.ForeignKey(
        to=netbox_dns.models.View,
        on_delete=models.PROTECT,
        related_name="seen_transfer_clients",
    )

    def __str__(self):
        return f"{self.source_ip} ({self.view.name})"

    class Meta:
        ordering = ("source_ip",)
        constraints = [
            models.UniqueConstraint(
                fields=["source_ip", "view"],
                name="unique_ip_view_seen_client",
            ),
        ]
