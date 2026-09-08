"""Tests for LoginWorker - the QThread worker wrapping the EASClient login flow.

Does not use a real QThread - slots are called synchronously in the test
thread, and plain Python callables are connected to the signals, which
works fine for PySide6 direct connections (no running event loop needed) -
same approach as tests/client/test_stream_worker.py.

Exercises the real EASClient against a scripted fake Transport (same
pattern as tests/login/test_eas_client.py, duplicated here to keep this
module self-contained) rather than mocking EASClient itself, so the
exception handling in the worker is checked against the real exception
types eas_wire.py actually raises. sal.py/launcher.py are monkeypatched,
since they already have their own dedicated test suites - this module
tests only the orchestration in LoginWorker.
"""

from pathlib import Path

from rift.login import worker as worker_module
from rift.login.eas_client import EASClient
from rift.login.eas_wire import obscure_password
from rift.login.models import CharacterListing, HandoffInfo
from rift.login.worker import LoginWorker


class FakeTransport:
    """Scripted transport double: each entry maps an expected outgoing line
    to the canned response returned for the recv_packet() that follows it."""

    def __init__(self, script: list[tuple[str, str]]):
        self._script = list(script)
        self.sent_lines: list[str] = []
        self.connected = False
        self.closed = False

    def connect(self) -> None:
        self.connected = True

    def send_line(self, line: str) -> None:
        self.sent_lines.append(line)

    def recv_packet(self) -> str:
        expected_line, response = self._script.pop(0)
        assert self.sent_lines[-1] == expected_line, (
            f"expected transport to have just sent {expected_line!r}, "
            f"but last sent line was {self.sent_lines[-1]!r}"
        )
        return response

    def close(self) -> None:
        self.closed = True


def _scrambled(password: str, hash_key: str) -> str:
    return obscure_password(password, hash_key)


def test_login_success_emits_authenticated_then_characters_ready():
    transport = FakeTransport(
        [
            ("K", "K\tHASHKEY"),
            ("A\tacct\t" + _scrambled("pw", "HASHKEY"), "A\tKEY\teassessionkey"),
            ("M", "M\tGS3\tGS Prime"),
            ("N\tGS3", "N\tSTORM"),
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    authenticated = []
    characters = []
    worker.authenticated.connect(lambda: authenticated.append(True))
    worker.characters_ready.connect(characters.append)

    worker.login("acct", "pw")

    assert authenticated == [True]
    assert characters == [
        [CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior")]
    ]
    assert transport.connected is True


def test_login_auth_failure_emits_auth_failed_not_characters_ready():
    transport = FakeTransport(
        [
            ("K", "K\tHASHKEY"),
            ("A\tacct\t" + _scrambled("wrong", "HASHKEY"), "A\tERROR\tPASSWORD"),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    auth_failed = []
    characters = []
    worker.auth_failed.connect(auth_failed.append)
    worker.characters_ready.connect(characters.append)

    worker.login("acct", "wrong")

    assert len(auth_failed) == 1
    assert "password" in auth_failed[0].lower()
    assert characters == []


def test_login_other_failure_emits_generic_error_not_auth_failed():
    transport = FakeTransport(
        [
            ("K", "K\tHASHKEY"),
            ("A\tacct\t" + _scrambled("pw", "HASHKEY"), "A\tKEY\teassessionkey"),
            ("M", "not a valid M response"),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    errors = []
    auth_failed = []
    worker.error.connect(errors.append)
    worker.auth_failed.connect(auth_failed.append)

    worker.login("acct", "pw")

    assert len(errors) == 1
    assert auth_failed == []


def test_select_character_success_writes_sal_launches_and_closes(monkeypatch):
    transport = FakeTransport(
        [
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            (
                "L\tABC\tSTORM",
                "L\tOK\tGAMEHOST=game.example.com\tGAMEPORT=1234\tKEY=sessionkey\tGAME=STORM",
            ),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    written_handoffs = []
    launch_calls = []
    monkeypatch.setattr(
        worker_module.sal,
        "write_sal_file",
        lambda handoff: written_handoffs.append(handoff) or Path("/tmp/fake.sal"),
    )
    monkeypatch.setattr(
        worker_module.launcher,
        "launch",
        lambda path, template: launch_calls.append((path, template)),
    )

    handoffs = []
    launched = []
    errors = []
    worker.handoff_ready.connect(handoffs.append)
    worker.launched.connect(lambda: launched.append(True))
    worker.error.connect(errors.append)

    worker.select_character("GS3", "ABC", "custom-template {sal_path}")

    expected_handoff = HandoffInfo(
        gamehost="game.example.com", gameport="1234", key="sessionkey", game="STORM"
    )
    assert errors == []
    assert handoffs == [expected_handoff]
    assert written_handoffs == [expected_handoff]
    assert launch_calls == [(Path("/tmp/fake.sal"), "custom-template {sal_path}")]
    assert launched == [True]
    assert transport.closed is True


def test_select_character_selection_failure_emits_error_only():
    transport = FakeTransport(
        [
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            ("L\tABC\tSTORM", "L\tERROR\tBADCHAR"),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    errors = []
    handoffs = []
    worker.error.connect(errors.append)
    worker.handoff_ready.connect(handoffs.append)

    worker.select_character("GS3", "ABC")

    assert len(errors) == 1
    assert handoffs == []
    assert transport.closed is False


def test_select_character_launch_failure_reports_friendly_error_and_leaves_transport_open(
    monkeypatch,
):
    # Regression coverage for the launcher.py finding, 2026-09-07: a
    # missing front-end command raises FileNotFoundError from
    # subprocess.Popen - this must surface as a friendly error signal,
    # not an unhandled traceback, and must not close the EAS transport
    # (the user may just need to fix their launch command and retry).
    transport = FakeTransport(
        [
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
            (
                "L\tABC\tSTORM",
                "L\tOK\tGAMEHOST=game.example.com\tGAMEPORT=1234\tKEY=sessionkey\tGAME=STORM",
            ),
        ]
    )
    worker = LoginWorker(EASClient(transport))

    monkeypatch.setattr(worker_module.sal, "write_sal_file", lambda handoff: Path("/tmp/fake.sal"))

    def _raise_not_found(path, template):
        raise FileNotFoundError("rift-client")

    monkeypatch.setattr(worker_module.launcher, "launch", _raise_not_found)

    errors = []
    launched = []
    worker.error.connect(errors.append)
    worker.launched.connect(lambda: launched.append(True))

    worker.select_character("GS3", "ABC")

    assert len(errors) == 1
    assert "rift-client" in errors[0]
    assert launched == []
    assert transport.closed is False


def test_close_delegates_to_eas_client():
    transport = FakeTransport([])
    worker = LoginWorker(EASClient(transport))
    worker.close()
    assert transport.closed is True
