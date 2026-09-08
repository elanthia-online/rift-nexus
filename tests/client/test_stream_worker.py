"""Tests for StreamWorker - the QThread worker owning the game socket.

Does not use a real QThread - start() is called synchronously in the
test thread, and plain Python callables are connected to the signals,
which works fine for PySide6 direct connections (no running event loop
needed).
"""

from rift.client.game_socket import GameSocket
from rift.client.stream_worker import StreamWorker


class FakeSocket:
    def __init__(self, recv_queue):
        self.sent: list[bytes] = []
        self._recv_queue = list(recv_queue)
        self.closed = False
        self.timeout = None

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int) -> bytes:
        if not self._recv_queue:
            return b""
        item = self._recv_queue.pop(0)
        if item is TimeoutError:
            raise TimeoutError
        return item

    def settimeout(self, seconds) -> None:
        self.timeout = seconds

    def close(self) -> None:
        self.closed = True


def _make_worker(recv_queue):
    sock = FakeSocket(recv_queue)
    game_socket = GameSocket("host", 1234, sock=sock)
    worker = StreamWorker(game_socket, "sessionkey")
    return worker, sock


def test_start_performs_handshake_sends_key_and_identification():
    worker, sock = _make_worker(
        [
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
            b"",  # EOF
        ]
    )
    worker.start()
    assert sock.sent[0] == b"sessionkey\n"
    assert sock.sent[1] == b"/FE:WRAYTH /VERSION:1.0.1.28 /P:WIN_UNKNOWN /XML\n"
    assert sock.sent.count(b"<c>\n") == 2


def test_start_emits_filtered_data_and_closes_on_eof():
    worker, sock = _make_worker(
        [
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
            b"Welcome!\n",
            b"",  # EOF
        ]
    )
    received = []
    closed = []
    worker.data_received.connect(received.append)
    worker.connection_closed.connect(lambda: closed.append(True))

    worker.start()

    assert closed == [True]
    assert any("Welcome!" in chunk for chunk in received)
    assert sock.closed is True


def test_send_line_queued_before_start_is_drained_on_a_timeout_poll():
    # A timeout tick (no data yet) must still drain any queued outgoing
    # command - this is how the worker avoids needing queued-slot
    # delivery from Qt (which would not run during the blocking read
    # loop anyway).
    worker, sock = _make_worker(
        [
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
            TimeoutError,
            b"",  # EOF
        ]
    )
    worker.send_line("look")

    worker.start()

    assert b"look\n" in sock.sent


def test_start_reports_a_connect_time_failure_without_closing():
    # Regression, confirmed live 2026-09-07 via a real launcher.py smoke
    # test against an address nothing was listening on: connection_closed
    # used to fire unconditionally in the finally block of start(), so a
    # failed connect/handshake made the window close itself immediately
    # after showing the error - before it could even be read. A failure
    # here never reached a live game session, so it must surface only as
    # an error, leaving the window open for the user to see it.
    class BrokenSocket(FakeSocket):
        def sendall(self, data: bytes) -> None:
            raise OSError("Broken pipe")

    sock = BrokenSocket([])
    game_socket = GameSocket("host", 1234, sock=sock)
    worker = StreamWorker(game_socket, "sessionkey")

    errors = []
    closed = []
    worker.error.connect(errors.append)
    worker.connection_closed.connect(lambda: closed.append(True))

    worker.start()

    assert len(errors) == 1
    assert "Broken pipe" in errors[0]
    assert closed == []  # never reached a live session, so nothing to "close"


def test_start_still_closes_on_a_failure_after_a_successful_handshake():
    # The other half of the regression above: once the handshake has
    # actually completed (a live session exists), a later failure - here,
    # the read loop blowing up - is a genuine disconnect and must still
    # emit connection_closed.
    class DiesAfterHandshakeSocket(FakeSocket):
        def recv(self, bufsize: int) -> bytes:
            if self._recv_queue:
                return super().recv(bufsize)
            raise OSError("Connection reset")

    sock = DiesAfterHandshakeSocket(
        [
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GS4"/>',
            b'<mode id="GAME"/>',
        ]
    )
    game_socket = GameSocket("host", 1234, sock=sock)
    worker = StreamWorker(game_socket, "sessionkey")

    errors = []
    closed = []
    worker.error.connect(errors.append)
    worker.connection_closed.connect(lambda: closed.append(True))

    worker.start()

    assert len(errors) == 1
    assert "Connection reset" in errors[0]
    assert closed == [True]


def test_stop_before_start_skips_the_read_loop_entirely():
    class InfiniteTimeoutSocket(FakeSocket):
        def recv(self, bufsize: int) -> bytes:
            raise TimeoutError

    sock = InfiniteTimeoutSocket([])
    game_socket = GameSocket("host", 1234, sock=sock)
    game_socket.perform_handshake = lambda session_key: ""  # noqa: SLF001 - test seam
    worker = StreamWorker(game_socket, "sessionkey")

    worker.stop()  # request stop before the main loop is ever entered
    worker.start()  # would loop forever on TimeoutError if _stop_requested were ignored

    assert sock.closed is True
