from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_dns_bridge", "0002_alter_integerkeyvaluesetting_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integerkeyvaluesetting",
            name="key",
            field=models.CharField(max_length=64, unique=True),
        ),
    ]
