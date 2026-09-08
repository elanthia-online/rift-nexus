# Tasks

Checkboxes render as tickable in GitHub's file view — this doubles as a lightweight board. Keep items small enough to check off in one sitting; split anything that stalls for more than a session or two.

## Repo setup

- [x] MIT license
- [x] `docs/architecture.md`
- [x] `docs/decisions.md`
- [X] `CLAUDE.md`
- [X] `README.md`
- [X] `pyproject.toml`
- [X] Skeleton package directories (`src/rift/{protocol,engine,mapdb,pkgmanager,login,client}`)
- [X] Skeleton `tests/` directories, one per package
- [X] First Claude Code (VS Code) session: confirm it reads `CLAUDE.md` and summarizes the project correctly before any real code is written

## protocol

- [ ] Recorded session log fixture set (capture real GS/DR feed samples)
- [ ] Tag/event grammar reference doc (what the feed actually looks like)
- [ ] Core tag parser (room, health, combat, text)
- [ ] Structured event interface (what `engine`/`client` consume)
- [ ] Unit tests against fixture logs

## mapdb

- [ ] Room graph data model
- [ ] Import path targeting `cartograph`'s MapDB *data format* (or a documented subset) — schema compatibility only, no code reuse (see CLAUDE.md licensing policy)
- [ ] Pathfinding (`;go2` equivalent)
- [ ] Unit tests against a small fixture map

## pkgmanager

- [ ] Repo manifest format (own format, or jinx-compatible manifest *schema* only — no code reuse, see CLAUDE.md licensing policy — decide and log in decisions.md)
- [ ] Install/update client
- [ ] Unit tests against a mock repo

## engine

- [ ] Static-analysis pass over `elanthia-online/scripts` corpus — frequency table of globals/methods actually used (informs API priority)
- [ ] Script loading/execution model (Python equivalent of "new thread + injected API")
- [ ] Core scripting API surface (v1: cover top items from frequency table)
- [ ] Sample scripts written against the new API, used as engine tests

## login

- [X] EAS protocol reference doc (`docs/eas-protocol.md`)
- [X] SAL format reference doc (`docs/sal-format.md`)
- [X] Auth flow implementation (`eas_wire.py`, `eas_client.py`, `tls_transport.py`, `cert_pinning.py` — tested)
- [X] PySide6 UI: character/server selection (`ui.py`'s `LoginWindow` — tested)
- [X] Session handoff to `client` (`worker.py` → `sal.py` → `launcher.py` — tested)

## client

- [ ] Wrayth UX reference notes (what parity actually means, concretely)
- [ ] Urnon / ProfanityFE study notes — approach only, no code reuse (see CLAUDE.md licensing policy)
- [X] PySide6 shell + connection to `login` session (`window.py`/`app.py`/`sal_reader.py` consume the SAL handoff file — tested)
- [ ] Render loop consuming `protocol` events (blocked on `protocol` package; `stream_worker.py` currently pipes raw text through `display_filter.py`'s regex stripper as a stopgap)
- [x] `display_filter.py`: squelch repeated `<prompt time="...">` bursts (2026-09-07 — see `docs/decisions.md`)
- [ ] `protocol`: real round-timer tracking from `<prompt time="...">` (raw data still captured in session logs; not lost, just not consumed yet)
