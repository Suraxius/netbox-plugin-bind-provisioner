from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from netbox_dns.models import Zone
from .models import CatalogZoneMemberIdentifier
from .utils import generate_catz_member_identifier

@receiver(pre_save, sender=Zone)
def zone_pre_save(sender, instance, **kwargs):
    """
    Cache the old name so post_save can see if it changed.
    """
    if instance.pk:
        try:
            instance._old_name = (
                sender.objects
                .only("name")
                .get(pk=instance.pk)
                .name
            )
        except sender.DoesNotExist:
            instance._old_name = None
    else:
        instance._old_name = None

@receiver(post_save, sender=Zone)
def sync_catalog_zone_identifier(sender, instance, created, **kwargs):
    """
    Ensure CatalogZoneMemberIdentifier exists for each Zone
    and keep its identifier in sync.
    """
    identifier = generate_catz_member_identifier()

    if created:
        # Create the related object on Zone creation
        CatalogZoneMemberIdentifier.objects.create(
            zone=instance,
            name=identifier
        )
    else:
        old_name = getattr(instance, "_old_name", None)

        # If the name did not change, do nothing
        if old_name == instance.name:
            return

        # Update identifier
        CatalogZoneMemberIdentifier.objects.update_or_create(
            zone=instance,
            defaults={"name": identifier},
        )
