from django.db import models
import netbox.models
import netbox_dns.models


# class CatalogZoneSerial(models.Model):
class IntegerKeyValueSetting(netbox.models.NetBoxModel):
    # view = models.ForeignKey(netbox_dns.models.View, on_delete=models.CASCADE)
    key = models.CharField(max_length=64)
    value = models.IntegerField()

    def __str__(self):
        # return f'{self.view.name}: {self.serial}'
        return f"{self.key}: {str(self.value)}"


# class TSIGKey(netbox.models.NetBoxModel):
#    view      = models.ForeignKey(netbox_dns.models.View, on_delete=models.CASCADE)
#    name      = models.CharField(max_length=256)
#    algorithm = models.CharField(max_length=25)
#    secret    = models.CharField(max_length=50)
#
#    def __str__(self):
#        return f'key "{self.name}" {{ algorithm {self.algorithm}; secret "{self.secret}"; }};'
