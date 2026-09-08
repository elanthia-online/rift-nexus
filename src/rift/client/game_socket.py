"""Plain TCP connection to the game server (GAMEHOST:GAMEPORT).

Confirmed live 2026-09-07: unlike the EAS connection (which requires
TLS), this connection is genuinely unencrypted - a TLS handshake attempt
against it fails immediately with SSL_ERROR_WRONG_VERSION_NUMBER, and a
plain-TCP connect + handshake receives an immediate response
(`<mode id="GAME"/>`) with no STARTTLS-style upgrade invitation anywhere
in the exchange. This corrects an earlier assumption (based on the EAS
migration and general "insecure ports are being retired" guidance) that
this connection would also require TLS - it does not, at least not yet.

The handshake is a real request/response exchange, not two blindly-timed
sends - confirmed via a packet capture of a genuine, successful Wrayth
login (2026-09-07). After the identification string, the server sends
`<mode id="GAME"/>`, "Please wait for connection to game server.",
`<playerID .../>`, and `<settingsInfo .../>` - only then does the client
send its first `<c>`. The server then sends a *second*
`<mode id="GAME"/>`, and only then does the client send the second `<c>`;
the welcome banner does not arrive until after that. Blindly sending both
`<c>` signals on a fixed timer (an earlier version of this module) never
got past the first `<mode id="GAME"/>` and the server rejected the
session with "Invalid login key. Please relogin to the web site." - a
generic protocol-desync error, not a literal statement that the key
string itself was malformed. The identification string itself must be
`/FE:WRAYTH /VERSION:1.0.1.28 /P:WIN_UNKNOWN /XML` (confirmed from the
same capture) - "WIN_UNKNOWN" is a fixed literal real clients send
regardless of host OS, not a real platform report.
"""

from __future__ import annotations

import socket
from typing import Callable, Protocol

_RECV_CHUNK = 4096
_IDENTIFICATION_STRING = "/FE:WRAYTH /VERSION:1.0.1.28 /P:WIN_UNKNOWN /XML"
_CLIENT_READY_SIGNAL = "<c>"
_SETTINGS_INFO_MARKER = "settingsInfo"
_MODE_TAG_MARKER = "<mode"


class _SocketLike(Protocol):
    def sendall(self, data: bytes) -> None: ...
    def recv(self, bufsize: int) -> bytes: ...
    def settimeout(self, seconds: float | None) -> None: ...
    def close(self) -> None: ...


class GameSocket:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        sock: _SocketLike | None = None,
    ):
        self._host = host
        self._port = port
        self._sock = sock  # injectable for tests; connect() sets it for real use

    def connect(self) -> None:
        if self._sock is None:  # no-op if a test already injected a fake socket
            self._sock = socket.create_connection((self._host, self._port))

    def set_timeout(self, seconds: float | None) -> None:
        assert self._sock is not None, "not connected"
        self._sock.settimeout(seconds)

    def perform_handshake(self, session_key: str) -> str:
        """Returns the raw text read during the handshake (the initial
        mode/playerID/settingsInfo/mode burst) so callers do not lose it."""
        self.send_line(session_key)
        self.send_line(_IDENTIFICATION_STRING)

        buffer = self._read_until(lambda text: _SETTINGS_INFO_MARKER in text)
        self.send_line(_CLIENT_READY_SIGNAL)

        buffer += self._read_until(lambda text: _MODE_TAG_MARKER in text)
        self.send_line(_CLIENT_READY_SIGNAL)

        return buffer

    def _read_until(self, is_done: Callable[[str], bool]) -> str:
        accumulated = ""
        while not is_done(accumulated):
            chunk = self.read_chunk()
            if not chunk:
                break
            accumulated += chunk
        return accumulated

    def send_line(self, text: str) -> None:
        assert self._sock is not None, "not connected"
        self._sock.sendall((text + "\n").encode("utf-8"))

    def read_chunk(self) -> str:
        assert self._sock is not None, "not connected"
        chunk = self._sock.recv(_RECV_CHUNK)
        return chunk.decode("utf-8", errors="replace")

    def close(self) -> None:
        if self._sock is not None:
            self._sock.close()
            self._sock = None
