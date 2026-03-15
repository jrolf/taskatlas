"""Event model — immutable records of change."""

from __future__ import annotations

from datetime import datetime, timezone

from taskatlas._identity import make_id


class Event:
    """A historical record of a mutation in the atlas.

    Events are append-only and should not be modified after creation.
    """

    __slots__ = (
        "id",
        "event_type",
        "entity_id",
        "entity_type",
        "timestamp",
        "data",
        "reason",
    )

    def __init__(
        self,
        *,
        event_type: str,
        entity_id: str,
        entity_type: str,
        data: dict | None = None,
        reason: str | None = None,
        id: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        self.id: str = id or make_id("ev")
        self.event_type = event_type
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.timestamp: str = timestamp or datetime.now(timezone.utc).isoformat()
        self.data: dict = data or {}
        self.reason: str | None = reason

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "timestamp": self.timestamp,
            "data": self.data,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Event:
        return cls(
            id=payload["id"],
            event_type=payload["event_type"],
            entity_id=payload["entity_id"],
            entity_type=payload["entity_type"],
            timestamp=payload["timestamp"],
            data=payload.get("data", {}),
            reason=payload.get("reason"),
        )

    def __repr__(self) -> str:
        return (
            f"Event({self.event_type!r}, entity={self.entity_type}:{self.entity_id})"
        )
