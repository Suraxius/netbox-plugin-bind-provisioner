import logging
import socketserver
import socket

logger = logging.getLogger("dns-transfer-endpoint")

class DNSAddressMixin:
    def _resolve_address(self, server_address, socktype, proto):
        host, port = server_address

        infos = socket.getaddrinfo(
            host,
            port,
            socket.AF_UNSPEC,
            socktype,
            proto,
            socket.AI_PASSIVE
        )

        family, _, _, _, sockaddr = infos[0]
        self.address_family = family
        return sockaddr


class TCPDNSServer(DNSAddressMixin, socketserver.TCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, keyring, tsig_view_map):
        sockaddr = self._resolve_address(
            server_address,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP
        )

        super().__init__(sockaddr, handler_class)

        self.keyring = keyring
        self.tsig_view_map = tsig_view_map


class UDPDNSServer(DNSAddressMixin, socketserver.UDPServer):
    allow_reuse_address = True

    def __init__(self, server_address, handler_class, keyring, tsig_view_map):
        sockaddr = self._resolve_address(
            server_address,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP
        )

        super().__init__(sockaddr, handler_class)

        self.keyring = keyring
        self.tsig_view_map = tsig_view_map
