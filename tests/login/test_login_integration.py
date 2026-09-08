"""Integration check: the real LoginWorker and LoginWindow wired together
over an actual QThread.

test_worker.py exercises LoginWorker's slots directly and synchronously
(no thread, no window); test_ui.py exercises LoginWindow against a fake
worker double (no thread, no real EASClient). Neither confirms the two
real classes actually agree on signal/slot signatures once genuinely
crossing threads via Qt's queued-connection dispatch - a mismatch there
(e.g. a Slot() decorator with the wrong argument count or type) would
only surface at real runtime, not in either of those narrower tests.
This is the one place that checks the real wiring end to end, against a
scripted fake Transport (same pattern as test_eas_client.py/test_worker.py)
so no live network is needed.
"""

import rift.login.config as config_module
import rift.login.credentials as credentials_module
from rift.login.config import LoginConfig
from rift.login.eas_client import EASClient
from rift.login.eas_wire import obscure_password
from rift.login.ui import LoginWindow
from rift.login.worker import LoginWorker


class FakeTransport:
    def __init__(self, script: list[tuple[str, str]]):
        self._script = list(script)
        self.sent_lines: list[str] = []

    def connect(self) -> None:
        pass

    def send_line(self, line: str) -> None:
        self.sent_lines.append(line)

    def recv_packet(self) -> str:
        expected_line, response = self._script.pop(0)
        assert self.sent_lines[-1] == expected_line
        return response

    def close(self) -> None:
        pass


def test_real_worker_and_window_wired_over_a_real_qthread(qtbot, monkeypatch):
    monkeypatch.setattr(config_module, "load", lambda: LoginConfig())
    monkeypatch.setattr(config_module, "save", lambda cfg: None)
    monkeypatch.setattr(credentials_module, "load_password", lambda account: None)
    monkeypatch.setattr(credentials_module, "save_password", lambda a, p: None)
    monkeypatch.setattr(credentials_module, "delete_password", lambda a: None)

    scrambled = obscure_password("pw", "HASHKEY")
    transport = FakeTransport(
        [
            ("K", "K\tHASHKEY"),
            ("A\tacct\t" + scrambled, "A\tKEY\teassessionkey"),
            ("M", "M\tGS3\tGS Prime"),
            ("N\tGS3", "N\tSTORM"),
            ("F\tGS3", "F\tNORMAL"),
            ("G\tGS3", "G\tOK"),
            ("P\tGS3", "P\tOK"),
            ("C", "C\t1\t2\t3\t4\tABC\tWarrior"),
        ]
    )
    worker = LoginWorker(EASClient(transport))
    window = LoginWindow(worker)
    qtbot.addWidget(window)

    window.login_requested.emit("acct", "pw")

    qtbot.waitUntil(lambda: window._character_list.count() == 1, timeout=2000)
    assert window._character_list.item(0).text() == "GS Prime - Warrior"

    window.close()
