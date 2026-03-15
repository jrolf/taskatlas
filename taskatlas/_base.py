"""Base work-item class shared by Goal and Task."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from taskatlas._event import Event
from taskatlas._identity import make_id
from taskatlas._link import Link
from taskatlas._types import LINK_KINDS, PRIORITY_LEVELS

if TYPE_CHECKING:
    from taskatlas._atlas import Atlas


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_payload(payload: dict | None, kwargs: dict) -> dict:
    """Merge a dict-style payload with kwargs into a single options dict."""
    if payload is not None and not isinstance(payload, dict):
        raise TypeError(f"Payload must be a dict, got {type(payload).__name__}")
    merged = dict(payload) if payload else {}
    merged.update(kwargs)
    return merged


class _WorkItem:
    """Abstract base for Goal and Task.

    Not intended for direct instantiation.
    """

    _entity_type: str = ""  # overridden by subclasses
    _id_prefix: str = ""    # overridden by subclasses

    def __init__(self, payload: dict | None = None, **kwargs) -> None:
        opts = _parse_payload(payload, kwargs)

        self.id: str = opts.get("id") or make_id(self._id_prefix)
        self.title: str = opts.get("title", "")
        self.summary: str = opts.get("summary", "")
        self.tags: list[str] = list(opts.get("tags") or [])
        self.notes: list[dict] = []
        self.meta: dict = dict(opts.get("meta") or {})

        now = _now()
        self.created_at: str = opts.get("created_at", now)
        self.updated_at: str = opts.get("updated_at", now)

        self._events: list[Event] = []
        self._link_ids: list[str] = []
        self._atlas: Atlas | None = None

        priority = opts.get("priority", "medium")
        if priority and priority not in PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority {priority!r}. "
                f"Must be one of {list(PRIORITY_LEVELS)}"
            )
        self._priority: str = priority

    # ------------------------------------------------------------------
    # Identity & comparison
    # ------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _WorkItem):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.id!r}, title={self.title!r})"

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------

    def _touch(self) -> None:
        self.updated_at = _now()

    def _emit(self, event_type: str, reason: str | None = None, **data) -> Event:
        ev = Event(
            event_type=event_type,
            entity_id=self.id,
            entity_type=self._entity_type,
            data=data,
            reason=reason,
        )
        self._events.append(ev)
        if self._atlas is not None:
            self._atlas._record_event(ev)
        return ev

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------

    @property
    def priority(self) -> str:
        return self._priority

    @priority.setter
    def priority(self, value: str) -> None:
        if value not in PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority {value!r}. "
                f"Must be one of {list(PRIORITY_LEVELS)}"
            )
        old = self._priority
        self._priority = value
        if old != value:
            self._touch()
            self._emit("priority_changed", old=old, new=value)

    def set_priority(self, priority: str, reason: str | None = None) -> None:
        if priority not in PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority {priority!r}. "
                f"Must be one of {list(PRIORITY_LEVELS)}"
            )
        old = self._priority
        if old == priority:
            return
        self._priority = priority
        self._touch()
        self._emit("priority_changed", reason=reason, old=old, new=priority)

    # ------------------------------------------------------------------
    # Title and summary
    # ------------------------------------------------------------------

    def set_title(self, title: str, reason: str | None = None) -> None:
        old = self.title
        if old == title:
            return
        self.title = title
        self._touch()
        self._emit("title_changed", reason=reason, old=old, new=title)

    def set_summary(self, summary: str, reason: str | None = None) -> None:
        old = self.summary
        if old == summary:
            return
        self.summary = summary
        self._touch()
        self._emit("summary_changed", reason=reason, old=old, new=summary)

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def add_tag(self, tag: str) -> None:
        if tag in self.tags:
            return
        self.tags.append(tag)
        self._touch()
        self._emit("tag_added", tag=tag)

    def remove_tag(self, tag: str) -> None:
        if tag not in self.tags:
            raise ValueError(f"Tag {tag!r} not present")
        self.tags.remove(tag)
        self._touch()
        self._emit("tag_removed", tag=tag)

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def note(self, text: str, meta: dict | None = None) -> dict:
        """Append a note. Returns the note record."""
        if not text:
            raise ValueError("Note text must be non-empty")
        entry = {
            "id": make_id("n"),
            "text": text,
            "created_at": _now(),
            "meta": meta or {},
        }
        self.notes.append(entry)
        self._touch()
        self._emit("note_added", note_id=entry["id"])
        return entry

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------

    def link(self, target: _WorkItem, kind: str, meta: dict | None = None) -> Link:
        """Create a typed link from this entity to *target*.

        Idempotent: if an identical link (same source, target, kind) already
        exists, the existing Link is returned without creating a duplicate.
        """
        if not isinstance(target, _WorkItem):
            raise TypeError(f"Link target must be a Goal or Task, got {type(target).__name__}")
        if kind not in LINK_KINDS:
            raise ValueError(f"Invalid link kind {kind!r}. Must be one of {list(LINK_KINDS)}")

        if self._atlas is not None:
            for existing in self._atlas._links.values():
                if (existing.source_id == self.id
                        and existing.target_id == target.id
                        and existing.kind == kind):
                    return existing

        lk = Link(
            source_id=self.id,
            source_type=self._entity_type,
            target_id=target.id,
            target_type=target._entity_type,
            kind=kind,
            meta=meta,
        )
        self._link_ids.append(lk.id)
        target._link_ids.append(lk.id)
        self._touch()

        if self._atlas is not None:
            self._atlas._register_link(lk)

        self._emit("link_added", link_id=lk.id, target_id=target.id, kind=kind)
        return lk

    def unlink(self, target: _WorkItem | None = None, kind: str | None = None) -> int:
        """Remove links matching *target* and/or *kind*. Returns count removed."""
        if self._atlas is None:
            return 0

        removed = 0
        to_remove: list[str] = []
        for lid in list(self._link_ids):
            lk = self._atlas._links.get(lid)
            if lk is None:
                continue
            if target is not None and lk.target_id != target.id and lk.source_id != target.id:
                continue
            if kind is not None and lk.kind != kind:
                continue
            to_remove.append(lid)

        for lid in to_remove:
            lk = self._atlas._links.get(lid)
            if lk is None:
                continue
            self._link_ids.remove(lid)
            other_id = lk.target_id if lk.source_id == self.id else lk.source_id
            other = self._atlas._goals.get(other_id) or self._atlas._tasks.get(other_id)
            if other is not None and lid in other._link_ids:
                other._link_ids.remove(lid)
            del self._atlas._links[lid]
            self._emit("link_removed", link_id=lid, kind=lk.kind)
            removed += 1

        if removed:
            self._touch()
        return removed

    def get_links(
        self,
        kind: str | None = None,
        direction: str | None = None,
    ) -> list[Link]:
        """Return links involving this entity.

        *kind* filters by link kind.  *direction* may be ``"outgoing"``
        (self is source), ``"incoming"`` (self is target), or ``None`` (both).
        """
        if self._atlas is None:
            return []
        result: list[Link] = []
        for lid in self._link_ids:
            lk = self._atlas._links.get(lid)
            if lk is None:
                continue
            if kind is not None and lk.kind != kind:
                continue
            if direction == "outgoing" and lk.source_id != self.id:
                continue
            if direction == "incoming" and lk.target_id != self.id:
                continue
            result.append(lk)
        return result

    def get_blockers(self) -> list[Link]:
        """Return links representing things blocking this entity.

        Includes incoming ``blocks`` links and outgoing ``depends_on`` links.
        """
        return (
            self.get_links(kind="blocks", direction="incoming")
            + self.get_links(kind="depends_on", direction="outgoing")
        )

    def get_dependents(self) -> list[Link]:
        """Return incoming ``depends_on`` links (entities waiting on this one)."""
        return self.get_links(kind="depends_on", direction="incoming")

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(
        self,
        limit: int | None = None,
        event_type: str | None = None,
    ) -> list[Event]:
        events = self._events
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        events = list(reversed(events))  # newest first
        if limit is not None:
            events = events[:limit]
        return events

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _base_to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "priority": self.priority,
            "tags": list(self.tags),
            "notes": [dict(n) for n in self.notes],
            "meta": dict(self.meta),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "link_ids": list(self._link_ids),
            "events": [e.to_dict() for e in self._events],
        }

    def _base_load(self, data: dict) -> None:
        """Restore serialized base fields (used by subclass from_dict)."""
        self.notes = data.get("notes", [])
        self._link_ids = data.get("link_ids", [])
        self._events = [Event.from_dict(e) for e in data.get("events", [])]
