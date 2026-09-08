"""Reads a Simutronics Autolaunch (SAL) file written by a login launcher.

Independent implementation - `client` does not import from `login`, since
it must work as a front-end launched from any SAL-writing source (the
launcher here, or any other one), not just the login package of this
project.
"""

from __future__ import annotations

from pathlib import Path


def read_sal_file(path: Path, *, delete_after: bool = True) -> dict[str, str]:
    text = path.read_text()
    if delete_after:
        path.unlink()  # the KEY field is a single-use game-session token

    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        fields[key.strip().lower()] = value.strip()
    return fields
