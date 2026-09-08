"""EAS wire-protocol encode/decode functions.

Pure functions only, no I/O - see docs/eas-protocol.md for the behavioral
reference this implements. This is an independent implementation of the
observed protocol behavior, not a translation of source from any
reference client.

Messages carry no trailing newline - the TLS layer delivers each message
as a complete unit, so tls_transport.py does one read per message rather
than scanning for a delimiter. parse_* functions still rstrip("\\n")
defensively in case a stray newline shows up, but build_*_line functions
deliberately do not append one.
"""

from __future__ import annotations

# Server-returned error codes confirmed empirically. Grows as more are
# observed - an unrecognized code still surfaces via error_code, just
# without a friendly description.
_KNOWN_ERROR_MESSAGES = {
    "PASSWORD": "Incorrect account password.",
}


def describe_error_code(error_code: str) -> str:
    return _KNOWN_ERROR_MESSAGES.get(error_code, f"EAS returned error code: {error_code}")


class EASProtocolError(Exception):
    """An EAS response did not match the expected pattern for its step."""


class EASAuthenticationError(EASProtocolError):
    """The server rejected the account/password combination (the A step)."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(describe_error_code(error_code))


class EASCharacterSelectionError(EASProtocolError):
    """The server rejected the character selection (the L step)."""

    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(describe_error_code(error_code))


def obscure_password(password: str, hash_key: str) -> str:
    if not hash_key:
        raise ValueError("hash_key must not be empty")
    # Keystream cycles when shorter than the password - unverified against a
    # real handshake, see docs/decisions.md risk log for the empirical check.
    result = []
    for index, char in enumerate(password):
        key_byte = ord(hash_key[index % len(hash_key)])
        shifted = ord(char) - 32
        result.append(chr((shifted ^ key_byte) + 32 & 0xFF))
    return "".join(result)


def build_k_line() -> str:
    return "K"


def build_a_line(account: str, scrambled_password: str) -> str:
    return f"A\t{account}\t{scrambled_password}"


def build_m_line() -> str:
    return "M"


def build_f_line(game_code: str) -> str:
    return f"F\t{game_code}"


def build_g_line(game_code: str) -> str:
    return f"G\t{game_code}"


def build_p_line(game_code: str) -> str:
    return f"P\t{game_code}"


def build_c_line() -> str:
    return "C"


def build_n_line(game_code: str) -> str:
    return f"N\t{game_code}"


def build_l_line(char_code: str, game_type: str = "STORM") -> str:
    # "STORM" is the only confirmed-working value here (live-tested
    # 2026-09-07; "WIZARD" and "PRODUCTION" both failed with a generic
    # error code). It appears to be a fixed protocol-version literal at
    # this EAS layer, not a front-end choice - the real
    # XML-tagged-vs-plain-text choice happens one layer downstream, in
    # the /FE: and /XML fields of the game-socket handshake (game_socket.py).
    # game_type stays a parameter for flexibility, not because
    # alternatives are known to work.
    return f"L\t{char_code}\t{game_type}"


def parse_hash_key(response: str) -> str:
    fields = response.rstrip("\n").split("\t")
    return fields[-1] if fields else ""


def parse_error_token(response: str) -> str:
    fields = response.rstrip("\n").split("\t")
    return fields[-1] if fields else ""


def parse_key_response(response: str) -> str:
    fields = response.rstrip("\n").split("\t")
    if "KEY" in fields:
        index = fields.index("KEY")
        if index + 1 < len(fields):
            return fields[index + 1]
    raise EASAuthenticationError(parse_error_token(response))


def parse_game_list(response: str) -> list[tuple[str, str]]:
    fields = response.rstrip("\n").split("\t")
    if not fields or fields[0] != "M":
        raise EASProtocolError(f"unexpected game-list response: {response!r}")
    pairs = fields[1:]
    return list(zip(pairs[0::2], pairs[1::2]))


def parse_subscription(response: str) -> str:
    # Open-ended, like parse_handoff_kv - live accounts show values well
    # beyond a small enum (PREMIUM, TRIAL, FREE, EXPIRED, NEW_TO_GAME,
    # UNKNOWN observed 2026-09-07), and _characters_for_game() does not
    # otherwise act on the value, so there is nothing to validate against.
    fields = response.rstrip("\n").split("\t")
    return fields[-1] if fields else ""


def parse_char_list(response: str) -> list[tuple[str, str]]:
    fields = response.rstrip("\n").split("\t")
    if not fields or fields[0] != "C":
        raise EASProtocolError(f"unexpected character-list response: {response!r}")
    pairs = fields[5:]  # "C" + 4 leading numeric fields, then char_code/char_name pairs
    return list(zip(pairs[0::2], pairs[1::2]))


def parse_n_response(response: str) -> bool:
    fields = response.rstrip("\n").split("\t")
    if not fields:
        return False
    # Last field is pipe-delimited flags, e.g. "PRODUCTION|STORM|TRIAL".
    flags = fields[-1].split("|")
    return "STORM" in flags


def parse_handoff_kv(response: str) -> dict[str, str]:
    fields = response.rstrip("\n").split("\t")
    if len(fields) < 2 or fields[0] != "L" or fields[1] != "OK":
        raise EASCharacterSelectionError(parse_error_token(response))
    result: dict[str, str] = {}
    for field in fields[2:]:
        key, _, value = field.partition("=")
        result[key.lower()] = value
    return result
