# Decisions

Running log of choices made and why. Newest at bottom. Not formal ADR numbering — a solo project doesn't need the ceremony, just the record.

---

## Scope & framing

**Not a port.** lich-5 scripts are Ruby source executed as Ruby threads with an injected runtime API. Python cannot execute that source. This project rebuilds the *functionality* idiomatically in Python; it does not translate Ruby syntax line-by-line. Corollary: the Ruby script corpus (`scripts`, `dr-scripts`) can never be used as executable conformance test input — there is no "does this real script run against our engine" check possible. It is read-only research material for API design (what globals/methods real scripts actually call, and how often), nothing more.

**Primary goal is evaluating whether a Python rewrite is a viable, genuinely usable alternative** to the Ruby-based lich-5 ecosystem — partly motivated by Python having more mature/accurate AI-assisted tooling than Ruby. Secondary goal is a learning vehicle for Python.

## Stack

- **Python 3.14** — current stable release at time of decision (3.15 was alpha-only).
- **PySide6** (Qt6) for `login` and `client` GUIs, chosen over Tkinter. Reasoning: lich5's own login manager is a GTK3 app — a real toolkit with native list/tree widgets, not a simple form. PySide6 gets closer functional parity and is a more broadly transferable skill than Tkinter.
- **pytest** — confirmed. Wired into `pyproject.toml` (`dev` extra plus `[tool.pytest.ini_options]` with `testpaths`/`pythonpath` set for the `src/` layout).

## Repository & package structure

**One repo, six internal packages, not six separate distributed packages.** Full separation (independently versioned/installable packages) was considered and rejected for now: correct package boundaries aren't yet known this early, and premature boundaries are often wrong boundaries. A true monolith was also rejected: it would blur genuinely different concerns (pure parsing logic vs. GUI code) and would teach less about Python's module/package system, which is itself a stated learning goal. Chosen middle ground: one repo, enforced import boundaries between packages, `src/` layout (catches packaging mistakes early by preventing accidental imports from the working directory instead of the installed package).

**Six packages:** `protocol`, `engine`, `mapdb`, `pkgmanager`, `login`, `client`. See `docs/architecture.md` for responsibilities and the dependency graph. Key finding: `protocol`, `mapdb`, and `pkgmanager` have no live-connection dependency and can be built/tested first, in any order; `engine` and `login` are mutually independent; `client` is the only package genuinely downstream of the others.

## Component 3 (`client`) scope

Confirmed as an independent, full game client — not a proxy requiring an external front-end. Target UX parity: Wrayth (closed source — reference for behavior/UX only). Implementation-level references: Urnon and ProfanityFE (both open source, inspectable).

## Naming

- **Package namespace:** `rift`. GemStone IV lore tie: the Rift is the in-game location spirits of the dead pass through — apt metaphor for "same functional intent, entirely new substrate."
- **Repository name:** `rift-nexus`. Considered and rejected: `project-rift` (too generic, reads as placeholder), `rift-lab` / `rift-sandbox` (accurately describes the project's actual nature — primarily a learning sandbox — but undersells intent; the name needed to read as a serious, fully-formed replacement, not a labeled experiment), `rift-portal` (good multi-component-entry-point framing, but "portal" carries generic SaaS/product-dashboard connotations). `rift-nexus` chosen for reading as intentional/permanent while still accurately describing the repo as a convergence point for multiple components. Note: this is a naming-merit choice, not a confirmed GS4-lore tie — no established in-game link between "the Rift" and "a Nexus" was confirmed.
- **License:** MIT.

## Tooling workflow

- Architecture/naming/tradeoff decisions handled conversationally (this chat), not in Claude Code — better suited to open-ended reasoning and web research than an agentic edit/run/verify loop.
- Migration to Claude Code (VS Code) planned for once `architecture.md`, `decisions.md`, `TASKS.md`, and `CLAUDE.md` exist alongside the skeleton package directories — i.e., once there's a real codebase with real context files for its memory system to load, and the work becomes actual implementation rather than planning.
- `CLAUDE.md` is committed to source control (not gitignored) — it's project memory, shared team/self context. Personal-only preferences belong in `~/.claude/CLAUDE.md` via `@import`, not in a repo-local file (`CLAUDE.local.md` is deprecated for this reason).

## `client`: display filter panel-update suppression

`client/display_filter.py` drops several tags/components unconditionally (`dialogData`, `openDialog`, the `inv` pushStream, and `component id='room objs'/'room players'`) because they are not narrative text at all — they are out-of-band updates for dedicated Wrayth GUI panels (combat controls, vitals bars, the inventory window, and a *dedicated "current room" panel*, confirmed 2026-09-07 from memory of the real Wrayth client) that this client does not render. The server pushes these independent of what the player is currently looking at — e.g. an NPC wandering through a room re-triggers a `room objs`/`room players` update with no accompanying room name or description, purely to keep that panel's live state current.

This is why dropping them unconditionally is safe: the genuine, player-facing room presentation (on room entry or `look`) never uses these wrapper tags — it sends room name/ID/description/population/exits as plain narrative text framed by self-closing `<style .../>` markers, which the filter already passes through untouched.

Forward-looking implication for `protocol`/`engine`: the real fix is not "drop forever" but "consume into structured state." A future `protocol` package should model a `current room` state (room ID, description, contents, present NPCs/players, exits) the same way it will eventually model vitals/combat state, updated by these same panel-refresh pushes rather than discarding them. `client/display_filter.py`'s drops are explicitly a stopgap for the raw-stream MVP, not the intended long-term handling — see the "TEMPORARY, evidence-based suppression" comments in that file.

## `client`: `<prompt>` squelched as background signal

`<prompt time="...">` (the game's "> " input-ready marker) is resent standalone far more often than once per player action; the `time` attribute updates on its own periodic timer, confirmed live 2026-09-07 by finding it after nearly every other component in a real capture. A burst of these rendered as a run of near-empty "> " lines in `display_filter.py`'s output — visually similar to the blank-line clutter fixed earlier in this project, but a different root cause (repeated real content, not un-collapsed separator newlines), so the blank-line collapsing alone never touched it.

Initially deferred (2026-09-07), then resolved the same session once the user confirmed the intended behavior: most front ends squelch `<prompt>` as background signal and never render it as transcript text, which this client has no reason to deviate from since it uses a dedicated input box rather than a command-echo convention that would need the prompt as a visual cue. Added `"prompt"` to `display_filter.py`'s existing `_DROP_WITH_CONTENT` list — no new mechanism needed, since prompt already matched that drop-a-whole-tag-and-content shape.

The underlying `time` value is not lost forever: it stays in the raw session log for whenever a real round-timer becomes `protocol`-package work, per the user's stated intent ("those prompts need to be tracked to maintain a running game-timer ultimately") — `display_filter.py` deliberately stays a dumb text-stripper rather than growing state-tracking of its own.

## `login`: `launcher.py`

Substitutes an already-written SAL path into a configurable launch-command template and `subprocess.Popen`s it — `"rift-client --sal {sal_path}"` by default, but any SAL-consuming front-end (Wrayth, Stormfront, Wizard) can be configured instead, matching `login`'s role as a launcher rather than a client tied to one front-end. Deliberately decoupled from `sal.py`/`config.py`: it takes a plain path and template string, not a `HandoffInfo`/`LoginConfig` object, so `worker.py` (task #11) owns stitching `select_character()` → `write_sal_file()` → `launcher.launch()` together. The SAL path is `shlex.quote()`-d before substitution (not after), so it survives the subsequent `shlex.split()` as one token even with spaces, while the rest of a locally-configured template keeps normal shell-style quoting of its own.

Live-tested (2026-09-07, not just against a mocked `subprocess.Popen`): confirmed the default template resolves and spawns `rift-client` correctly when the venv is activated; confirmed a custom template with a space-containing SAL path is quoted correctly through a real (unmocked) `Popen` call; and confirmed a real gap — with a "clean" `PATH` (venv's `bin/` not on it), `Popen` raises `FileNotFoundError` immediately, since PATH resolution does not derive from `sys.executable`'s location. `launcher.py` itself does not catch this; `worker.py` needs a `try/except FileNotFoundError` around the launch call to surface a friendly error rather than an unhandled traceback.

## `client`: `stream_worker.py` — connect-time failure vs. genuine disconnect

Bug found via the `launcher.py` live-testing above: `StreamWorker.start()`'s `finally` block used to emit `connection_closed` unconditionally, regardless of *why* the `try` block exited. A failed `connect()` (bad host, refused port) never reaches a live game session, but still triggered the exact same "auto-close the window" path as a real, established session ending — confirmed live by launching the real client against an address nothing listens on: the window closed itself immediately after showing the error, before it could be read.

Fixed by tracking whether the handshake actually completed (`connected = True`, set only after `perform_handshake()` returns) and gating the `finally` block's `connection_closed.emit()` on that flag. A connect/handshake failure now only emits `error` and leaves the window open; a failure or EOF after a successful handshake still emits `connection_closed` as before. This matches the original intent from when `window.py`'s auto-close-on-disconnect was built: closing should follow a genuine disconnect of a live session, not a connection attempt that never succeeded.

## `login`: `eas_wire.obscure_password()` risk log

`obscure_password()` XORs each password character against a byte of the server-issued hash key, cycling the key (`index % len(hash_key)`) when the password is longer than the key. This cycling behavior is unverified — every live handshake tested so far (2026-09-07) used a password no longer than the returned hash key, so the cycling branch has never actually executed against a real server response. It is implemented on the reasonable assumption that a stream-cipher-style keystream would cycle rather than fail or truncate, not on empirical confirmation.

**Risk:** if a real account ever has a password longer than the hash key EAS returns, authentication could silently fail (wrong scrambled password) with no obvious cause, since `describe_error_code()` only distinguishes `PASSWORD` from other generic codes. If that happens, check this cycling assumption first before suspecting the account credentials themselves.
