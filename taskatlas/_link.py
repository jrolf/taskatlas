"""Link model — typed relationships between entities."""

from __future__ import annotations

from datetime import datetime, timezone

from taskatlas._identity import make_id
from taskatlas._types import LINK_KINDS


class Link:
    """A typed, directed relationship between two atlas entities.

    Source/target may be any combination of goal and task.
    """

    __slots__ = (
        "id",
        "source_id",
        "source_type",
        "target_id",
        "target_type",
        "kind",
        "created_at",
        "meta",
    )

    def __init__(
        self,
        *,
        source_id: str,
        source_type: str,
        target_id: str,
        target_type: str,
        kind: str,
        meta: dict | None = None,
        id: str | None = None,
        created_at: str | None = None,
    ) -> None:
        if kind not in LINK_KINDS:
            raise ValueError(
                f"Invalid link kind {kind!r}. Must be one of {list(LINK_KINDS)}"
            )
        if source_type not in ("goal", "task"):
            raise ValueError(f"source_type must be 'goal' or 'task', got {source_type!r}")
        if target_type not in ("goal", "task"):
            raise ValueError(f"target_type must be 'goal' or 'task', got {target_type!r}")
        if source_id == target_id:
            raise ValueError("Cannot link an entity to itself")

        self.id: str = id or make_id("lk")
        self.source_id = source_id
        self.source_type = source_type
        self.target_id = target_id
        self.target_type = target_type
        self.kind = kind
        self.created_at: str = created_at or datetime.now(timezone.utc).isoformat()
        self.meta: dict = meta or {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "target_id": self.target_id,
            "target_type": self.target_type,
            "kind": self.kind,
            "created_at": self.created_at,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> Link:
        return cls(
            id=payload["id"],
            source_id=payload["source_id"],
            source_type=payload["source_type"],
            target_id=payload["target_id"],
            target_type=payload["target_type"],
            kind=payload["kind"],
            created_at=payload.get("created_at"),
            meta=payload.get("meta", {}),
        )

    def __repr__(self) -> str:
        return (
            f"Link({self.source_type}:{self.source_id} "
            f"--{self.kind}--> "
            f"{self.target_type}:{self.target_id})"
        )
