import threading
import sys
import dns.query
import dns.message
import dns.tsigkeyring
import dns.name
import dns.zone
import dns.rdatatype
import dns.rdataclass
import dns.rdtypes
import dns.exception
import dns.renderer

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import OperationalError
from netbox_dns.models import View
from netbox_dns_bridge.request_handler import UDPRequestHandler, TCPRequestHandler
from netbox_dns_bridge.dns_server import UDPDNSServer, TCPDNSServer
from netbox_dns_bridge.logger import get_logger

LOGGER = get_logger(__name__)
SETTINGS = settings.PLUGINS_CONFIG.get("netbox_dns_bridge", {})


class Command(BaseCommand):
    help = "Run a minimal AXFR DNS server using data from NetBox DNS plugin"

    def _load_tsig_key_settings(self):
        self.keyring = {}
        self.tsig_view_map = {}

        for view_name, data in self.tsig_keys.items():
            key_name = data.get("keyname")
            secret = data.get("secret")
            algorithm = data.get("algorithm", "hmac-sha256")

            if not key_name:
                LOGGER.error(
                    f"TSIG key for view {view_name} not found. Cannot start transfer endpoint."
                )
                sys.exit(1)
            elif not secret:
                LOGGER.error(
                    f"TSIG secret for key {key_name} not found. Cannot start transfer endpoint."
                )
                sys.exit(1)

            try:
                nb_view = View.objects.get(name=view_name)
            except View.DoesNotExist:
                LOGGER.error(
                    f"Skipping TSIG key {key_name}: View '{view_name}' not found in database."
                )
                continue
            except OperationalError as e:
                LOGGER.error(
                    f"There was an error retrieving view model from database: {e}"
                )
                sys.exit(1)

            # Normalize key name to absolute DNS name
            key_name_obj = dns.name.from_text(
                key_name, origin=dns.name.root
            ).canonicalize()
            key_name_str = key_name_obj.to_text()  # Will always include trailing do

            self.keyring[key_name_obj] = dns.tsig.Key(
                name=key_name_obj, secret=secret, algorithm=algorithm
            )
            self.tsig_view_map[key_name_str] = nb_view
            LOGGER.info(f"Loaded TSIG key {key_name_str} for view {nb_view.name}")

        if not self.keyring:
            msg = "No TSIG keys found in database."
            LOGGER.critical(msg)
            raise RuntimeError(msg)

    def add_arguments(self, parser):
        parser.add_argument(
            "--port", type=int, default=5354, help="Port number to listen on"
        )
        parser.add_argument(
            "--address", type=str, default="0.0.0.0", help="IP to bind to"
        )

    def handle(self, *args, **options):
        # Load parameters
        port = options["port"]
        address = options["address"]

        self.tsig_keys = SETTINGS.get("tsig_keys", None)
        if not self.tsig_keys:
            raise RuntimeError("tsig_keys variable not set in plugin settings.")

        self._load_tsig_key_settings()

        udp_server = UDPDNSServer(
            (address, port), UDPRequestHandler, self.keyring, self.tsig_view_map
        )

        tcp_server = TCPDNSServer(
            (address, port), TCPRequestHandler, self.keyring, self.tsig_view_map
        )

        def _run_udp_server(server):
            LOGGER.info(f"Query endpoint listening on {address} udp/{port}")
            server.serve_forever()

        udp_thread = threading.Thread(
            target=_run_udp_server, args=(udp_server,), daemon=True
        )

        udp_thread.start()

        LOGGER.info(f"Query endpoint listening on {address} tcp/{port}")
        tcp_server.serve_forever()
