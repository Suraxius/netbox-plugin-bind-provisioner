import logging
import threading
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
from netbox_dns.models import View
from netbox_plugin_bind_provisioner.service.endpoint.request_handler import UDPRequestHandler, TCPRequestHandler
from netbox_plugin_bind_provisioner.service.endpoint.dns_server import UDPDNSServer, TCPDNSServer
from netbox_plugin_bind_provisioner.service.endpoint import catalog_zone_manager as catzm

logger = logging.getLogger("dns-transfer-endpoint")

class Command(BaseCommand):
    help = "Run a minimal AXFR DNS server using data from NetBox DNS plugin"

    def load_settings(self):
        self.settings = settings.PLUGINS_CONFIG.get(
            "netbox_plugin_bind_provisioner", None
        )
        if not self.settings:
            raise RuntimeError(
                "Command failed to initialize due to missing settings. Terminating Netbox."
            )

        self.tsig_keys = self.settings.get("tsig_keys", None)
        if not self.tsig_keys:
            raise RuntimeError("tsig_keys variable not set in plugin settings.")

    # Load TSIG keys and map them to views
    def load_tsig_key_settings(self):
        self.keyring = {}
        self.tsig_view_map = {}

        for view_name, data in self.tsig_keys.items():
            raw_key_name = data.get("keyname")
            secret = data.get("secret")
            algorithm_str = data.get("algorithm", "hmac-sha256")

            if not raw_key_name or not secret:
                logger.error(
                    f"Skipping TSIG key for view {view_name}: missing keyname or secret."
                )
                continue

            try:
                nb_view = View.objects.get(name=view_name)
            except View.DoesNotExist:
                logger.error(
                    f"Skipping TSIG key {raw_key_name}: view '{view_name}' not found."
                )
                continue

            # Normalize key name to absolute DNS name
            key_name_obj = dns.name.from_text(raw_key_name, origin=None).canonicalize()
            if not key_name_obj.is_absolute():
                key_name_obj = key_name_obj.concatenate(dns.name.root)
            key_name_str = key_name_obj.to_text()  # Will always include trailing do

            self.keyring[key_name_obj] = dns.tsig.Key(
                name=key_name_obj, secret=secret, algorithm=algorithm_str
            )
            self.tsig_view_map[key_name_str] = nb_view
            logger.debug(f"Loaded TSIG key: {key_name_str} view: {nb_view.name}")

        if not self.keyring:
            msg = "No TSIG keys found in database."
            logger.critical(msg)
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
        catzm.init()

        # Initialize settings
        self.load_settings()
        self.load_tsig_key_settings()

        udp_server = UDPDNSServer(
            (address, port), UDPRequestHandler, self.keyring, self.tsig_view_map
        )

        tcp_server = TCPDNSServer(
            (address, port), TCPRequestHandler, self.keyring, self.tsig_view_map
        )

        def run_udp_server(server):
            logger.debug(f"Query endpoint listening on {address} udp/{port}")
            server.serve_forever()

        udp_thread = threading.Thread(
            target=run_udp_server, args=(udp_server,), daemon=True
        )

        udp_thread.start()

        logger.debug(f"Query endpoint listening on {address} tcp/{port}")
        tcp_server.serve_forever()
