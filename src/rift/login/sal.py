"""Writes a temp Simutronics Autolaunch (SAL) file for a launched front-end.

SAL is a small, publicly-known KEY=VALUE text format already consumed
directly by real front-ends (Wrayth, Stormfront, Wizard) - this is an
independent implementation of that public format, not lich5 code (see
docs/sal-format.md and the licensing policy in CLAUDE.md).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from rift.login.models import HandoffInfo

_KNOWN_FIELD_ORDER = ("gamehost", "gameport", "key", "game", "gamefile", "fullgamename")


def sal_dir() -> Path:
    # Prefer XDG_RUNTIME_DIR (per-user tmpfs, auto-wiped at logout) over a
    # shared /tmp - the file briefly holds a live, single-use session key.
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    return Path(runtime_dir) if runtime_dir else Path(tempfile.gettempdir())


def _sal_lines(handoff: HandoffInfo) -> list[str]:
    fields = {name: getattr(handoff, name) for name in _KNOWN_FIELD_ORDER}
    fields.update(handoff.extra)
    return [f"{key.upper()}={value}\n" for key, value in fields.items() if value]


def write_sal_file(handoff: HandoffInfo, directory: Path | None = None) -> Path:
    directory = directory or sal_dir()
    fd, raw_path = tempfile.mkstemp(prefix="rift-nexus-", suffix=".sal", dir=directory)
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "w") as f:
            f.writelines(_sal_lines(handoff))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, 0o600)  # mkstemp already creates 0600; explicit for clarity
    return path
