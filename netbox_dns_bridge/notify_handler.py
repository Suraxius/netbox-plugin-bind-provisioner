import dns.message
import dns.name
import dns.opcode
import dns.query
import dns.rdatatype
import dns.tsig
from django.conf import settings
from django.utils import timezone
from netbox.jobs import JobRunner
from netbox_dns.models import View, Zone
from .logger import get_logger
from .models import SeenTransferClients

logger = get_logger(__name__)
SETTINGS = settings.PLUGINS_CONFIG["netbox_dns_bridge"]


class SendDNSNotify(JobRunner):
    class Meta:
        name = "Send DNS NOTIFY"

    def _load_tsig_key(self, view_name: str) -> dns.tsig.Key:
        tsig_keys = SETTINGS.get("tsig_keys", {})
        if view_name not in tsig_keys:
            raise RuntimeError(f"No TSIG key configured for view '{view_name}'")

        key_data = tsig_keys[view_name]
        raw_key_name = key_data.get("keyname")
        secret = key_data.get("secret")
        algorithm = key_data.get("algorithm")
        if not algorithm:
            raise RuntimeError(
                f"Missing 'algorithm' in TSIG key configuration for view '{view_name}'"
            )

        if not raw_key_name or not secret:
            raise RuntimeError(
                f"Incomplete TSIG key configuration for view '{view_name}'"
            )

        key_name = dns.name.from_text(raw_key_name, origin=None).canonicalize()
        if not key_name.is_absolute():
            key_name = key_name.concatenate(dns.name.root)

        return dns.tsig.Key(name=key_name, secret=secret, algorithm=algorithm)

    def run(self, *args, **kwargs):
        view_name = kwargs["view_name"]
        zone_name = kwargs["zone_name"]

        view = View.objects.get(name=view_name)
        tsig_key = self._load_tsig_key(view_name)

        cutoff_hours = SETTINGS.get("notify_client_dead_after_hours", 24)
        seen_cutoff = timezone.now() - timezone.timedelta(hours=cutoff_hours)
        clients = SeenTransferClients.objects.filter(
            view=view, last_seen__gte=seen_cutoff
        )

        for name in (zone_name, "catz", f"{view_name}.catz"):
            msg = dns.message.make_query(name, dns.rdatatype.SOA)
            msg.flags = 0
            msg.set_opcode(dns.opcode.NOTIFY)
            msg.use_tsig(keyring={tsig_key.name: tsig_key}, keyname=tsig_key.name)

            for client in clients:
                try:
                    dns.query.udp(msg, client.source_ip, timeout=2)
                    self.logger.info(
                        f"NOTIFY sent to {client.source_ip} for zone {name}"
                    )
                except Exception as e:
                    self.logger.error(
                        f"NOTIFY failed for {client.source_ip} zone {name}: {e}"
                    )


def schedule(zone: Zone):
    SendDNSNotify.enqueue(
        zone_name=zone.name,
        view_name=zone.view.name,
    )
