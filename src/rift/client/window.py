"""PySide6 raw-stream client window - the minimal UI for client v1.

Read-only scrollback pane for incoming (filtered) game text, plus a
single-line input box; Enter sends. All socket I/O happens on a
StreamWorker moved to its own QThread - this window only ever touches
Qt widgets and the thread-safe send_line()/stop() methods on that worker.
"""

from __future__ import annotations

from PySide6.QtCore import QThread
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QLineEdit, QMainWindow, QPlainTextEdit, QVBoxLayout, QWidget

from rift.client.stream_worker import StreamWorker

_MAX_SCROLLBACK_BLOCKS = 10000


class ClientWindow(QMainWindow):
    def __init__(self, worker: StreamWorker):
        super().__init__()
        self.setWindowTitle("rift-nexus client")
        self.resize(900, 700)

        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(_MAX_SCROLLBACK_BLOCKS)
        self._input = QLineEdit()
        self._input.returnPressed.connect(self._on_return_pressed)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._output)
        layout.addWidget(self._input)
        self.setCentralWidget(central)
        self._input.setFocus()

        self._worker = worker
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.data_received.connect(self._append_output)
        self._worker.error.connect(self._on_error)
        self._worker.connection_closed.connect(self._on_connection_closed)
        self._thread.start()

    def _on_return_pressed(self) -> None:
        text = self._input.text()
        self._input.clear()
        if text:
            # Echoed into the same output pane as the responses coming
            # from the game (rather than only existing in the input box,
            # which clears immediately) so the visible transcript reads
            # as command/response pairs - important for diagnosing cause
            # and effect later, per the user, 2026-09-07. The "> " prompt
            # sent by the game is squelched by display_filter, so this
            # locally-echoed line is the only prompt-like marker shown.
            self._append_output(f"> {text}\n")
            self._worker.send_line(text)

    def _append_output(self, text: str) -> None:
        if not text:
            return
        cursor = self._output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._output.setTextCursor(cursor)
        self._output.ensureCursorVisible()

    def _on_error(self, message: str) -> None:
        self._append_output(f"\n[error] {message}\n")

    def _on_connection_closed(self) -> None:
        # Trigger is the actual disconnect (whatever caused it - exit,
        # server kick, dropped connection), not "did the player type
        # exit" - per the user 2026-09-07, correcting an earlier version
        # of this method that special-cased the "exit" command text.
        self._append_output("\n[connection closed]\n")
        self._finalize()
        self.close()

    def _finalize(self) -> None:
        """Extension point for anything that needs to happen before the
        window actually closes - flushing logs, persisting settings, etc.
        No-op placeholder for now (client v1 has neither yet); exists so
        future additions have an obvious, single place to slot into,
        per the user 2026-09-07."""

    def closeEvent(self, event) -> None:
        self._worker.stop()
        self._thread.quit()
        self._thread.wait(2000)
        super().closeEvent(event)
