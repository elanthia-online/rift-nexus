# EAS protocol reference

Behavioral reference for Simutronics' Eaccess Authentication Server (EAS) protocol, as implemented by `login/eas_wire.py`, `login/eas_client.py`, and `login/tls_transport.py`. This is written from observed protocol behavior (live-tested 2026-09-07 against the real server) and public knowledge of the SAL/EAS ecosystem, not derived from `lich-5` or any other reference project's source — see the licensing policy in `CLAUDE.md`.

## Transport

- TCP + TLS to `eaccess.play.net:7910` (`tls_transport.EAS_HOST` / `EAS_PORT`).
- The server presents a self-signed certificate. `TLSTransport.connect()` disables hostname checking and chain validation (`ssl.CERT_NONE`) and instead pins against a bundled certificate via `cert_pinning.verify_pin()` — that pin check is the real trust boundary here, not TLS chain validation. See `docs/decisions.md` for the rationale.
- Encoding is `latin-1` (a 1:1 byte mapping), not UTF-8 — `obscure_password()` produces byte values across the full 0-255 range, which would not round-trip through UTF-8.
- Messages carry no trailing delimiter. Each `recv_packet()` call does exactly one socket read and treats the result as one complete message; there is no buffering or delimiter-scanning. This matches guidance from Simutronics on the transport, not an assumption.
- Fields within a message are tab-separated.

## Handshake sequence

All steps below happen over one connected transport, in order. `eas_client.EASClient` is the orchestrator; `eas_wire` holds the pure encode/decode functions.

| Step | Client sends | Server responds with | Purpose |
|---|---|---|---|
| K | `K` | a random hash key (last tab-separated field) | Establishes the per-session XOR key used to obscure the password. |
| A | `A\t<account>\t<scrambled password>` | `KEY\t<eas session key>` on success, or an error token | Authenticates the account. `<scrambled password>` comes from `obscure_password()` below. |
| M | `M` | `M\t<code1>\t<name1>\t<code2>\t<name2>...` | Lists games available to the account. |
| N | `N\t<game_code>` | last field is `\|`-delimited flags, e.g. `PRODUCTION\|STORM\|TRIAL` | Per-game capability flags. `enumerate_all()` skips a game entirely if `STORM` is not among them. |
| F | `F\t<game_code>` | subscription status (open-ended string: `PREMIUM`, `TRIAL`, `FREE`, `EXPIRED`, `NEW_TO_GAME`, `UNKNOWN` all observed live) | Not otherwise validated or acted on by this client. |
| G | `G\t<game_code>` | (unparsed) | Part of the required per-game sequence; response is currently discarded. |
| P | `P\t<game_code>` | (unparsed) | Part of the required per-game sequence; response is currently discarded. |
| C | `C` | `C\t<4 leading numeric fields>\t<char_code1>\t<char_name1>...` | Lists characters for whichever game_code the F/G/P steps most recently targeted. |
| L | `L\t<char_code>\t<game_type>` | `L\tOK\t<KEY=value pairs>` or an error token | Selects a character and returns the game-server handoff info (host, port, session key, etc. — see `docs/sal-format.md`). |

`F`, `G`, `P`, `C` must be re-run for a specific `game_code` **immediately before** the `L` step, even if `enumerate_all()` already walked that sequence earlier for every game. Confirmed live 2026-09-07: skipping this leaves the server-side "current game" context of the EAS session pointed at whichever game code was walked *last* during enumeration, so `L` still returns a well-formed handoff, but the game server then rejects the resulting `KEY` with a generic "Invalid login key" error because it was not issued against a properly-selected session for the requested game. `EASClient.select_character()` re-runs `_characters_for_game(game_code)` for exactly this reason.

`game_type` in the `L` line is a fixed protocol-version literal at this layer, not a front-end choice. Only `"STORM"` is confirmed working (live-tested 2026-09-07); `"WIZARD"` and `"PRODUCTION"` both failed with a generic error code. The real XML-tagged-vs-plain-text front-end choice happens one layer downstream, in the `/FE:` and `/XML` fields of the game-socket handshake (`client/game_socket.py`), not here. `build_l_line()` keeps `game_type` as a parameter for flexibility, not because alternatives are known to work.

## Password obscuring

`obscure_password(password, hash_key)` XORs each password character against a byte from `hash_key`, cycling the key if it is shorter than the password:

```
shifted = ord(char) - 32
result_char = chr(((shifted ^ ord(hash_key[i % len(hash_key)])) + 32) & 0xFF)
```

**Open question, not yet resolved:** the key-cycling behavior (`i % len(hash_key)`) has not been empirically verified against a real handshake where the password is longer than the returned hash key — only same-length-or-shorter passwords have been live-tested (2026-09-07). If a live test ever surfaces a password/key length mismatch that fails authentication, check this function first.

## Error handling

- `parse_error_token()` extracts the last tab-separated field of an error response as the error code.
- `describe_error_code()` maps known codes to a friendly message via `_KNOWN_ERROR_MESSAGES`; currently only `PASSWORD` → "Incorrect account password." is confirmed. Unrecognized codes still surface (as `f"EAS returned error code: {error_code}"`) rather than failing silently — extend `_KNOWN_ERROR_MESSAGES` as more codes are observed.
- `EASAuthenticationError` wraps a failed `A` step; `EASCharacterSelectionError` wraps a failed `L` step. Both carry `.error_code` for programmatic handling in addition to the friendly message.

## What this document is not

This is a description of observed client-visible behavior sufficient to drive `login`'s implementation — not a full protocol specification, and not sourced from any reference client's code. Fields and steps not exercised by this client (e.g. alternate `game_type` values, error codes beyond `PASSWORD`) are documented only to the extent they have been empirically observed or ruled out.
