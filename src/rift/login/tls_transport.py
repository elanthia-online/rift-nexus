"""TLS socket transport for the EAS connection.

Wraps a TCP socket in TLS, verifies the certificate presented by the
server against the bundled Simutronics certificate (see cert_pinning.py),
and provides message-oriented send/receive over the encrypted connection.
This is the one module in `login` that does real network I/O -
eas_client.py depends only on the Transport protocol below, so it can be
exercised in tests against a fake.

Per guidance from Simutronics on this transport, messages carry no
trailing delimiter - the TLS layer is trusted to deliver each message as
a complete unit, so recv_packet() does a single read per message rather
than buffering until a delimiter appears.
"""

from __future__ import annotations

import socket
import ssl
from typing import Protocol

from rift.login import cert_pinning

EAS_HOST = "eaccess.play.net"
EAS_PORT = 7910
_RECV_CHUNK = 4096
_ENCODING = "latin-1"  # 1:1 byte mapping - obscure_password() produces bytes 0-255


class Transport(Protocol):
    def connect(self) -> None: ...
    def send_line(self, line: str) -> None: ...
    def recv_packet(self) -> str: ...
    def close(self) -> None: ...


class TLSTransport:
    def __init__(self, host: str = EAS_HOST, port: int = EAS_PORT):
        self._host = host
        self._port = port
        self._sock: ssl.SSLSocket | None = None

    def connect(self) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        # EAS uses a self-signed cert; the cert_pinning check below against
        # the bundled Simutronics cert is the real trust boundary, not
        # chain validation - see docs/decisions.md.
        context.verify_mode = ssl.CERT_NONE
        raw_sock = socket.create_connection((self._host, self._port))
        self._sock = context.wrap_socket(raw_sock, server_hostname=self._host)
        cert_bytes = self._sock.getpeercert(binary_form=True)
        if cert_bytes is None:
            raise ConnectionError("EAS server did not present a certificate")
        cert_pinning.verify_pin(cert_bytes)

    def send_line(self, line: str) -> None:
        assert self._sock is not None, "not connected"
        self._sock.sendall(line.encode(_ENCODING))

    def recv_packet(self) -> str:
        assert self._sock is not None, "not connected"
        chunk = self._sock.recv(_RECV_CHUNK)
        return chunk.decode(_ENCODING)

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
