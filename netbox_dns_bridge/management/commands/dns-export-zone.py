import netbox_dns.models
from netbox_dns_bridge.utils import export_bind_zone_file
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            "--view",
            type=str,
            help="The name of the view the Zone to be exported is in",
        )
        parser.add_argument(
            "--zone", type=str, help="The FQDN of the Zone to be exported"
        )
        parser.add_argument(
            "--file", type=str, help="Path of the zone file to be written"
        )

    def handle(self, *args, **options):
        # Load parameters
        view_name = options["view"]
        zone_name = options["zone"]
        file_path = options["file"]

        if not view_name:
            raise CommandError("No --view parameter given")
        elif not zone_name:
            raise CommandError("No --zone parameter given")
        elif not file_path:
            raise CommandError("No --file parameter given")

        try:
            # Load the zone from NetBox DNS
            nb_zone = netbox_dns.models.Zone.objects.get(
                view__name=view_name, name=zone_name
            )

            if nb_zone:
                export_bind_zone_file(nb_zone, file_path=file_path)
                self.stdout.write(
                    self.style.SUCCESS(f"Zone '{zone_name}' exported to '{file_path}'")
                )
            else:
                self.stderr.write("Zone not found in Netbox. Aborting")

        except Exception as e:
            raise CommandError(f"Failed to export zone: {e}")
