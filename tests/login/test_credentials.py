import keyring.errors
import pytest

from rift.login import credentials


class _FakeKeyring:
    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service, account, password):
        self._store[(service, account)] = password

    def get_password(self, service, account):
        return self._store.get((service, account))

    def delete_password(self, service, account):
        if (service, account) not in self._store:
            raise keyring.errors.PasswordDeleteError("not found")
        del self._store[(service, account)]


@pytest.fixture
def fake_keyring(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(credentials.keyring, "set_password", fake.set_password)
    monkeypatch.setattr(credentials.keyring, "get_password", fake.get_password)
    monkeypatch.setattr(credentials.keyring, "delete_password", fake.delete_password)
    return fake


def test_save_and_load_password_round_trip(fake_keyring):
    credentials.save_password("acct", "hunter2")
    assert credentials.load_password("acct") == "hunter2"


def test_load_password_returns_none_when_absent(fake_keyring):
    assert credentials.load_password("nobody") is None


def test_delete_password_removes_entry(fake_keyring):
    credentials.save_password("acct", "hunter2")
    credentials.delete_password("acct")
    assert credentials.load_password("acct") is None


def test_delete_password_is_a_noop_when_absent(fake_keyring):
    credentials.delete_password("nobody")  # does not raise
