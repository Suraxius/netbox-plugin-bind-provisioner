from django.core.management.base import BaseCommand, CommandError
from netbox_dns_bridge.models import IntegerKeyValueSetting


class Command(BaseCommand):
    help = "Get or set integer key-value settings"

    def add_arguments(self, parser):
        parser.add_argument(
            "action", choices=["get", "set", "list"], help="Action to perform"
        )
        parser.add_argument("key", nargs="?", help="Setting key")
        parser.add_argument(
            "value", nargs="?", type=int, help="Value to set (required for 'set')"
        )

    def handle(self, *args, **options):
        action = options["action"]
        key = options.get("key")
        value = options.get("value")

        if action == "list":
            settings = IntegerKeyValueSetting.objects.all()
            if not settings.exists():
                self.stdout.write("No settings found.")
                return
            for setting in settings:
                self.stdout.write(str(setting))

        elif action == "get":
            if not key:
                raise CommandError("A key is required for GET")
            try:
                setting = IntegerKeyValueSetting.objects.get(key=key)
                self.stdout.write(f"{setting.key}: {setting.value}")
            except IntegerKeyValueSetting.DoesNotExist:
                raise CommandError(f"No setting was found for {key}")

        elif action == "set":
            if not key:
                raise CommandError("A setting is required for SET command")
            if value is None:
                raise CommandError("A value is required for SET command")
            try:
                setting = IntegerKeyValueSetting.objects.get(key=key)
                old_value = setting.value
                setting.value = value
                setting.save()
                self.stdout.write(f"Updated {key} from {old_value} to {value}")
            except IntegerKeyValueSetting.DoesNotExist:
                raise CommandError(f"No setting found for {key}")
