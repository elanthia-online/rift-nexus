"""EAS client orchestrating the authentication + character-selection handshake.

Depends only on tls_transport.Transport, not on TLSTransport directly, so
the full sequencing can be tested offline against a fake transport.
"""

from __future__ import annotations

from rift.login import eas_wire
from rift.login.models import CharacterListing, GameListing, HandoffInfo
from rift.login.tls_transport import Transport


class EASClient:
    def __init__(self, transport: Transport):
        self._transport = transport
        self._eas_session_key: str | None = None

    def connect(self) -> None:
        self._transport.connect()

    def authenticate(self, account: str, password: str) -> None:
        self._transport.send_line(eas_wire.build_k_line())
        hash_key = eas_wire.parse_hash_key(self._transport.recv_packet())
        scrambled = eas_wire.obscure_password(password, hash_key)
        self._transport.send_line(eas_wire.build_a_line(account, scrambled))
        self._eas_session_key = eas_wire.parse_key_response(self._transport.recv_packet())

    def list_games(self) -> list[GameListing]:
        self._transport.send_line(eas_wire.build_m_line())
        response = self._transport.recv_packet()
        return [GameListing(code, name) for code, name in eas_wire.parse_game_list(response)]

    def _characters_for_game(self, game_code: str) -> list[tuple[str, str]]:
        self._transport.send_line(eas_wire.build_f_line(game_code))
        eas_wire.parse_subscription(self._transport.recv_packet())
        self._transport.send_line(eas_wire.build_g_line(game_code))
        self._transport.recv_packet()
        self._transport.send_line(eas_wire.build_p_line(game_code))
        self._transport.recv_packet()
        self._transport.send_line(eas_wire.build_c_line())
        return eas_wire.parse_char_list(self._transport.recv_packet())

    def enumerate_all(self) -> list[CharacterListing]:
        listings: list[CharacterListing] = []
        for game in self.list_games():
            self._transport.send_line(eas_wire.build_n_line(game.code))
            if not eas_wire.parse_n_response(self._transport.recv_packet()):
                continue
            for char_code, char_name in self._characters_for_game(game.code):
                listings.append(
                    CharacterListing(
                        game_code=game.code,
                        game_name=game.name,
                        char_code=char_code,
                        char_name=char_name,
                    )
                )
        return listings

    def select_character(self, game_code: str, char_code: str, game_type: str = "STORM") -> HandoffInfo:
        # Re-run F/G/P/C for this specific game_code immediately before L,
        # matching the targeted (non-legacy) path of eaccess.rb - confirmed
        # live 2026-09-07 that skipping this leaves the server-side
        # "current game" context of the EAS session pointed at whichever
        # game code enumerate_all() walked last, so every handoff silently
        # returned the connection info of that game regardless of which
        # character was actually requested (the server still replied with
        # a well-formed L response, but the game server then rejected the
        # resulting KEY with a generic "Invalid login key" error, since it
        # did not correspond to a properly-selected session for that game).
        self._characters_for_game(game_code)
        self._transport.send_line(eas_wire.build_l_line(char_code, game_type))
        kv = eas_wire.parse_handoff_kv(self._transport.recv_packet())
        return HandoffInfo.from_kv(kv)

    def close(self) -> None:
        self._transport.close()
