"""Launches a configured front-end process against a written SAL file.

Defaults to `rift-client`, the client built as part of this project, but
the launch command is a configurable template so any SAL-consuming front-end
(Wrayth, Stormfront, Wizard) can be substituted - `login` is a launcher,
not tied to one particular client. Does not proxy or hold the connection
itself: once the front-end process is spawned, `login` has no further
job to do (see docs/decisions.md on the no-proxy-in-v1 decision).
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_LAUNCH_COMMAND_TEMPLATE = "rift-client --sal {sal_path}"


def build_command(template: str, sal_path: Path) -> list[str]:
    template = template or DEFAULT_LAUNCH_COMMAND_TEMPLATE
    # sal_path is quoted before substitution (not after) so a path
    # containing spaces or shell-special characters survives the
    # subsequent shlex.split() as a single argv token, while the rest of
    # the (trusted, locally-configured) template is still free to use
    # normal shell-style quoting/spacing of its own.
    filled = template.format(sal_path=shlex.quote(str(sal_path)))
    return shlex.split(filled)


def launch(sal_path: Path, launch_command_template: str = "") -> subprocess.Popen:
    command = build_command(launch_command_template, sal_path)
    log.info("Launching front-end: %s", command[0])
    log.debug("Full launch command: %s", command)
    return subprocess.Popen(command)
