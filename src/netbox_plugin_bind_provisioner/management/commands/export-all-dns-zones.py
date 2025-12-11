import os
import dns.zone
import dns.rdatatype
import dns.rdataclass
import dns.exception
import netbox_dns.models
from netbox_plugin_bind_provisioner.utils import export_bind_zone_file
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            "--path", type=str, help="Path to the directory where zone files are to be written"
        )

    def handle(self, *args, **options):
        # Load parameters
        base_path = options['path']

        if not base_path:
            raise CommandError("No --path parameter given")

        # Ensure base_path exists
        os.makedirs(base_path, exist_ok=True)

        # Iterate through all zones
        nb_zones = netbox_dns.models.Zone.objects.prefetch_related("view").all()
        if not nb_zones.exists():
            self.stdout.write(self.style.WARNING("No zones found in NetBox DNS."))
            return

        for zone in nb_zones:
            # Determine view directory
            view_name = zone.view.name
            view_dir = os.path.join(base_path, view_name)
            os.makedirs(view_dir, exist_ok=True)

            # Zone file path
            file_path = os.path.join(view_dir, zone.name)

            try:
                # Call existing export function
                export_bind_zone_file(zone, file_path=file_path)
                self.stdout.write(self.style.SUCCESS(f"Exported zone '{zone.name}' to '{file_path}'"))
            except Exception as e:
                self.stderr.write(f"Failed to export zone '{zone.name}': {e}")
