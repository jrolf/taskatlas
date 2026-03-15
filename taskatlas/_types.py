"""Shared constants and type definitions for taskatlas."""

from __future__ import annotations

DEFAULT_TASK_STAGES: tuple[str, ...] = (
    "inbox",
    "ready",
    "active",
    "blocked",
    "review",
    "done",
    "archived",
)

DEFAULT_GOAL_STATUSES: tuple[str, ...] = (
    "proposed",
    "active",
    "paused",
    "achieved",
    "archived",
)

PRIORITY_LEVELS: tuple[str, ...] = (
    "low",
    "medium",
    "high",
    "urgent",
)

PRIORITY_ORDER: dict[str, int] = {p: i for i, p in enumerate(PRIORITY_LEVELS)}

LINK_KINDS: tuple[str, ...] = (
    "depends_on",
    "blocks",
    "relates_to",
    "supports",
    "duplicates",
    "derived_from",
    "conflicts_with",
)


class _Unset:
    """Sentinel for distinguishing 'not provided' from ``None``."""

    _instance: _Unset | None = None

    def __new__(cls) -> _Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()
