import logging
import socketserver
import os
#import re
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

# from hashlib import sha256
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from netbox_dns.models import Zone, Record, View
from netbox_dns.choices import ZoneStatusChoices, RecordStatusChoices
from datetime import datetime
from netbox_plugin_bind_provisioner.models import IntegerKeyValueSetting

logger = logging.getLogger("bind-transfer-endpoint")


class CatalogZone:
    lock = threading.Lock()
    _serial_max = 0xFFFFFFFF
    _serial_obj = None
    _previous_last_zone_update = None

    # Following function loads the last serial from the DB. No return value
    # but it sets the setting "catalog_serial" or terminates the plugin on failure.
    @classmethod
    def initSerial(cls):
        try:
            cls._serial_obj = IntegerKeyValueSetting.objects.get(
                key="catalog-zone-soa-serial"
            )
            logger.debug(
                f"Catalog zone SOA serial number {cls._serial_obj.value} loaded from database"
            )
        except IntegerKeyValueSetting.DoesNotExist:
            cls._serial_obj = IntegerKeyValueSetting.objects.create(
                key="catalog-zone-soa-serial", value=1
            )
            logger.debug(
                f"Catalog zone SOA serial number was not set in the database. Set to {cls._serial_obj.value}"
            )

    @classmethod
    def _incrementSerial(cls):
        if 0 < cls._serial_obj.value < cls._serial_max:
            cls._serial_obj.value += 1
            cls._serial_obj.save()
        else:
            logger.warn(
                f"Failed to incremenet catalog serial {cls._serial_obj.value}. Will overflow serial back to 1"
            )
            cls._serial_obj = 1
            cls._serial_obj.save()
            logger.debug(
                f"Catalog zone SOA serial number incremented to {_serial_obj.value}"
            )

    @classmethod
    def create(cls, name, view_name):
        # Synchronize following across threads as TCP and UDP listener both use it.
        with cls.lock:
            # cls = self.__class__
            # datestamp = datetime.now().strftime("%y%m%d")
            # latest_zone = Zone.objects.filter().order_by("-last_updated").first()
            latest_zone = (
                Zone.objects.filter(status=ZoneStatusChoices.STATUS_ACTIVE)
                .order_by("-last_updated")
                .first()
            )

            last_zone_update = getattr(latest_zone, "last_updated", None)

            # Check if there was a zone updated since last call
            # If no zone was found previously then this will be false since (None != None) = False
            if cls._previous_last_zone_update != last_zone_update:
                if last_zone_update is not None:
                    logger.debug(
                        f"Zone {latest_zone.name} was updated in view {latest_zone.view.name}"
                    )
                # Setting previous last zone update for next iteration:
                cls._previous_last_zone_update = last_zone_update
                cls._incrementSerial()

        # Zone origin
        origin = dns.name.from_text(name, dns.name.root)

        # Create a new empty zone
        zone = dns.zone.Zone(origin)
        zone.rdclass = dns.rdataclass.IN

        # get zones from netbox
        nb_zones = Zone.objects.filter(
            view__name=view_name, status=ZoneStatusChoices.STATUS_ACTIVE
        )

        ptr_base = dns.name.from_text("zones", origin)

        for nb_zone in nb_zones:
            ttl = nb_zone.soa_ttl
            qname = dns.name.from_text(nb_zone.name, dns.name.root)
            # zone_id = sha256(qname.to_text().encode()).hexdigest()[0:63]
            zone_id = str(nb_zone.id)

            # Create PTR record
            ptr_name = dns.name.from_text(zone_id, ptr_base)
            assert ptr_name.is_subdomain(origin)
            rdata = dns.rdata.from_text(
                dns.rdataclass.IN, dns.rdatatype.PTR, qname.to_text()
            )
            rdataset = zone.find_rdataset(ptr_name, dns.rdatatype.PTR, create=True)
            rdataset.add(rdata, ttl)

            # Configure DNSSec Policy for member Zone if DNSSec is enabled
            if nb_zone.dnssec_policy:
                # Configure policy
                rid = dns.name.from_text("group", ptr_name)
                policy_name = nb_zone.dnssec_policy.name.rstrip(" ")
                group_name = f"dnssec-policy-{policy_name}"
                rdata = dns.rdata.from_text(
                    dns.rdataclass.IN, dns.rdatatype.TXT, group_name
                )
                rdataset = zone.find_rdataset(rid, dns.rdatatype.TXT, create=True)
                rdataset.add(rdata, ttl)

            ## Configure dnssec status for member zone
            # status = str(1 if nb_zone.dnssec_policy else 0)
            # rid = dns.name.from_text("enabled.dnssec.ext", ptr_name)
            # rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.TXT, status)
            # rdataset = zone.find_rdataset(rid, dns.rdatatype.TXT, create=True)
            # rdataset.add(rdata, ttl)

        # SOA Record components
        ttl = 3600
        rclass = dns.rdataclass.IN
        rtype = dns.rdatatype.SOA
        mname = dns.name.root  # dns.name.from_text("invalid.", origin)
        rname = dns.name.root  # dns.name.from_text("contact.master.", origin)
        serial = cls._serial_obj.value
        refresh = 60
        retry = 10
        expire = 1209600
        minimum = 86400

        # Create SOA rdata object
        soa_rdata = dns.rdata.from_text(
            rclass,
            rtype,
            f"{mname} {rname} {serial} {refresh} {retry} {expire} {minimum}",
        )

        # Create Rdataset and add the RDATA to it
        soa_rdataset = dns.rdataset.Rdataset(rclass, rtype)
        soa_rdataset.add(soa_rdata, ttl)

        # Add to the origin node in the zone
        node = zone.find_node(origin, create=True)
        node.rdatasets.append(soa_rdataset)

        # NS record for catz.
        ns_name = dns.name.from_text("invalid", dns.name.root)
        ns_rdata = dns.rdata.from_text(
            dns.rdataclass.IN, dns.rdatatype.NS, str(ns_name)
        )
        ns_rdataset = dns.rdataset.Rdataset(dns.rdataclass.IN, dns.rdatatype.NS)
        ns_rdataset.add(ns_rdata, 86400)

        # Add to node (catz. is the origin)
        ns_node = zone.find_node(origin, create=True)
        ns_node.rdatasets.append(ns_rdataset)

        # TXT record for version.catz.
        version_name = dns.name.from_text(
            "version", origin
        )  # relative to origin "catz."
        txt_rdata = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.TXT, '"2"')

        txt_rdataset = dns.rdataset.Rdataset(dns.rdataclass.IN, dns.rdatatype.TXT)
        txt_rdataset.add(txt_rdata, 86400)

        # Add to node version.catz.
        txt_node = zone.find_node(version_name, create=True)
        txt_node.rdatasets.append(txt_rdataset)

        return zone

    @classmethod
    def importLegacySerialFile(cls, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    serial = int(f.read().strip())
                    cls._serial_obj.value = int(serial)
                    cls._serial_obj.save()
                    logger.info(
                        f"Legacy catalog serial file {file_path} imported into database and file removed. Serial is now {serial}"
                    )
                    os.remove(file_path)
            except OSError as e:
                logger.error(
                    f"Failed to import catalog zone serial from legacy file {file_path}"
                )


class DNSBaseRequestHandler(socketserver.BaseRequestHandler):
    # getZoneFromNB rewritten
    def getZoneFromNB(self, zone_name, view_name):
        # Find the zone
        try:
            nb_zone = Zone.objects.get(
                name=zone_name,
                view__name=view_name,
                status=ZoneStatusChoices.STATUS_ACTIVE,
            )
        except Zone.DoesNotExist:
            return None

        # Build DNS zone
        zone = dns.zone.Zone(zone_name, dns.name.root)
        zone.rdclass = dns.rdataclass.IN

        nb_records = Record.objects.filter(
            zone=nb_zone, status=RecordStatusChoices.STATUS_ACTIVE
        )

        rdatasets_dict = {}

        for record in nb_records:
            rdtype = dns.rdatatype.from_text(record.type)
            if not record.name:
                name = zone.origin
            elif record.name.endswith("."):
                name = dns.name.from_text(record.name)
            else:
                name = dns.name.from_text(record.name, origin=zone.origin)

            # If the record has no TTL, use the zone default
            ttl = record.ttl or nb_zone.default_ttl

            # Apply quoting for TXT records to stop tokanizer
            # from cutting it up:
            value = record.value
            if rdtype == dns.rdatatype.TXT:
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1].replace('" "', '').replace('"', '\"')

                if len(value) > 255:
                    # This is a bug fix for netbox. If netbox allowed for
                    # an unquoted value to be larger then 255 characters,
                    # it misunderstood everything behind a ; as a comment.
                    chunks = ['"{}"'.format(value[i:i+255]) for i in range(0, len(value), 255)]
                    value = " ".join(chunks)
                else:
                    value = f'"{value}"'

            rdata = dns.rdata.from_text(
                dns.rdataclass.IN,
                rdtype,
                value,
                relativize=False,
                origin=zone.origin,
            )

            # Initialize rdataset if it doesn't exist for this name and type
            if name not in rdatasets_dict:
                rdatasets_dict[name] = {}
            if rdtype not in rdatasets_dict[name]:
                rdatasets_dict[name][rdtype] = dns.rdataset.Rdataset(
                    dns.rdataclass.IN, rdtype
                )

            # Add the rdata to the appropriate rdataset
            rdatasets_dict[name][rdtype].add(rdata, ttl)

        # Now, add all rdatasets to the zone
        for name, rdtypes in rdatasets_dict.items():
            for rdtype, rdataset in rdtypes.items():
                # Ensure rdataset has the same rdclass as the zone
                if rdataset.rdclass != zone.rdclass:
                    raise ValueError(
                        f"rdataset rdclass {rdataset.rdclass} does not match zone rdclass {zone.rdclass}"
                    )

                # Check if the rdataset has any rdata before creating an RRset
                if not rdataset:
                    logger.debug(f"Skipping empty rdataset for {name} {rdtype}")
                    continue  # Skip empty rdataset

                # Replace the rdataset for the given name and type
                zone.replace_rdataset(name, rdataset)
        return zone


    def denyRequestBadTSIG(self, wire, tsig_error: dns.rcode):
        # Use empty keyring to parse TSIG without validating
        query = dns.message.from_wire(
            wire, keyring={}, ignore_trailing=True, continue_on_error=True
        )

        # Make a response
        response = dns.message.make_response(query)
        response.set_rcode(dns.rcode.REFUSED)

        if query.had_tsig:
            # Add TSIG with BADKEY, but do not sign (no MAC)
            response.use_tsig(
                keyring={},  # empty; we're not signing
                keyname=query.keyname,
                tsig_error=tsig_error,
            )
        self.denyRequest(query)


class UDPRequestHandler(DNSBaseRequestHandler):
    def denyRequest(self, query, rcode: dns.rcode = dns.rcode.REFUSED):
        response = dns.message.make_response(query)
        response.set_rcode(rcode)
        wire = response.to_wire(multi=False)
        sock = self.request[1]
        sock.sendto(wire, self.client_address)

    def handle(self):
        data, sock = self.request
        peer = self.client_address[0]
        query = None

        try:
            query = dns.message.from_wire(
                data,
                keyring=self.server.keyring,
                continue_on_error=False,
                ignore_trailing=True,
            )
        except Exception as e:
            logger.error("Error parsing query: ", e)
            return

        # Create a response
        response = dns.message.make_response(query)

        # Set the Authoritative Answer flag
        response.flags |= dns.flags.AA

        question = query.question[0]

        # Get the queried record name and type:
        qname = question.name
        qtype = question.rdtype
        dname = qname.to_text().rstrip(".")

        # Only process SOA queries
        if qtype != dns.rdatatype.SOA:
            logger.warning(
                f"Request denied from {peer}: Request was not SOA (Type: {qtype})"
            )
            self.denyRequest(query)
            return

        # Identify TSIG key used
        if not query.had_tsig:
            logger.warning(f"Request denied from {peer}: No TSIG key used")
            self.denyRequest(query)
            return

        key_name = query.keyname.canonicalize().to_text()

        # Check if key matches a view
        nb_view = self.server.tsig_view_map.get(key_name)
        if not nb_view:
            logger.warning(
                f"Request denied from {peer}: {key_name} does not match a view"
            )
            self.denyRequestBadTSIG(wire, dns.rcode.BADKEY)
            return

        # Check if catalog zone
        if dname == "catz" or dname == f"{nb_view.name}.catz":
            zone = CatalogZone.create(dname, nb_view.name)
        # If generic zone, retreive from NB
        else:
            zone = self.getZoneFromNB(dname, nb_view.name)
            # When zone was not found, let client know
            if not zone:
                logger.warning(f"Zone {nb_view.name}/{dname} not found in NB")
                self.denyRequest(query)
                return

        # Retrieve the existing SOA record from the Zone
        soa_rdataset = zone.get_rdataset(zone.origin, dns.rdatatype.SOA)

        # We assume that the SOA rdataset has at least one record (it usually does).
        soa_rdata = soa_rdataset[0]  # Get the first SOA record

        # Now, create the rrset from the soa_rdata
        rrset = dns.rrset.from_rdata(zone.origin, soa_rdataset.ttl, soa_rdata)

        # Append the rrset to the response's answer section
        response.answer.append(rrset)

        # TSIG response
        if query.had_tsig:
            # If key was found in DB
            if query.keyname in self.server.keyring:
                response.use_tsig(
                    self.server.keyring, keyname=query.keyname, original_id=query.id
                )
            else:
                # If key is unknown
                response.set_rcode(dns.rcode.REFUSED)
                # Generate new key for keyname provided
                # keyname = query.keyname
                # b64 = base64.b64encode(urandom(32)).decode("ascii")
                # newkey = dns.tsigkeyring.from_text({ keyname: b64 })
                response.use_tsig(
                    self.server.keyring,
                    keyname=query.keyname,
                    tsig_error=dns.rcode.BADKEY,
                )

        # Send back the response
        response_wire = response.to_wire(max_size=512)
        sock.sendto(response_wire, self.client_address)
        logger.debug(f"{peer} SOA {nb_view.name}/{dname}")


class TCPRequestHandler(DNSBaseRequestHandler):
    def denyRequest(self, query, rcode: dns.rcode = dns.rcode.REFUSED):
        response = dns.message.make_response(query)
        response.set_rcode(rcode)
        wire = response.to_wire(multi=False)
        length = len(wire).to_bytes(2, byteorder="big")
        self.request.sendall(length + wire)

    def handle(self):
        MAX_WIRE = 65535
        # MAX_WIRE = 2000 # For testing fragmentation
        RESERVED_TSIG = 300
        # create a var for setting the client ip in log messages
        peer = self.client_address[0]

        try:
            # Receive the entire message....
            sock = self.request  # TCP socket
            # Read 2-byte length prefix
            length_data = sock.recv(2)
            if len(length_data) < 2:
                return
            length = int.from_bytes(length_data, byteorder="big")
            wire = b""
            while len(wire) < length:
                chunk = sock.recv(length - len(wire))
                if not chunk:
                    return  # connection closed
                wire += chunk

            # Parse the query
            query = None
            try:
                query = dns.message.from_wire(wire, keyring=self.server.keyring)
            # If TSIG signature doesnt match our key, refuse query:
            except dns.tsig.BadSignature as e:
                logger.warning(
                    f"Request denied from {peer} failed TSIG verification: {e}"
                )
                self.denyRequestBadTSIG(wire, dns.rcode.BADSIG)
                return
            # If TSIG Key used is not in our list, refuse query:
            except dns.message.UnknownTSIGKey as e:
                logger.warning(f"Request denied from {peer} with bad TSIG key: {e}")
                self.denyRequestBadTSIG(wire, dns.rcode.BADKEY)
                return

            # If there was no question in the query, refuse
            if len(query.question) != 1:
                self.denyRequest(query)
                return

            # Get the queried record name and type:
            qname = query.question[0].name
            qtype = query.question[0].rdtype

            dname = qname.to_text().rstrip(".")

            # Only process AXFR queries
            if qtype != dns.rdatatype.AXFR:
                # if qtype != dns.rdatatype.AXFR or qtype != dns.rdatatype.SOA:
                logger.warning(
                    f"Request denied from {peer}: Request was not AXFR (Type: {qtype})"
                )
                self.denyRequest(query)
                return

            # Identify TSIG key used
            if not query.had_tsig:
                logger.warning(f"Request denied from {peer}: No TSIG key used")
                self.denyRequest(query)
                return

            key_name = query.keyname.canonicalize().to_text()

            # Check if the key matches a view
            nb_view = self.server.tsig_view_map.get(key_name)
            if not nb_view:
                logger.warning(
                    f"Request denied from {peer}: {key_name} does not match a view"
                )
                self.denyRequest(query)
                return

            # Check if catalog zone
            if dname == "catz" or dname == f"{nb_view.name}.catz":
                zone = CatalogZone.create(dname, nb_view.name)
            else:
                zone = self.getZoneFromNB(dname, nb_view.name)

            # When zone was not found, let client know
            if not zone:
                logger.warning(f"Zone {dname} not found in view {nb_view.name}")
                self.denyRequest(query)
                return

            # 1. Prepare SOA + RRsets (identical to your code)
            soa_rrset = None
            rrsets = []
            for name, rdataset in zone.iterate_rdatasets():
                if not name.is_absolute():
                    name = name.concatenate(zone.origin)
                rrset = dns.rrset.from_rdata_list(name, rdataset.ttl, rdataset)
                if rdataset.rdtype == dns.rdatatype.SOA and soa_rrset is None:
                    soa_rrset = rrset
                else:
                    rrsets.append(rrset)

            if soa_rrset is None:
                logger.error(f"Zone {dname} has no SOA — aborting AXFR")
                return

            rrsets.insert(0, soa_rrset)  # Opening SOA
            rrsets.append(soa_rrset)  # Closing SOA

            # 2. Create a Renderer for the first message
            r = dns.renderer.Renderer(
                id=query.id,
                flags=(dns.flags.QR | dns.flags.AA),
                max_size=MAX_WIRE,
                origin=None,
            )
            r.add_question(
                query.question[0].name,
                query.question[0].rdtype,
                query.question[0].rdclass,
            )

            # 3. Loop through RRsets
            tsig_ctx = None
            for rrset in rrsets:
                # logger.debug(f"Iterating over rrset {rrset}. tsig_ctx: {tsig_ctx}")
                try:
                    # logger.debug(f"Adding {rrset} to renderer object")
                    r.add_rrset(dns.renderer.ANSWER, rrset)
                    if r.max_size - len(r.output.getvalue()) < RESERVED_TSIG:
                        raise dns.exception.TooBig("TSIG wont fit")
                except dns.exception.TooBig:
                    # TSIG chain previous message
                    r.write_header()
                    tsig_ctx = r.add_multi_tsig(
                        ctx=tsig_ctx,
                        secret=self.server.keyring[query.keyname],
                        keyname=query.keyname,
                        fudge=300,
                        id=query.id,
                        tsig_error=0,
                        other_data=b"",
                        request_mac=r.mac if tsig_ctx else query.mac,
                    )
                    wire = r.get_wire()
                    self.request.sendall(len(wire).to_bytes(2, "big") + wire)

                    # Start new renderer
                    r = dns.renderer.Renderer(
                        id=query.id,
                        flags=(dns.flags.QR | dns.flags.AA),
                        max_size=MAX_WIRE,
                        origin=None,
                    )
                    r.add_question(
                        query.question[0].name,
                        query.question[0].rdtype,
                        query.question[0].rdclass,
                    )
                    r.add_rrset(dns.renderer.ANSWER, rrset)

            # 4. Final message with terminating TSIG
            r.write_header()
            # logger.debug(f"Final message. tsig_ctx: {tsig_ctx}")
            tsig_ctx = r.add_multi_tsig(
                ctx=tsig_ctx,
                secret=self.server.keyring[query.keyname],
                keyname=query.keyname,
                fudge=300,
                id=query.id,
                tsig_error=0,
                other_data=b"",
                # request_mac=r.mac if tsig_ctx else None,
                request_mac=r.mac if tsig_ctx else query.mac,
            )
            wire = r.get_wire()
            self.request.sendall(len(wire).to_bytes(2, "big") + wire)

            # logger.debug(f"Zone transfer request for {nb_view.name}/{dname} from {peer}")
            logger.debug(f"{peer} AXFR {nb_view.name}/{dname}")

        except Exception as e:
            logger.error(f"Error handling request from {peer}: {e}")
            import traceback

            traceback.print_exc()


class TCPDNSServer(socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, keyring, tsig_view_map):
        super().__init__(server_address, handler_class)
        self.keyring = keyring
        self.tsig_view_map = tsig_view_map


class UDPDNSServer(socketserver.UDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, keyring, tsig_view_map):
        super().__init__(server_address, handler_class)
        self.keyring = keyring
        self.tsig_view_map = tsig_view_map


class Command(BaseCommand):
    help = "Run a minimal AXFR DNS server using NetBox DNS plugin data"

    def loadSettings(self):
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
    def loadTSIGKeySettings(self):
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
        CatalogZone.initSerial()
        # Initialize settings
        self.loadSettings()
        # self.loadCatalogZoneSettings()
        self.loadTSIGKeySettings()
        # Following is temporary. Function and invocation can be deleted once v1.0 is reached.
        serial_file = self.settings.get("catalog_serial_file", None)
        if serial_file:
            CatalogZone.importLegacySerialFile(serial_file)

        udp_server = UDPDNSServer(
            (address, port), UDPRequestHandler, self.keyring, self.tsig_view_map
        )
        tcp_server = TCPDNSServer(
            (address, port), TCPRequestHandler, self.keyring, self.tsig_view_map
        )

        def run_udp_server(server):
            logger.debug(f"SOA endpoint listening on {address} udp/{port}")
            server.serve_forever()

        udp_thread = threading.Thread(
            target=run_udp_server, args=(udp_server,), daemon=True
        )
        udp_thread.start()

        logger.debug(f"AXFR endpoint listening on {address} tcp/{port}")
        tcp_server.serve_forever()
