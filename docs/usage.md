# Usage

Manual, end-to-end instructions for running the real `login` → `client` chain against a live account. Automated `pytest` coverage (fixtures/mocks, no live connection) is separate — see `docs/architecture.md`'s Testing philosophy section.

## Setup

```bash
cd rift-nexus
python3.14 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

This installs the `rift-login` and `rift-client` console scripts into the venv. The venv must stay active in whatever shell launches `rift-login`, because `login/launcher.py` resolves `rift-client` via `PATH` when it spawns the client process — see the known gap logged under "`login`: `launcher.py`" in `docs/decisions.md`. If `PATH` doesn't include the venv's `bin/`, character selection fails immediately with `FileNotFoundError`.

## Running the login → client handoff

Launch the login GUI:

```bash
rift-login --debug        # or: RIFT_DEBUG=1 rift-login
```

`--debug`/`RIFT_DEBUG` enables verbose protocol-level logging in the terminal, including the EAS handshake and the launch command `launcher.py` builds.

In the GUI: enter your account name/password, log in, then pick a game and character. On confirmation this should:

1. complete the EAS handshake,
2. write a SAL handoff file (temp file under `$XDG_RUNTIME_DIR`, falling back to the system temp directory if that's unset; filename prefix `rift-nexus-*.sal`, mode `0600`),
3. spawn `rift-client --sal <path>` via `launcher.py`'s configurable launch-command template (default: `rift-client --sal {sal_path}`; override `launch_command_template` in `~/.config/rift-nexus/config.json` to point at a different SAL-consuming front-end, such as Wrayth, instead).

The `rift-client` window should then open, connect, and render the live game stream (filtered through `client/display_filter.py`).

To run the client standalone against a hand-written or previously-captured SAL file, skip login entirely:

```bash
rift-client --sal /path/to/file.sal --debug
```

## What to check on a manual run

- Does `rift-login`'s terminal output show a clean handshake end-to-end (with `--debug`)?
- Does `rift-client` actually spawn, or does the `PATH`/`FileNotFoundError` gap above bite?
- Does the client window stay open and show live text, or does it auto-close unexpectedly (see the connect-vs-disconnect fix in `docs/decisions.md` under "`client`: `stream_worker.py`")?
- Any prompt-spam, garbled tags, or missing room text in the rendered output.
