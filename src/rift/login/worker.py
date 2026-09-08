"""QThread worker wrapping the EASClient login flow behind signals/slots.

Worker-object + moveToThread pattern (not QThread subclassing), matching
client/stream_worker.py - keeps the roughly eight network round trips of
the EAS handshake off the GUI thread. Unlike stream_worker.py, there is
no persistent blocking read loop here: each slot is a short, finite
sequence of round trips triggered by a single user action (log in, then
select a character to launch), so ordinary queued Qt slot delivery works
fine - none of the queue.Queue workaround stream_worker.py needs is
required here.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot

from rift.login import launcher, sal
from rift.login.eas_client import EASClient
from rift.login.eas_wire import EASAuthenticationError

log = logging.getLogger(__name__)


class LoginWorker(QObject):
    authenticated = Signal()
    auth_failed = Signal(str)
    characters_ready = Signal(object)  # list[CharacterListing]
    handoff_ready = Signal(object)  # HandoffInfo
    launched = Signal()
    error = Signal(str)

    def __init__(self, eas_client: EASClient):
        super().__init__()
        self._eas_client = eas_client

    @Slot(str, str)
    def login(self, account: str, password: str) -> None:
        """Connects, authenticates, and enumerates every character on the
        account. Emits authenticated then characters_ready on success,
        auth_failed for a rejected account/password, or error for
        anything else (connection/protocol failures)."""
        try:
            self._eas_client.connect()
            self._eas_client.authenticate(account, password)
            self.authenticated.emit()
            characters = self._eas_client.enumerate_all()
        except EASAuthenticationError as exc:
            self.auth_failed.emit(str(exc))
            return
        except Exception as exc:  # worker thread - report, do not crash silently
            self.error.emit(str(exc))
            return
        self.characters_ready.emit(characters)

    @Slot(str, str, str)
    def select_character(
        self, game_code: str, char_code: str, launch_command_template: str = ""
    ) -> None:
        """Selects a character, writes its handoff to a SAL file, and
        launches the configured front-end (rift-client by default) against
        it. Emits handoff_ready then launched on success, or error for a
        rejected selection, a launch failure (e.g. the configured command
        not found), or anything else. The EAS connection is closed once
        the front-end has launched - the login program has no further job
        at that point, see docs/decisions.md on the no-proxy-in-v1
        decision."""
        try:
            handoff = self._eas_client.select_character(game_code, char_code)
        except Exception as exc:  # worker thread - report, do not crash silently
            self.error.emit(str(exc))
            return
        self.handoff_ready.emit(handoff)

        try:
            sal_path = sal.write_sal_file(handoff)
            launcher.launch(sal_path, launch_command_template)
        except FileNotFoundError as exc:
            self.error.emit(f"Could not find the configured front-end command: {exc}")
            return
        except Exception as exc:  # worker thread - report, do not crash silently
            self.error.emit(str(exc))
            return

        log.info("Launched front-end for character %s (%s)", char_code, game_code)
        self.launched.emit()
        self._eas_client.close()

    def close(self) -> None:
        self._eas_client.close()
