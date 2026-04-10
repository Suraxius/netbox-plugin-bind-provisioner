import logging
from netbox.plugins import PluginConfig
from django.conf import settings

__version__ = "1.5.3"

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S",  # Date format for timestamps
)


class DNSBridgeConfig(PluginConfig):
    name = "netbox_dns_bridge"
    verbose_name = "Netbox DNS Bridge"
    description = ""
    version = __version__
    author = "Sven Luethi"
    author_email = "dev@sven.luethi.co"
    base_url = "dns-bridge"

    def ready(self):
        self.settings = settings.PLUGINS_CONFIG.get(self.name, None)
        if not self.settings:
            raise RuntimeError(
                f"{self.name}: Plugin {self.verbose_name} failed to initialize due to missing settings. Terminating Netbox."
            )

        from . import signals as signals


config = DNSBridgeConfig
