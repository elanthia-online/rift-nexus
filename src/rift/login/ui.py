"""PySide6 LoginWindow - account/password, character selection, launch.

Talks only to the signals/slots of LoginWorker, never to EASClient
directly - worker-object + moveToThread pattern (not QThread
subclassing), matching client/window.py. Unlike client/window.py, the
worker here has no blocking loop of its own, so outgoing actions are
dispatched through ordinary Qt signals (login_requested,
character_launch_requested) connected to the slots on that worker,
rather than called as plain thread-safe methods - the own
queued-connection delivery of Qt does the cross-thread dispatch
correctly since nothing on the worker thread blocks it.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rift.login import config, credentials
from rift.login.models import CharacterListing, HandoffInfo
from rift.login.worker import LoginWorker


class LoginWindow(QMainWindow):
    login_requested = Signal(str, str)
    character_launch_requested = Signal(str, str, str)

    def __init__(self, worker: LoginWorker):
        super().__init__()
        self.setWindowTitle("rift-nexus login")
        self.resize(420, 480)

        self._config = config.load()

        self._account_input = QLineEdit(self._config.account_name)
        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._remember_checkbox = QCheckBox("Remember me")

        saved_password = None
        if self._config.account_name:
            saved_password = credentials.load_password(self._config.account_name)
        if saved_password is not None:
            self._password_input.setText(saved_password)
            self._remember_checkbox.setChecked(True)

        self._login_button = QPushButton("Log In")
        self._login_button.clicked.connect(self._on_login_clicked)
        self._password_input.returnPressed.connect(self._on_login_clicked)

        self._character_list = QListWidget()
        self._character_list.itemSelectionChanged.connect(self._on_selection_changed)

        self._launch_button = QPushButton("Launch")
        self._launch_button.setEnabled(False)
        self._launch_button.clicked.connect(self._on_launch_clicked)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)

        account_row = QHBoxLayout()
        account_row.addWidget(QLabel("Account:"))
        account_row.addWidget(self._account_input)

        password_row = QHBoxLayout()
        password_row.addWidget(QLabel("Password:"))
        password_row.addWidget(self._password_input)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(account_row)
        layout.addLayout(password_row)
        layout.addWidget(self._remember_checkbox)
        layout.addWidget(self._login_button)
        layout.addWidget(self._character_list)
        layout.addWidget(self._launch_button)
        layout.addWidget(self._status_label)
        self.setCentralWidget(central)
        self._account_input.setFocus()

        self._worker = worker
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self.login_requested.connect(self._worker.login)
        self.character_launch_requested.connect(self._worker.select_character)
        self._worker.authenticated.connect(self._on_authenticated)
        self._worker.auth_failed.connect(self._on_auth_failed)
        self._worker.characters_ready.connect(self._on_characters_ready)
        self._worker.handoff_ready.connect(self._on_handoff_ready)
        self._worker.launched.connect(self._on_launched)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def _on_login_clicked(self) -> None:
        account = self._account_input.text().strip()
        password = self._password_input.text()
        if not account or not password:
            self._status_label.setText("Account and password are both required.")
            return
        self._set_login_controls_enabled(False)
        self._character_list.clear()
        self._launch_button.setEnabled(False)
        self._status_label.setText("Connecting...")
        self.login_requested.emit(account, password)

    def _on_authenticated(self) -> None:
        account = self._account_input.text().strip()
        self._config.account_name = account
        config.save(self._config)
        if self._remember_checkbox.isChecked():
            credentials.save_password(account, self._password_input.text())
        else:
            credentials.delete_password(account)
        self._status_label.setText("Authenticated. Loading characters...")

    def _on_auth_failed(self, message: str) -> None:
        self._set_login_controls_enabled(True)
        self._status_label.setText(message)

    def _on_characters_ready(self, characters: list[CharacterListing]) -> None:
        self._character_list.clear()
        for listing in characters:
            item = QListWidgetItem(f"{listing.game_name} - {listing.char_name}")
            item.setData(Qt.ItemDataRole.UserRole, (listing.game_code, listing.char_code))
            self._character_list.addItem(item)
        if not characters:
            self._status_label.setText("No characters found on this account for a supported game.")
            return
        self._status_label.setText("Select a character to launch.")

    def _on_selection_changed(self) -> None:
        self._launch_button.setEnabled(bool(self._character_list.selectedItems()))

    def _on_launch_clicked(self) -> None:
        selected = self._character_list.selectedItems()
        if not selected:
            return
        game_code, char_code = selected[0].data(Qt.ItemDataRole.UserRole)
        self._launch_button.setEnabled(False)
        self._status_label.setText("Selecting character...")
        self.character_launch_requested.emit(game_code, char_code, self._config.launch_command_template)

    def _on_handoff_ready(self, handoff: HandoffInfo) -> None:
        selected = self._character_list.selectedItems()
        if selected:
            game_code, char_code = selected[0].data(Qt.ItemDataRole.UserRole)
            self._config.last_game_code = game_code
            self._config.last_char_code = char_code
            config.save(self._config)
        self._status_label.setText(f"Launching {handoff.game}...")

    def _on_launched(self) -> None:
        self._status_label.setText("Launched.")
        self.close()

    def _on_error(self, message: str) -> None:
        self._set_login_controls_enabled(True)
        self._launch_button.setEnabled(bool(self._character_list.selectedItems()))
        self._status_label.setText(message)

    def _set_login_controls_enabled(self, enabled: bool) -> None:
        self._account_input.setEnabled(enabled)
        self._password_input.setEnabled(enabled)
        self._remember_checkbox.setEnabled(enabled)
        self._login_button.setEnabled(enabled)

    def closeEvent(self, event) -> None:
        self._worker.close()
        self._thread.quit()
        self._thread.wait(2000)
        super().closeEvent(event)
