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
            old = sender.objects.only("name", "soa_serial").get(pk=zone.pk)
            zone._old_name = old.name
            zone._old_soa_serial = old.soa_serial
        except sender.DoesNotExist:
            zone._old_name = None
            zone._old_soa_serial = None
    else:
        zone._old_name = None
        zone._old_soa_serial = None


@receiver(post_save, sender=Zone)
def zone_post_save(sender, instance, created, **kwargs):
    zone = instance

    # Quit if this is not the first signal in this session for this zone.
    try:
        request = current_request.get()
        handled_zones = getattr(request, "_handled_zones", set())
        if zone.pk in handled_zones:
            return
        handled_zones.add(zone.pk)
        request._handled_zones = handled_zones
    except LookupError:
        pass

    # Determine whether the zone's SOA serial number changed with this save.
    # A newly created zone is always considered to have a "changed" serial.
    old_soa_serial = getattr(zone, "_old_soa_serial", None)
    new_soa_serial = getattr(zone, "soa_serial", None)
    soa_serial_changed = created or (old_soa_serial != new_soa_serial)

    # On commit, increment soa serial and if notify is enabled, schedule bg job.
    def _on_commit():
        catzm.increment_soa_serial()

        if SETTINGS.get("notify_clients", False):
            notify_handler.schedule_client_notify(zone)

        # Send a NOTIFY to the zone's own nameservers when its SOA serial changed
        # and the feature is enabled — globally or per zone via a custom field.
        if soa_serial_changed and _notify_ns_enabled(zone):
            notify_handler.schedule_ns_notify(zone)

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


def _notify_ns_enabled(zone) -> bool:
    """Return True if a NOTIFY to the zone's nameservers should be sent.

    Enabled either globally for every zone via ``notify_ns_all_zones`` or per
    zone when the boolean custom field named by ``notify_ns_custom_field_name``
    is set to True on the zone.
    """
    if SETTINGS.get("notify_ns_all_zones", False):
        return True

    cf_name = SETTINGS.get("notify_ns_custom_field_name")
    if not cf_name:
        return False

    custom_fields = getattr(zone, "custom_field_data", None) or {}
    return custom_fields.get(cf_name) is True
