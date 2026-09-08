"""QThread worker owning the live game-socket connection.

All socket I/O (connect, handshake, reads, writes) happens on this own
worker thread, never the GUI thread - the own idiomatic worker-object +
moveToThread pattern of PySide6, not QThread subclassing.

A QObject moved to a QThread only processes queued slot calls (like a
GUI-thread call to send_line) while that thread is running its own Qt
event loop - but this worker needs a blocking socket read loop for the
lifetime of the connection, which would never yield control back to the
Qt dispatcher. So send_line does not rely on queued-slot delivery at all: it
just pushes onto a thread-safe queue.Queue, and the same read loop drains
it between reads (using a short socket receive timeout to wake up
periodically even when no data has arrived).
"""

from __future__ import annotations

import queue
import time

from PySide6.QtCore import QObject, Signal, Slot

from rift.client.display_filter import StreamingDisplayFilter
from rift.client.game_socket import GameSocket

# Server-side input throttling is roughly 3 inputs/sec, tier-dependent -
# sending faster gets the server to push back (confirmed by the user,
# 2026-09-07). Pace outgoing sends rather than firing them immediately.
_MIN_SEND_INTERVAL_SECONDS = 0.4
_POLL_TIMEOUT_SECONDS = 0.2


class StreamWorker(QObject):
    data_received = Signal(str)
    connection_closed = Signal()
    error = Signal(str)

    def __init__(self, game_socket: GameSocket, session_key: str):
        super().__init__()
        self._game_socket = game_socket
        self._session_key = session_key
        self._filter = StreamingDisplayFilter()
        self._outgoing: queue.Queue[str] = queue.Queue()
        self._last_send_time = 0.0
        self._stop_requested = False

    @Slot()
    def start(self) -> None:
        """Connects, performs the handshake, then reads until the
        connection closes or stop() is called. Meant to run once, right
        after the owning QThread starts (connect QThread.started to this)."""
        connected = False
        try:
            self._game_socket.connect()
            handshake_text = self._game_socket.perform_handshake(self._session_key)
            # Only from here on does connection_closed apply - a failure
            # in connect()/perform_handshake() above never reached a live
            # game session, so it is a connect-time error to display, not
            # a disconnect to act on. Confirmed as a real bug, 2026-09-07:
            # connection_closed used to fire unconditionally in the
            # finally block below, so a bad host/port made the window
            # close itself immediately after showing the error, before it
            # could be read - contradicting the intent that closing
            # should follow a genuine disconnect of a live session, not a
            # connection attempt that never succeeded.
            connected = True
            filtered = self._filter.feed(handshake_text)
            if filtered:
                self.data_received.emit(filtered)

            self._game_socket.set_timeout(_POLL_TIMEOUT_SECONDS)
            while not self._stop_requested:
                try:
                    chunk = self._game_socket.read_chunk()
                except TimeoutError:
                    chunk = None  # no data yet - connection still alive

                if chunk is None:
                    self._drain_outgoing()
                    continue
                if not chunk:
                    break  # genuine EOF - server closed the connection

                filtered = self._filter.feed(chunk)
                if filtered:
                    self.data_received.emit(filtered)
                self._drain_outgoing()
        except Exception as exc:  # worker thread - report, do not crash silently
            self.error.emit(str(exc))
        finally:
            trailing = self._filter.flush()
            if trailing:
                self.data_received.emit(trailing)
            self._game_socket.close()
            if connected:
                self.connection_closed.emit()

    def send_line(self, text: str) -> None:
        """Thread-safe: callable directly from the GUI thread. Does not
        touch the socket itself - just queues the command for the read
        loop (running on this own worker thread) to send and pace."""
        self._outgoing.put(text)

    @Slot()
    def stop(self) -> None:
        self._stop_requested = True

    def _drain_outgoing(self) -> None:
        while True:
            try:
                text = self._outgoing.get_nowait()
            except queue.Empty:
                return
            elapsed = time.monotonic() - self._last_send_time
            if elapsed < _MIN_SEND_INTERVAL_SECONDS:
                time.sleep(_MIN_SEND_INTERVAL_SECONDS - elapsed)
            self._game_socket.send_line(text)
            self._last_send_time = time.monotonic()
