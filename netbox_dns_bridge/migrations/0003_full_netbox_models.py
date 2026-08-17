import taggit.managers
import utilities.json
import django.db.models.deletion
from django.db import migrations, models


def copy_serials_and_link_members(apps, schema_editor):
    """Seed one CatalogZone per view from the old global serial and link members."""
    IntegerKeyValueSetting = apps.get_model(
        "netbox_dns_bridge", "IntegerKeyValueSetting"
    )
    CatalogZone = apps.get_model("netbox_dns_bridge", "CatalogZone")
    CatalogZoneMember = apps.get_model("netbox_dns_bridge", "CatalogZoneMember")

    # Preserve the current global serial; default to 1 when never initialized.
    seed_serial = 1
    kv = IntegerKeyValueSetting.objects.filter(key="catalog-zone-soa-serial").first()
    if kv is not None:
        seed_serial = kv.value

    # Create a CatalogZone for every view that currently has at least one
    # member, seeding each with the old global serial.
    view_ids = set(
        CatalogZoneMember.objects.exclude(
            zone__view__isnull=True
        ).values_list("zone__view_id", flat=True)
    )

    view_id_to_catalog_zone = {}
    for view_id in view_ids:
        cz, _ = CatalogZone.objects.get_or_create(
            view_id=view_id, defaults={"soa_serial": seed_serial}
        )
        view_id_to_catalog_zone[view_id] = cz

    # Link each member to the CatalogZone matching its zone's view.
    for member in CatalogZoneMember.objects.select_related("zone__view"):
        cz = view_id_to_catalog_zone.get(member.zone.view_id)
        if cz is None:
            # Defensive: member existed without a resolvable view. Create
            # the CatalogZone on demand so the NOT NULL constraint can be set.
            cz, _ = CatalogZone.objects.get_or_create(
                view_id=member.zone.view_id, defaults={"soa_serial": seed_serial}
            )
            view_id_to_catalog_zone[member.zone.view_id] = cz
        member.catalog_zone = cz
        member.save(update_fields=["catalog_zone"])


def reverse_migration(apps, schema_editor):
    """Best-effort reverse: restore the KV row and null the FK."""
    IntegerKeyValueSetting = apps.get_model(
        "netbox_dns_bridge", "IntegerKeyValueSetting"
    )
    CatalogZone = apps.get_model("netbox_dns_bridge", "CatalogZone")
    CatalogZoneMember = apps.get_model("netbox_dns_bridge", "CatalogZoneMember")

    # Pick a representative serial (first catalog zone) to write back.
    first = CatalogZone.objects.order_by("pk").first()
    serial = first.soa_serial if first is not None else 1
    IntegerKeyValueSetting.objects.update_or_create(
        key="catalog-zone-soa-serial", defaults={"value": serial}
    )

    CatalogZoneMember.objects.update(catalog_zone=None)


class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0140_imageattachment_image_size"),
        (
            "netbox_dns",
            "0032_record_expiration_date",
        ),
        ("netbox_dns_bridge", "0002_alter_integerkeyvaluesetting_options_and_more"),
    ]

    operations = [
        # --- CatalogZone (full NetBoxModel, born with all fields) ---
        migrations.CreateModel(
            name="CatalogZone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("soa_serial", models.IntegerField(default=1)),
                ("soa_refresh", models.IntegerField(default=60)),
                ("soa_retry", models.IntegerField(default=10)),
                ("soa_expire", models.IntegerField(default=1209600)),
                ("soa_minimum", models.IntegerField(default=0)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
                (
                    "view",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="catalog_zone",
                        to="netbox_dns.view",
                    ),
                ),
            ],
            options={
                "ordering": ("view__name",),
            },
        ),
        # --- CatalogZoneMemberIdentifier → CatalogZoneMember (rename + full NetBoxModel) ---
        migrations.RenameModel(
            old_name="CatalogZoneMemberIdentifier",
            new_name="CatalogZoneMember",
        ),
        migrations.AddField(
            model_name="catalogzonemember",
            name="created",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="catalogzonemember",
            name="last_updated",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="catalogzonemember",
            name="custom_field_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                encoder=utilities.json.CustomFieldJSONEncoder,
            ),
        ),
        migrations.AddField(
            model_name="catalogzonemember",
            name="tags",
            field=taggit.managers.TaggableManager(
                through="extras.TaggedItem", to="extras.Tag"
            ),
        ),
        migrations.AlterField(
            model_name="catalogzonemember",
            name="name",
            field=models.CharField(max_length=26),
        ),
        migrations.AlterField(
            model_name="catalogzonemember",
            name="zone",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="catalog_zone_member",
                to="netbox_dns.zone",
            ),
        ),
        migrations.AddField(
            model_name="catalogzonemember",
            name="catalog_zone",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="members",
                to="netbox_dns_bridge.catalogzone",
            ),
        ),
        migrations.RunPython(
            copy_serials_and_link_members,
            reverse_code=reverse_migration,
        ),
        migrations.AlterField(
            model_name="catalogzonemember",
            name="catalog_zone",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="members",
                to="netbox_dns_bridge.catalogzone",
            ),
        ),
        migrations.AddConstraint(
            model_name="catalogzonemember",
            constraint=models.UniqueConstraint(
                fields=("name", "catalog_zone"),
                name="unique_name_per_catalog_zone",
            ),
        ),
        migrations.DeleteModel(
            name="IntegerKeyValueSetting",
        ),
        # --- SeenTransferClients → SeenTransferClient (rename + full NetBoxModel) ---
        migrations.RenameModel(
            old_name="SeenTransferClients",
            new_name="SeenTransferClient",
        ),
        migrations.AddField(
            model_name="seentransferclient",
            name="created",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="seentransferclient",
            name="last_updated",
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name="seentransferclient",
            name="custom_field_data",
            field=models.JSONField(
                blank=True,
                default=dict,
                encoder=utilities.json.CustomFieldJSONEncoder,
            ),
        ),
        migrations.AddField(
            model_name="seentransferclient",
            name="tags",
            field=taggit.managers.TaggableManager(
                through="extras.TaggedItem", to="extras.Tag"
            ),
        ),
    ]
