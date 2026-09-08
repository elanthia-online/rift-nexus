# SAL format reference

Reference for the Simutronics Autolaunch (SAL) file format, as produced by `login/sal.py` and consumed by `client/sal_reader.py`. SAL is a small, publicly-known `KEY=VALUE` text format already consumed directly by real front-ends (Wrayth, Stormfront, Wizard) — this describes an independent implementation of that public format, not `lich-5` code. See the licensing policy in `CLAUDE.md`.

## Purpose

A SAL file is the handoff artifact between an EAS login flow and a game front-end: it carries everything a front-end needs to connect directly to the game server without repeating the EAS handshake. `login` writes one after a successful character selection; `client` (or any other SAL-consuming front-end — Wrayth, Stormfront, Wizard) reads and deletes it on launch.

`client` deliberately does not import from `login` to read this file (see `sal_reader.py`'s module docstring) — the SAL file itself is the entire integration contract between the two packages, by design. This mirrors the same decoupling rationale documented for `login/launcher.py` in `docs/decisions.md`.

## File shape

Plain text, one `KEY=VALUE` pair per line, no section headers or quoting:

```
GAMEHOST=<host>
GAMEPORT=<port>
KEY=<single-use session token>
GAME=<game code>
GAMEFILE=<game file, if provided>
FULLGAMENAME=<display name, if provided>
```

- Keys are written upper-case (`_sal_lines()` in `sal.py`); `sal_reader.read_sal_file()` lower-cases them again on read, so case is not meaningful in either direction.
- Field order matches `_KNOWN_FIELD_ORDER` in `sal.py`: `gamehost`, `gameport`, `key`, `game`, `gamefile`, `fullgamename`, followed by any additional fields the EAS `L` response returned (`HandoffInfo.extra`) that are not part of the known set. Any field with an empty value is omitted entirely, not written as `KEY=`.
- `sal_reader.read_sal_file()` does not require any particular field order or set — it parses every `key=value` line it finds (splitting only on the first `=`) and ignores blank lines or lines without an `=`. It is intentionally permissive since it must work against SAL files written by other tools, not only this project's `login`.

## Field meanings

| Field | Meaning |
|---|---|
| `gamehost` | Game server hostname/IP to connect to (distinct from the EAS host). |
| `gameport` | Game server port. |
| `key` | Single-use session token authorizing the connection; the game server rejects a stale or already-used key. |
| `game` | Game code (e.g. the short code EAS uses to identify GS4/DR). |
| `gamefile` | Optional; not always present in a handoff response. |
| `fullgamename` | Optional; human-readable game name, not always present. |

Any other key EAS returns in the `L\tOK\t...` response (see `docs/eas-protocol.md`) that is not one of the above passes through unchanged via `HandoffInfo.extra` and is written as-is — the format is treated as open-ended, not a fixed schema, since the real EAS response is not itself formally specified anywhere the implementation could source a closed field list.

## Lifecycle and security notes

- **Location:** `sal.sal_dir()` prefers `XDG_RUNTIME_DIR` (a per-user tmpfs, wiped at logout) over the shared system temp directory, because the file briefly holds a live, single-use session key.
- **Permissions:** written `0600` (owner read/write only) via `tempfile.mkstemp` plus an explicit `os.chmod` for clarity.
- **Naming:** `tempfile.mkstemp(prefix="rift-nexus-", suffix=".sal", ...)` — a random, collision-resistant filename, not a fixed path.
- **Single use:** `read_sal_file()` deletes the file immediately after reading by default (`delete_after=True`), since the `key` field is a single-use token and there is no reason for the file to persist past the front-end reading it once.
- **Cleanup on write failure:** if writing the file body fails partway through, `write_sal_file()` unlinks the partially-written temp file before re-raising, rather than leaving a corrupt SAL file behind.
