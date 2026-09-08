"""TLS certificate pinning against the bundled Simutronics EAS certificate.

Simutronics ships a copy of their own self-signed certificate with
reference clients and compares it byte-for-byte against whatever the
server presents during the TLS handshake, rather than relying on public
CA chain validation (confirmed via direct correspondence with Simutronics
staff - see docs/decisions.md; that correspondence itself is confidential
and is never reproduced here). simu.pem is public key material - it is
transmitted in the clear to any connecting client during every handshake,
so bundling a copy is not a confidentiality concern.
"""

from __future__ import annotations

import ssl
from importlib import resources

_BUNDLED_CERT_RESOURCE = "simu.pem"


class CertPinMismatchError(Exception):
    """The server presented a certificate that does not match the bundled one."""


def load_bundled_cert_der() -> bytes:
    pem_text = resources.files(__package__).joinpath(_BUNDLED_CERT_RESOURCE).read_text()
    return ssl.PEM_cert_to_DER_cert(pem_text)


def verify_pin(cert_bytes: bytes) -> None:
    bundled = load_bundled_cert_der()
    if bundled != cert_bytes:
        raise CertPinMismatchError(
            "certificate presented by the server does not match the bundled "
            "Simutronics certificate"
        )
