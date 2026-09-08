import pytest

from rift.login import cert_pinning


def test_load_bundled_cert_der_returns_nonempty_bytes():
    der = cert_pinning.load_bundled_cert_der()
    assert isinstance(der, bytes)
    assert len(der) > 0


def test_verify_pin_accepts_the_bundled_cert():
    der = cert_pinning.load_bundled_cert_der()
    cert_pinning.verify_pin(der)  # does not raise


def test_verify_pin_rejects_a_different_cert():
    with pytest.raises(cert_pinning.CertPinMismatchError):
        cert_pinning.verify_pin(b"not-the-real-certificate")
