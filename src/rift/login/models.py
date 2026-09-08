"""Data models for EAS game/character listings and session handoff."""

from __future__ import annotations

from dataclasses import dataclass, field

_KNOWN_HANDOFF_FIELDS = ("gamehost", "gameport", "key", "game", "gamefile", "fullgamename")


@dataclass(frozen=True)
class GameListing:
    code: str
    name: str


@dataclass(frozen=True)
class CharacterListing:
    game_code: str
    game_name: str
    char_code: str
    char_name: str


@dataclass(frozen=True)
class HandoffInfo:
    gamehost: str
    gameport: str
    key: str
    game: str
    gamefile: str = ""
    fullgamename: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_kv(cls, kv: dict[str, str]) -> HandoffInfo:
        remaining = dict(kv)
        known = {name: remaining.pop(name, "") for name in _KNOWN_HANDOFF_FIELDS}
        return cls(**known, extra=remaining)
