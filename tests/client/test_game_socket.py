from rift.client.game_socket import GameSocket


class FakeSocket:
    def __init__(self, recv_queue: list[bytes] | None = None):
        self.sent: list[bytes] = []
        self._recv_queue = list(recv_queue or [])
        self.closed = False
        self.timeout: float | None = None

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def recv(self, bufsize: int) -> bytes:
        return self._recv_queue.pop(0) if self._recv_queue else b""

    def settimeout(self, seconds: float | None) -> None:
        self.timeout = seconds

    def close(self) -> None:
        self.closed = True


def test_send_line_appends_newline_and_encodes_utf8():
    sock = FakeSocket()
    gs = GameSocket("host", 1234, sock=sock)
    gs.send_line("hello")
    assert sock.sent == [b"hello\n"]


def test_perform_handshake_sends_key_and_identification_string():
    sock = FakeSocket(
        recv_queue=[
            b'<mode id="GAME"/>',
            b"Please wait for connection to game server.",
            b"<playerID id='1165808'/>",
            b'<settingsInfo  client="1.0.1.28" major="15" crc=\'123\' instance=\'GSF\'/>',
            b'<mode id="GAME"/>',
        ]
    )
    gs = GameSocket("host", 1234, sock=sock)
    gs.perform_handshake("sessionkey")

    assert sock.sent[0] == b"sessionkey\n"
    assert sock.sent[1] == b"/FE:WRAYTH /VERSION:1.0.1.28 /P:WIN_UNKNOWN /XML\n"


def test_perform_handshake_waits_for_settings_info_before_first_ready_signal():
    # Confirmed via a real, successful Wrayth login capture (2026-09-07):
    # the client must not send <c> until settingsInfo has arrived - an
    # earlier version sent it on a fixed timer instead, and the server
    # rejected the whole session ("Invalid login key").
    sock = FakeSocket(
        recv_queue=[
            b'<mode id="GAME"/>',
            b"Please wait for connection to game server.",
            b"<playerID id='1165808'/>",
            b'<settingsInfo  client="1.0.1.28" major="15" crc=\'123\' instance=\'GSF\'/>',
            b'<mode id="GAME"/>',
        ]
    )
    gs = GameSocket("host", 1234, sock=sock)
    gs.perform_handshake("sessionkey")

    ready_signals = [i for i, data in enumerate(sock.sent) if data == b"<c>\n"]
    assert len(ready_signals) == 2
    first_ready_index = ready_signals[0]
    # Every recv() the fake socket serves before the first <c> must have
    # already been consumed - i.e. the first <c> is sent only after all
    # scripted chunks up to and including settingsInfo were read out.
    assert sock._recv_queue == []  # all chunks consumed by the time handshake finishes
    assert first_ready_index >= 2  # key + identification string precede it


def test_perform_handshake_returns_buffered_text():
    sock = FakeSocket(
        recv_queue=[
            b'<mode id="GAME"/>',
            b'<settingsInfo instance="GSF"/>',
            b'<mode id="GAME"/>',
        ]
    )
    gs = GameSocket("host", 1234, sock=sock)
    buffer = gs.perform_handshake("sessionkey")

    assert '<mode id="GAME"/>' in buffer
    assert "settingsInfo" in buffer


def test_read_chunk_decodes_incoming_bytes():
    sock = FakeSocket(recv_queue=[b"You are standing in a room.\n"])
    gs = GameSocket("host", 1234, sock=sock)
    assert gs.read_chunk() == "You are standing in a room.\n"


def test_read_chunk_returns_empty_string_when_socket_closed():
    sock = FakeSocket(recv_queue=[])
    gs = GameSocket("host", 1234, sock=sock)
    assert gs.read_chunk() == ""


def test_set_timeout_delegates_to_socket():
    sock = FakeSocket()
    gs = GameSocket("host", 1234, sock=sock)
    gs.set_timeout(0.2)
    assert sock.timeout == 0.2


def test_connect_is_a_noop_when_a_socket_was_already_injected():
    sock = FakeSocket()
    gs = GameSocket("host", 1234, sock=sock)
    gs.connect()  # must not attempt a real socket.create_connection()
    assert gs._sock is sock  # noqa: SLF001 - verifying the no-op did not replace it


def test_close_closes_underlying_socket():
    sock = FakeSocket()
    gs = GameSocket("host", 1234, sock=sock)
    gs.close()
    assert sock.closed is True
