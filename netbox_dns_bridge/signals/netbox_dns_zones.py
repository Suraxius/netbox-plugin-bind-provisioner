from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.db import transaction
from netbox.context import current_request
from netbox_dns.models import Zone
from netbox_dns_bridge import catalog_zone_manager as catzm
from netbox_dns_bridge import notify_handler


@receiver(pre_save, sender=Zone)
def zone_pre_save(sender, instance, **kwargs):
    zone = instance
    if zone.pk:
        try:
            zone._old_name = sender.objects.only("name").get(pk=zone.pk).name
        except sender.DoesNotExist:
            zone._old_name = None
    else:
        zone._old_name = None


@receiver(post_save, sender=Zone)
def zone_post_save(sender, instance, created, **kwargs):
    zone = instance
    request = current_request.get()
    handled_zones = getattr(request, "_handled_zones", set())
    if zone.pk in handled_zones:
        return
    handled_zones.add(zone.pk)
    request._handled_zones = handled_zones

    def _on_commit():
        catzm.increment_soa_serial()
        notify_handler.schedule(zone)

    transaction.on_commit(_on_commit)

    if created:
        catzm.update_member_identifier(zone)
    else:
        old_name = getattr(zone, "_old_name", None)
        if old_name != zone.name:
            catzm.update_member_identifier(zone)
