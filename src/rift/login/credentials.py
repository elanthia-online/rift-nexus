"""Password storage via the OS keyring - never written to disk by this app.

Single-account tool: the service name alone is enough to key the entry.
"""

from __future__ import annotations

import keyring
import keyring.errors

_SERVICE_NAME = "rift-nexus"


def save_password(account: str, password: str) -> None:
    keyring.set_password(_SERVICE_NAME, account, password)


def load_password(account: str) -> str | None:
    return keyring.get_password(_SERVICE_NAME, account)


def delete_password(account: str) -> None:
    try:
        keyring.delete_password(_SERVICE_NAME, account)
    except keyring.errors.PasswordDeleteError:
        pass
