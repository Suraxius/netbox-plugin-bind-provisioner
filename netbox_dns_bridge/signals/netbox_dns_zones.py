from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from netbox.context import current_request
from netbox_dns.models import Zone, View
from netbox_dns_bridge.management.commands.dns_transfer_endpoint import catalog_zone_manager as catzm
from netbox_dns_bridge.jobs import notify


@receiver(pre_save, sender=Zone)
def zone_pre_save(sender, instance, **kwargs):
    zone = instance
    if zone.pk:
        try:
            old = sender.objects.only("name", "soa_serial", "view_id").get(pk=zone.pk)
            zone._old_name = old.name
            zone._old_soa_serial = old.soa_serial
            zone._old_view_id = old.view_id
        except sender.DoesNotExist:
            zone._old_name = None
            zone._old_soa_serial = None
            zone._old_view_id = None
    else:
        zone._old_name = None
        zone._old_soa_serial = None
        zone._old_view_id = None


@receiver(post_save, sender=Zone)
def zone_post_save(sender, instance, created, **kwargs):
    zone = instance

    # Quit if this is not the first signal in this session for this zone.
    try:
        request = current_request.get()
        if request is None:
            raise LookupError
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

    # Detect whether the zone moved between views. When it does, the old
    # view's catalog zone loses a member and the new view's gains one, so
    # both serials must be incremented.
    old_view_id = getattr(zone, "_old_view_id", None)
    view_changed = (
        not created
        and old_view_id is not None
        and old_view_id != zone.view_id
    )

    # On commit, increment soa serial and schedule notify jobs. All settings
    # gating happens inside the scheduling functions.
    def _on_commit():
        if view_changed:
            try:
                old_view = View.objects.get(pk=old_view_id)
                catzm.increment_soa_serial(old_view)
            except View.DoesNotExist:
                pass
        catzm.increment_soa_serial(zone.view)

        if soa_serial_changed:
            notify.schedule_client_notify(zone)
            notify.schedule_ns_notify(zone)

    transaction.on_commit(_on_commit)

    if created:
        # If zone was created, create the catalog zone member record for this zone.
        catzm.update_member(zone)
    else:
        # Re-create the catalog zone member when the zone name or its view
        # changed. A view move leaves the member pointing at the wrong
        # catalog zone, so it must be refreshed.
        old_name = getattr(zone, "_old_name", None)
        if (old_name and zone.name != old_name) or view_changed:
            catzm.update_member(zone)


@receiver(post_delete, sender=Zone)
def zone_post_delete(sender, instance, **kwargs):
    def _on_commit():
        catzm.increment_soa_serial(instance.view)

    transaction.on_commit(_on_commit)
