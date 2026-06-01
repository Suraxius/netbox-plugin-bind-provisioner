from django.db import models

# import netbox.models
import netbox_dns.models


class IntegerKeyValueSetting(models.Model):
    _netbox_private = True

    key = models.CharField(max_length=64)
    value = models.IntegerField()

    def __str__(self):
        return f"{self.key}: {str(self.value)}"


class CatalogZoneMemberIdentifier(models.Model):
    _netbox_private = True

    name = models.CharField(
        max_length=26,
        unique=True,
    )

    zone = models.OneToOneField(
        to=netbox_dns.models.Zone,
        on_delete=models.CASCADE,
        related_name="catz_identifier",
    )

    class Meta:
        ordering = ("name",)

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
