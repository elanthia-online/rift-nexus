"""Tests for ClientWindow - the PySide6 raw-stream client UI.

Uses the qtbot fixture from pytest-qt (provides a QApplication and can
wait for Qt signals crossing from the real QThread of the worker back to
the GUI thread). Run with QT_QPA_PLATFORM=offscreen in headless
environments.
"""

from rift.client.game_socket import GameSocket
from rift.client.stream_worker import StreamWorker
from rift.client.window import ClientWindow


class FakeSocket:
    def __init__(self, recv_queue):
        self.sent: list[bytes] = []
        self._recv_queue = list(recv_queue)
        self.closed = False
        self.timeout = None

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int) -> bytes:
        return self._recv_queue.pop(0) if self._recv_queue else b""

    def settimeout(self, seconds) -> None:
        self.timeout = seconds

    def close(self) -> None:
        self.closed = True


class StaysOpenSocket(FakeSocket):
    """Like FakeSocket, but raises TimeoutError once its queue is
    exhausted instead of signaling EOF - for tests that need the
    connection to stay open (e.g. to send a command after the handshake)."""

    def recv(self, bufsize: int) -> bytes:
        if not self._recv_queue:
            raise TimeoutError
        return self._recv_queue.pop(0)


class DisconnectsAfterCommandSocket(FakeSocket):
    """Stays open (TimeoutError) through the handshake, then reports EOF
    once any player command is sent - simulating a disconnect. Does not
    care what the command was (exit or otherwise): the reaction of the
    window should be driven by the disconnect itself, not by matching
    command text."""

    def recv(self, bufsize: int) -> bytes:
        if self._recv_queue:
            return self._recv_queue.pop(0)
        if len(self.sent) > 4:  # handshake = key + identification + two <c>
            return b""
        raise TimeoutError


def _make_window(qtbot, recv_queue, socket_cls=FakeSocket):
    sock = socket_cls(recv_queue)
    game_socket = GameSocket("host", 1234, sock=sock)
    worker = StreamWorker(game_socket, "sessionkey")
    window = ClientWindow(worker)
    qtbot.addWidget(window)
    return window, worker, sock


def test_window_shows_incoming_data_and_closes_on_disconnect(qtbot):
    window, worker, sock = _make_window(
        qtbot,
        [
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
            b"Welcome!\n",
            b"",  # EOF
        ],
    )
    window.show()

    qtbot.waitUntil(lambda: "Welcome!" in window._output.toPlainText(), timeout=2000)
    # connection_closed crosses threads via a queued connection - waiting
    # on the signal itself does not guarantee the GUI-thread slot (which
    # closes the window) has actually run yet, so poll for the real effect.
    qtbot.waitUntil(lambda: window.isVisible() is False, timeout=2000)


def test_return_pressed_sends_input_and_clears_the_line_edit(qtbot):
    window, worker, sock = _make_window(
        qtbot,
        [
            b'<mode id="GAME"/><settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
        ],
        socket_cls=StaysOpenSocket,
    )

    def handshake_done():
        return len(sock.sent) >= 4  # key, identification, two <c> sends

    qtbot.waitUntil(handshake_done, timeout=2000)

    window._input.setText("look")
    window._input.returnPressed.emit()

    qtbot.waitUntil(lambda: b"look\n" in sock.sent, timeout=2000)
    assert window._input.text() == ""

    window.close()


def test_return_pressed_echoes_the_command_into_the_output_pane(qtbot):
    # The "> " prompt sent by the game is squelched by display_filter, so
    # the transcript needs its own command/response markers for later
    # cause-and-effect diagnosis - per the user, 2026-09-07.
    window, worker, sock = _make_window(
        qtbot,
        [
            b'<mode id="GAME"/><settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
        ],
        socket_cls=StaysOpenSocket,
    )

    qtbot.waitUntil(lambda: len(sock.sent) >= 4, timeout=2000)

    window._input.setText("look")
    window._input.returnPressed.emit()

    assert "> look" in window._output.toPlainText()

    window.close()

    window.close()


def test_window_closes_after_disconnect_following_any_command_not_just_exit(qtbot):
    # Regression: an earlier version special-cased the literal "exit"
    # command text to decide whether to auto-close. Corrected per the
    # user 2026-09-07 - the trigger must be the actual disconnect, so a
    # server-initiated close after *any* command (not just "exit") should
    # close the window the same way.
    window, worker, sock = _make_window(
        qtbot,
        [
            b'<mode id="GAME"/><settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
        ],
        socket_cls=DisconnectsAfterCommandSocket,
    )
    window.show()

    def handshake_done():
        return len(sock.sent) >= 4

    qtbot.waitUntil(handshake_done, timeout=2000)
    assert window.isVisible() is True

    window._input.setText("look")  # deliberately not "exit"
    window._input.returnPressed.emit()

    qtbot.waitUntil(lambda: window.isVisible() is False, timeout=2000)
