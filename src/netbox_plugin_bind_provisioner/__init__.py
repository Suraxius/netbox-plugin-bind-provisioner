import logging
from netbox.plugins import PluginConfig
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.dispatch import receiver
from django.conf import settings

__version__ = "0.9.2"

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.DEBUG,  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S",  # Date format for timestamps
)


class BindProvisionerConfig(PluginConfig):
    name = "netbox_bind_provisioner"
    verbose_name = "Netbox Bind Provisioner"
    description = "Provisions Zones to a Bind Server configured as hidden master"
    version = __version__
    author = "Sven Luethi"
    author_email = "sven.luethi@everyware.ch"
    base_url = "bind_provisioner"

    def ready(self):
        self.settings = settings.PLUGINS_CONFIG.get(self.name, None)
        if not self.settings:
            raise RuntimeError(
                f"{self.name}: Plugin {self.verbose_name} failed to initialize due to missing settings. Terminating Netbox."
            )

    #    from . import bind, rndc
    #
    #    if not bind.zoneDirWritable():
    #        BIND_ZONE_DIR = settings.get("BIND_ZONE_DIR")
    #        logger.error(f"Bind's zone file directory {BIND_ZONE_DIR} is not writable.")
    #        raise RuntimeError(
    #            "Plugin initialization failed due to failed writable-zone-directory healthcheck."
    #        )
    #    if not rndc.tsigKeyFileAccessible():
    #        RNDC_KEY_FILE = settings.get("RNDC_KEY_FILE")
    #        logger.error(f"The RNDC key file {RNDC_KEY_FILE} is inaccessible.")
    #        raise RuntimeError(
    #            "Plugin initialization failed due to failed rndc-key-accessible healthcheck."
    #        )
    #
    #    # Import signal callbacks from signals.py (With @receiver decorations)
    #    from . import signals


config = BindProvisionerConfig
default_app_config = ".apps.NetboxBindProvisionerConfig"
