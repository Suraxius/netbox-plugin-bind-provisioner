import django.db.models.deletion
from django.db import migrations, models


def copy_serials_and_link_identifiers(apps, schema_editor):
    """Seed one CatalogZone per view from the old global serial and link identifiers."""
    IntegerKeyValueSetting = apps.get_model(
        "netbox_dns_bridge", "IntegerKeyValueSetting"
    )
    CatalogZone = apps.get_model("netbox_dns_bridge", "CatalogZone")
    CatalogZoneMemberIdentifier = apps.get_model(
        "netbox_dns_bridge", "CatalogZoneMemberIdentifier"
    )

    # Preserve the current global serial; default to 1 when never initialized.
    seed_serial = 1
    kv = IntegerKeyValueSetting.objects.filter(key="catalog-zone-soa-serial").first()
    if kv is not None:
        seed_serial = kv.value

    # Create a CatalogZone for every view that currently has at least one
    # member identifier, seeding each with the old global serial.
    view_ids = set(
        CatalogZoneMemberIdentifier.objects.exclude(
            zone__view__isnull=True
        ).values_list("zone__view_id", flat=True)
    )

    view_id_to_catalog_zone = {}
    for view_id in view_ids:
        cz, _ = CatalogZone.objects.get_or_create(
            view_id=view_id, defaults={"soa_serial": seed_serial}
        )
        view_id_to_catalog_zone[view_id] = cz

    # Link each identifier to the CatalogZone matching its zone's view.
    for ident in CatalogZoneMemberIdentifier.objects.select_related("zone__view"):
        cz = view_id_to_catalog_zone.get(ident.zone.view_id)
        if cz is None:
            # Defensive: identifier existed without a resolvable view. Create
            # the CatalogZone on demand so the NOT NULL constraint can be set.
            cz, _ = CatalogZone.objects.get_or_create(
                view_id=ident.zone.view_id, defaults={"soa_serial": seed_serial}
            )
            view_id_to_catalog_zone[ident.zone.view_id] = cz
        ident.catalog_zone = cz
        ident.save(update_fields=["catalog_zone"])


def reverse_migration(apps, schema_editor):
    """Best-effort reverse: restore the KV row and null the FK."""
    IntegerKeyValueSetting = apps.get_model(
        "netbox_dns_bridge", "IntegerKeyValueSetting"
    )
    CatalogZone = apps.get_model("netbox_dns_bridge", "CatalogZone")
    CatalogZoneMemberIdentifier = apps.get_model(
        "netbox_dns_bridge", "CatalogZoneMemberIdentifier"
    )

    # Pick a representative serial (first catalog zone) to write back.
    first = CatalogZone.objects.order_by("pk").first()
    serial = first.soa_serial if first is not None else 1
    IntegerKeyValueSetting.objects.update_or_create(
        key="catalog-zone-soa-serial", defaults={"value": serial}
    )

    CatalogZoneMemberIdentifier.objects.update(catalog_zone=None)


class Migration(migrations.Migration):

    dependencies = [
        (
            "netbox_dns",
            "0030_dnsseckeytemplate_comments_dnsseckeytemplate_owner_and_more",
        ),
        ("netbox_dns_bridge", "0002_alter_integerkeyvaluesetting_options_and_more"),
    ]

    operations = [
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
        migrations.AddField(
            model_name="catalogzonememberidentifier",
            name="catalog_zone",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="member_identifiers",
                to="netbox_dns_bridge.catalogzone",
            ),
        ),
        migrations.AlterField(
            model_name="catalogzonememberidentifier",
            name="name",
            field=models.CharField(max_length=26),
        ),
        migrations.RunPython(
            copy_serials_and_link_identifiers,
            reverse_code=reverse_migration,
        ),
        migrations.AlterField(
            model_name="catalogzonememberidentifier",
            name="catalog_zone",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="member_identifiers",
                to="netbox_dns_bridge.catalogzone",
            ),
        ),
        migrations.AddConstraint(
            model_name="catalogzonememberidentifier",
            constraint=models.UniqueConstraint(
                fields=("name", "catalog_zone"),
                name="unique_name_per_catalog_zone",
            ),
        ),
        migrations.DeleteModel(
            name="IntegerKeyValueSetting",
        ),
    ]
