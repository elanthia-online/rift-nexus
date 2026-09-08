"""Local (non-secret) configuration for the login launcher.

Stored under the XDG config directory, outside the repo. Passwords never
live here - see credentials.py for OS-keyring-backed storage.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

APP_DIR_NAME = "rift-nexus"
CONFIG_FILE_NAME = "config.json"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR_NAME


def config_path() -> Path:
    return config_dir() / CONFIG_FILE_NAME


@dataclass
class LoginConfig:
    account_name: str = ""
    last_game_code: str = ""
    last_char_code: str = ""
    launch_command_template: str = ""


def load(path: Path | None = None) -> LoginConfig:
    path = path or config_path()
    if not path.exists():
        return LoginConfig()
    data = json.loads(path.read_text())
    fields = LoginConfig.__dataclass_fields__
    return LoginConfig(**{name: data.get(name, "") for name in fields})


def save(config: LoginConfig, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2) + "\n")
    os.chmod(path, 0o600)
