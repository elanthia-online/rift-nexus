"""Tests for LoginWindow - the PySide6 account/character-selection UI.

Uses a minimal FakeLoginWorker double (a real QObject with the same
signal/slot shape as LoginWorker) rather than a real LoginWorker, since
the orchestration in LoginWorker is already covered by test_worker.py -
this module tests only how LoginWindow reacts to and drives those
signals/slots. config.py/credentials.py are monkeypatched, since they
already have their own dedicated test suites and must never touch a real
file or OS keyring in tests. Run with QT_QPA_PLATFORM=offscreen in
headless environments.
"""

from PySide6.QtCore import QObject, Signal

import rift.login.config as config_module
import rift.login.credentials as credentials_module
from rift.login.config import LoginConfig
from rift.login.models import CharacterListing, HandoffInfo
from rift.login.ui import LoginWindow


class FakeLoginWorker(QObject):
    authenticated = Signal()
    auth_failed = Signal(str)
    characters_ready = Signal(object)
    handoff_ready = Signal(object)
    launched = Signal()
    error = Signal(str)

    def __init__(self):
        super().__init__()
        self.login_calls: list[tuple[str, str]] = []
        self.select_character_calls: list[tuple[str, str, str]] = []
        self.closed = False

    def login(self, account: str, password: str) -> None:
        self.login_calls.append((account, password))

    def select_character(self, game_code: str, char_code: str, launch_command_template: str = "") -> None:
        self.select_character_calls.append((game_code, char_code, launch_command_template))

    def close(self) -> None:
        self.closed = True


def _patch_config_and_credentials(monkeypatch, cfg=None, saved_password=None):
    cfg = cfg or LoginConfig()
    saved_configs = []
    saved_passwords = []
    deleted_accounts = []
    monkeypatch.setattr(config_module, "load", lambda: cfg)
    monkeypatch.setattr(config_module, "save", saved_configs.append)
    monkeypatch.setattr(credentials_module, "load_password", lambda account: saved_password)
    monkeypatch.setattr(credentials_module, "save_password", lambda a, p: saved_passwords.append((a, p)))
    monkeypatch.setattr(credentials_module, "delete_password", deleted_accounts.append)
    return cfg, saved_configs, saved_passwords, deleted_accounts


def _make_window(qtbot, monkeypatch, cfg=None, saved_password=None):
    cfg, saved_configs, saved_passwords, deleted_accounts = _patch_config_and_credentials(
        monkeypatch, cfg, saved_password
    )
    worker = FakeLoginWorker()
    window = LoginWindow(worker)
    qtbot.addWidget(window)
    return window, worker, cfg, saved_configs, saved_passwords, deleted_accounts


def test_prefills_account_from_config(qtbot, monkeypatch):
    window, worker, cfg, *_ = _make_window(
        qtbot, monkeypatch, cfg=LoginConfig(account_name="mirascible")
    )
    assert window._account_input.text() == "mirascible"
    window.close()


def test_prefills_password_and_checks_remember_me_when_a_password_is_saved(qtbot, monkeypatch):
    window, worker, *_ = _make_window(
        qtbot, monkeypatch, cfg=LoginConfig(account_name="mirascible"), saved_password="hunter2"
    )
    assert window._password_input.text() == "hunter2"
    assert window._remember_checkbox.isChecked() is True
    window.close()


def test_login_click_emits_to_worker_and_disables_controls(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    window._account_input.setText("mirascible")
    window._password_input.setText("hunter2")

    window._login_button.click()

    qtbot.waitUntil(lambda: worker.login_calls == [("mirascible", "hunter2")], timeout=2000)
    assert window._account_input.isEnabled() is False
    assert window._login_button.isEnabled() is False
    window.close()


def test_login_click_without_account_or_password_does_not_call_worker(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    window._account_input.setText("mirascible")
    window._password_input.setText("")

    window._login_button.click()

    assert worker.login_calls == []
    assert "required" in window._status_label.text().lower()
    window.close()


def test_authenticated_saves_account_and_remembers_password_when_checked(qtbot, monkeypatch):
    window, worker, cfg, saved_configs, saved_passwords, deleted_accounts = _make_window(
        qtbot, monkeypatch
    )
    window._account_input.setText("mirascible")
    window._password_input.setText("hunter2")
    window._remember_checkbox.setChecked(True)

    worker.authenticated.emit()

    assert cfg.account_name == "mirascible"
    assert saved_configs == [cfg]
    assert saved_passwords == [("mirascible", "hunter2")]
    assert deleted_accounts == []
    window.close()


def test_authenticated_deletes_saved_password_when_remember_unchecked(qtbot, monkeypatch):
    window, worker, cfg, saved_configs, saved_passwords, deleted_accounts = _make_window(
        qtbot, monkeypatch
    )
    window._account_input.setText("mirascible")
    window._password_input.setText("hunter2")
    window._remember_checkbox.setChecked(False)

    worker.authenticated.emit()

    assert saved_passwords == []
    assert deleted_accounts == ["mirascible"]
    window.close()


def test_characters_ready_populates_list(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    characters = [
        CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior"),
        CharacterListing(game_code="GS3", game_name="GS Prime", char_code="XYZ", char_name="Historian"),
    ]

    worker.characters_ready.emit(characters)

    assert window._character_list.count() == 2
    assert window._character_list.item(0).text() == "GS Prime - Warrior"
    assert window._launch_button.isEnabled() is False
    window.close()


def test_selecting_a_character_enables_launch_button(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    worker.characters_ready.emit(
        [CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior")]
    )

    window._character_list.setCurrentRow(0)

    assert window._launch_button.isEnabled() is True
    window.close()


def test_launch_click_emits_to_worker_with_configured_template(qtbot, monkeypatch):
    window, worker, *_ = _make_window(
        qtbot, monkeypatch, cfg=LoginConfig(launch_command_template="/opt/Wizard/wizard {sal_path}")
    )
    worker.characters_ready.emit(
        [CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior")]
    )
    window._character_list.setCurrentRow(0)

    window._launch_button.click()

    qtbot.waitUntil(
        lambda: worker.select_character_calls
        == [("GS3", "ABC", "/opt/Wizard/wizard {sal_path}")],
        timeout=2000,
    )
    window.close()


def test_handoff_ready_saves_last_game_and_character_code(qtbot, monkeypatch):
    window, worker, cfg, saved_configs, *_ = _make_window(qtbot, monkeypatch)
    worker.characters_ready.emit(
        [CharacterListing(game_code="GS3", game_name="GS Prime", char_code="ABC", char_name="Warrior")]
    )
    window._character_list.setCurrentRow(0)

    worker.handoff_ready.emit(
        HandoffInfo(gamehost="game.example.com", gameport="1234", key="k", game="STORM")
    )

    assert cfg.last_game_code == "GS3"
    assert cfg.last_char_code == "ABC"
    assert saved_configs == [cfg]
    window.close()


def test_launched_closes_the_window(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    window.show()

    worker.launched.emit()

    assert window.isVisible() is False


def test_auth_failed_reenables_login_controls_and_shows_message(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)
    window._account_input.setText("mirascible")
    window._password_input.setText("wrong")
    window._login_button.click()
    qtbot.waitUntil(lambda: bool(worker.login_calls), timeout=2000)

    worker.auth_failed.emit("Incorrect account password.")

    assert window._login_button.isEnabled() is True
    assert window._account_input.isEnabled() is True
    assert window._status_label.text() == "Incorrect account password."
    window.close()


def test_error_reenables_login_controls_and_preserves_launch_state(qtbot, monkeypatch):
    window, worker, *_ = _make_window(qtbot, monkeypatch)

    worker.error.emit("Connection refused")

    assert window._login_button.isEnabled() is True
    assert window._launch_button.isEnabled() is False
    assert window._status_label.text() == "Connection refused"
    window.close()
