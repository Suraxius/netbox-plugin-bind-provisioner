from django.db import models

# import netbox.models
import netbox_dns.models
from netbox.models import NetBoxModel


class CatalogZone(NetBoxModel):
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
        verbose_name = "Catalog Zone"
        verbose_name_plural = "Catalog Zones"

    def __str__(self):
        return f"{self.view.name}: {self.soa_serial}"


class CatalogZoneMember(NetBoxModel):
    name = models.CharField(
        max_length=26,
    )

    zone = models.OneToOneField(
        to=netbox_dns.models.Zone,
        on_delete=models.CASCADE,
        related_name="catalog_zone_member",
    )

    catalog_zone = models.ForeignKey(
        to=CatalogZone,
        on_delete=models.CASCADE,
        related_name="members",
    )

    class Meta:
        ordering = ("name",)
        verbose_name = "Catalog Zone Member"
        verbose_name_plural = "Catalog Zone Members"
        constraints = [
            models.UniqueConstraint(
                fields=["name", "catalog_zone"],
                name="unique_name_per_catalog_zone",
            ),
        ]

    def __str__(self):
        return self.name


class SeenTransferClient(NetBoxModel):
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
        verbose_name = "Seen Transfer Client"
        verbose_name_plural = "Seen Transfer Clients"
        constraints = [
            models.UniqueConstraint(
                fields=["source_ip", "view"],
                name="unique_ip_view_seen_client",
            ),
        ]
