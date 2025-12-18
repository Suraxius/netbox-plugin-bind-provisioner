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

