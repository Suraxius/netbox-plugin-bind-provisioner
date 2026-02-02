from django.db import models
import netbox.models
import netbox_dns.models

class IntegerKeyValueSetting(models.Model):
    key = models.CharField(max_length=64)
    value = models.IntegerField()

    def __str__(self):
        return f"{self.key}: {str(self.value)}"

    class Meta:
        default_permissions = ()

class CatalogZoneMemberIdentifier(models.Model):
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
