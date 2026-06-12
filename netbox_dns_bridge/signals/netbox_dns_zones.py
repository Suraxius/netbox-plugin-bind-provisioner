from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.conf import settings
from netbox.context import current_request
from netbox_dns.models import Zone
from netbox_dns_bridge import catalog_zone_manager as catzm
from netbox_dns_bridge import notify_handler

SETTINGS = settings.PLUGINS_CONFIG["netbox_dns_bridge"]


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

    # Quit if this is not the first signal in this session for this zone.
    request = current_request.get()
    if request is not None:
        handled_zones = getattr(request, "_handled_zones", set())
        if zone.pk in handled_zones:
            return
        handled_zones.add(zone.pk)
        request._handled_zones = handled_zones

    # On commit, increment soa serial and if notify is enabled, schedule bg job.
    def _on_commit():
        catzm.increment_soa_serial()

        if SETTINGS.get("notify_clients", False):
            notify_handler.schedule(zone)

    transaction.on_commit(_on_commit)

    if created:
        # If zone was created, create catz member identifier record for this zone.
        catzm.update_member_identifier(zone)
    else:
        # Check if zone name has changed and change the catz member identifier if so.
        old_name = getattr(zone, "_old_name", None)
        if old_name and zone.name != old_name:
            catzm.update_member_identifier(zone)

@receiver(post_delete, sender=Zone)
def zone_post_delete(sender, instance, **kwargs):
    catzm.increment_soa_serial()
