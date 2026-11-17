"""Shared base classes for bound Atlas entities (Dream, Goal, Task)."""

import copy
from datetime import datetime, timezone
from types import MappingProxyType

from taskatlas._event import Event
from taskatlas._identity import make_id, validate_id
from taskatlas._link import Link
from taskatlas._types import LINK_KINDS, PRIORITY_LEVELS

_FACTORY_TOKEN = object()


def _now():
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _parse_options(first, primary_key, kwargs, entity_label):
    """Normalize (title_or_dict, **kwargs) construction inputs into one dict.

    Supports three ergonomic call styles:
    1. Positional string: ``add_task("Write tests", priority="high")``
    2. Dict payload: ``add_task({"title": "Write tests", "priority": "high"})``
    3. Keyword arguments: ``add_task(title="Write tests", priority="high")``
    """
    if isinstance(first, _WorkItem):
        raise TypeError(
            f"add_{entity_label}() creates a new {entity_label.capitalize()}; "
            f"use attach_{entity_label}(...) to attach an existing instance"
        )

    merged = {}
    if first is None:
        pass
    elif isinstance(first, str):
        merged[primary_key] = first
    elif isinstance(first, dict):
        merged.update(first)
    else:
        raise TypeError(
            f"Expected str title, dict payload, or keyword arguments for "
            f"{entity_label}, got {type(first).__name__}"
        )

    merged.update(kwargs)
    return merged


def _check_unknown_keys(opts, allowed_keys, cls_name):
    """Raise ValueError when unrecognized initialization keys are supplied."""
    unknown = set(opts) - allowed_keys
    if unknown:
        raise ValueError(
            f"Unknown {cls_name} option(s): {sorted(unknown)}. "
            f"Valid options: {sorted(allowed_keys)}"
        )


def _entity_stub(item):
    """Build a compact hydrated summary dict for a neighbor entity."""
    stub = {
        "id": item.id,
        "title": item.title,
        "priority": item.priority,
    }
    if item._entity_type == "task":
        stub["stage"] = item.stage
        stub["is_blocked"] = item.is_blocked
        if item.is_held:
            stub["hold_reason"] = item.hold_reason
    elif item._entity_type == "goal":
        stub["status"] = item.status
        stub["is_blocked"] = item.is_blocked
        if item.is_held:
            stub["hold_reason"] = item.hold_reason
    else:
        stub["status"] = item.status
    if item.archived:
        stub["archived"] = True
    return stub


class _WorkItem:
    """Base class shared by Dream, Goal, and Task.

    Entities cannot be instantiated standalone; every instance is created by and
    permanently bound to an owning ``Atlas`` from birth. Tracked fields are
    exposed as read-only properties so mutations always flow through audited
    methods that record causal history in the Atlas event log.
    """

    _entity_type = ""
    _id_prefix = ""
    _BASE_KEYS = frozenset({
        "id",
        "title",
        "summary",
        "priority",
        "tags",
        "meta",
        "archived",
        "created_at",
        "updated_at",
        "actor",
    })

    def __init__(self, atlas=None, opts=None, *, _token=None, **_kwargs):
        if _token is not _FACTORY_TOKEN or atlas is None:
            cls_name = type(self).__name__
            method = f"atlas.add_{self._entity_type or cls_name.lower()}(...)"
            raise TypeError(
                f"Cannot instantiate {cls_name} directly; create it through an "
                f"Atlas via {method}"
            )
        opts = opts or {}

        title = opts.get("title", "")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{type(self).__name__} requires a non-empty 'title'")

        priority = opts.get("priority", "medium")
        if priority not in PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority {priority!r}. "
                f"Must be one of {list(PRIORITY_LEVELS)}"
            )

        raw_tags = opts.get("tags") or []
        if isinstance(raw_tags, str) or not isinstance(raw_tags, (list, tuple, set)):
            raise TypeError("tags must be a list, tuple, or set of non-empty strings")
        deduped_tags = []
        for tag in raw_tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("Each tag must be a non-empty string")
            if tag not in deduped_tags:
                deduped_tags.append(tag)

        raw_meta = opts.get("meta") or {}
        if not isinstance(raw_meta, dict):
            raise TypeError("meta must be a dict")

        archived = opts.get("archived", False)
        if not isinstance(archived, bool):
            raise TypeError("archived must be a bool")

        self._atlas = atlas
        existing_ids = atlas._all_entity_ids()
        raw_id = opts.get("id")
        if raw_id is not None:
            validate_id(raw_id, expected_prefix=self._id_prefix)
            self._id = raw_id
        else:
            self._id = make_id(self._id_prefix, existing=existing_ids)
        self._title = title
        self._summary = opts.get("summary", "") or ""
        if not isinstance(self._summary, str):
            raise TypeError("summary must be a string")

        self._priority = priority
        self._tags = deduped_tags
        self._notes = []
        self._meta = copy.deepcopy(raw_meta)
        self._archived = archived
        self._link_ids = []

        now = _now()
        self._created_at = opts.get("created_at") or now
        self._updated_at = opts.get("updated_at") or self._created_at

    # ------------------------------------------------------------------
    # Identity and representation
    # ------------------------------------------------------------------

    def __eq__(self, other):
        if not isinstance(other, _WorkItem):
            return NotImplemented
        return type(self) is type(other) and self._id == other._id

    def __hash__(self):
        return hash((type(self).__name__, self._id))

    def __repr__(self):
        return f"{type(self).__name__}(id={self._id!r}, title={self._title!r})"

    @property
    def atlas(self):
        """Return the owning Atlas container."""
        return self._atlas

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        raise AttributeError("Entity 'id' is immutable")

    @property
    def created_at(self):
        return self._created_at

    @created_at.setter
    def created_at(self, value):
        raise AttributeError("Entity 'created_at' is immutable")

    @property
    def updated_at(self):
        return self._updated_at

    @updated_at.setter
    def updated_at(self, value):
        raise AttributeError("Entity 'updated_at' is managed automatically")

    # ------------------------------------------------------------------
    # Internal mutation and event helpers
    # ------------------------------------------------------------------

    def _touch(self):
        self._updated_at = _now()

    def _resolve_actor(self, actor):
        if actor is not None:
            return actor
        return self._atlas._active_actor

    def _emit(self, event_type, reason=None, actor=None, **data):
        ev = Event(
            event_type=event_type,
            entity_id=self._id,
            entity_type=self._entity_type,
            data=data,
            reason=reason,
            actor=self._resolve_actor(actor),
            id=make_id("ev", existing=self._atlas._event_ids),
        )
        self._atlas._record_event(ev)
        return ev

    def _require_same_atlas(self, other):
        if other._atlas is not self._atlas:
            raise ValueError(
                "Cannot relate or attach entities belonging to different Atlas instances"
            )

    # ------------------------------------------------------------------
    # Read-only tracked properties and explicit mutation methods
    # ------------------------------------------------------------------

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        raise AttributeError(
            "Cannot assign to 'title' directly; use set_title(title, reason=...)"
        )

    def set_title(self, title, reason=None, *, actor=None):
        """Update the entity title and emit a ``title_changed`` event."""
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title must be a non-empty string")
        if self._title == title:
            return
        old = self._title
        self._title = title
        self._touch()
        self._emit("title_changed", reason=reason, actor=actor, old=old, new=title)

    @property
    def summary(self):
        return self._summary

    @summary.setter
    def summary(self, value):
        raise AttributeError(
            "Cannot assign to 'summary' directly; use set_summary(summary, reason=...)"
        )

    def set_summary(self, summary, reason=None, *, actor=None):
        """Update the entity summary and emit a ``summary_changed`` event."""
        if not isinstance(summary, str):
            raise TypeError("summary must be a string")
        if self._summary == summary:
            return
        old = self._summary
        self._summary = summary
        self._touch()
        self._emit("summary_changed", reason=reason, actor=actor, old=old, new=summary)

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        raise AttributeError(
            "Cannot assign to 'priority' directly; "
            "use set_priority(priority, reason=...)"
        )

    def set_priority(self, priority, reason=None, *, actor=None):
        """Change priority level and emit a ``priority_changed`` event."""
        if priority not in PRIORITY_LEVELS:
            raise ValueError(
                f"Invalid priority {priority!r}. "
                f"Must be one of {list(PRIORITY_LEVELS)}"
            )
        if self._priority == priority:
            return
        old = self._priority
        self._priority = priority
        self._touch()
        self._emit(
            "priority_changed",
            reason=reason,
            actor=actor,
            old=old,
            new=priority,
        )

    @property
    def tags(self):
        """Return tags as an immutable tuple."""
        return tuple(self._tags)

    @tags.setter
    def tags(self, value):
        raise AttributeError(
            "Cannot assign to 'tags' directly; use add_tag(tag) or remove_tag(tag)"
        )

    def add_tag(self, tag, *, actor=None):
        """Attach a tag if not already present (idempotent)."""
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("Tag must be a non-empty string")
        if tag in self._tags:
            return
        self._tags.append(tag)
        self._touch()
        self._emit("tag_added", actor=actor, tag=tag)

    def remove_tag(self, tag, *, actor=None):
        """Remove an existing tag; raises ValueError if not present."""
        if tag not in self._tags:
            raise ValueError(f"Tag {tag!r} not present on {self._id!r}")
        self._tags.remove(tag)
        self._touch()
        self._emit("tag_removed", actor=actor, tag=tag)

    @property
    def meta(self):
        """Return a read-only view of structured metadata."""
        return MappingProxyType(self._meta)

    @meta.setter
    def meta(self, value):
        raise AttributeError(
            "Cannot assign to 'meta' directly; use update_meta({...})"
        )

    def update_meta(self, mapping=None, *, reason=None, actor=None, **kwargs):
        """Merge key-value pairs into ``meta`` and emit ``meta_updated``."""
        updates = {}
        if mapping is not None:
            if not isinstance(mapping, dict):
                raise TypeError("mapping must be a dict")
            updates.update(mapping)
        updates.update(kwargs)
        if not updates:
            return
        copied = copy.deepcopy(updates)
        changed_keys = [
            k for k, v in copied.items()
            if k not in self._meta or self._meta[k] != v
        ]
        if not changed_keys:
            return
        self._meta.update(copied)
        self._touch()
        self._emit(
            "meta_updated",
            reason=reason,
            actor=actor,
            keys=sorted(changed_keys),
        )

    @property
    def archived(self):
        """Whether this item is shelved from default active views."""
        return self._archived

    @archived.setter
    def archived(self, value):
        raise AttributeError(
            "Cannot assign to 'archived' directly; use archive() or unarchive()"
        )

    def archive(self, reason=None, *, actor=None):
        """Shelve this item from default active views without altering its stage/status."""
        if self._archived:
            return
        self._archived = True
        self._touch()
        self._emit("archived", reason=reason, actor=actor)

    def unarchive(self, reason=None, *, actor=None):
        """Restore an archived item back into active views."""
        if not self._archived:
            return
        self._archived = False
        self._touch()
        self._emit("unarchived", reason=reason, actor=actor)

    # ------------------------------------------------------------------
    # Notes (append-only narrative log)
    # ------------------------------------------------------------------

    @property
    def notes(self):
        """Return append-only notes as a tuple of read-only mappings."""
        return tuple(MappingProxyType(copy.deepcopy(n)) for n in self._notes)

    @notes.setter
    def notes(self, value):
        raise AttributeError("Notes are append-only; use note(text, meta=...)")

    def note(self, text, meta=None, *, actor=None):
        """Append a timestamped note and return a plain copy of the note entry."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Note text must be a non-empty string")
        if meta is not None and not isinstance(meta, dict):
            raise TypeError("Note meta must be a dict or None")

        resolved_actor = self._resolve_actor(actor)
        entry = {
            "id": make_id("n"),
            "text": text,
            "created_at": _now(),
            "meta": copy.deepcopy(meta) if meta else {},
        }
        if resolved_actor is not None:
            entry["actor"] = resolved_actor

        self._notes.append(entry)
        self._touch()
        self._emit("note_added", actor=resolved_actor, note_id=entry["id"])
        return copy.deepcopy(entry)

    # ------------------------------------------------------------------
    # Typed cross-reference links
    # ------------------------------------------------------------------

    def link(self, target, kind, meta=None, *, reason=None, actor=None):
        """Create a typed directed link from ``self`` to ``target``.

        Idempotent: if an identical ``(source_id, target_id, kind)`` link already
        exists in the Atlas, returns it without creating a duplicate.
        Causal ``depends_on`` links are validated for acyclicity before creation.
        """
        if isinstance(target, str):
            target = self._atlas.get_entity(target)
        if not isinstance(target, _WorkItem):
            raise TypeError(
                f"Link target must be a Dream, Goal, Task, or entity ID, "
                f"got {type(target).__name__}"
            )
        self._require_same_atlas(target)

        if kind not in LINK_KINDS:
            raise ValueError(
                f"Invalid link kind {kind!r}. Must be one of {list(LINK_KINDS)}"
            )

        for lid in self._link_ids:
            existing = self._atlas._links.get(lid)
            if (
                existing is not None
                and existing.source_id == self._id
                and existing.target_id == target.id
                and existing.kind == kind
            ):
                return existing

        # Validate endpoint constraints first (e.g. Dream disallowed on depends_on)
        lk = Link(
            id=make_id("lk", existing=self._atlas._links),
            source_id=self._id,
            source_type=self._entity_type,
            target_id=target.id,
            target_type=target._entity_type,
            kind=kind,
            meta=meta,
        )

        if kind == "depends_on":
            if self._atlas._has_dependency_path(target.id, self._id):
                raise ValueError(
                    f"Cyclic dependency detected: {target.id!r} already depends "
                    f"(directly or transitively) on {self._id!r}"
                )

        self._link_ids.append(lk.id)
        target._link_ids.append(lk.id)
        self._atlas._register_link(lk)
        self._touch()
        self._emit(
            "link_added",
            reason=reason,
            actor=actor,
            link_id=lk.id,
            target_id=target.id,
            kind=kind,
        )
        return lk

    def unlink(self, target=None, kind=None, *, direction=None, reason=None, actor=None):
        """Remove links involving ``self`` matching optional filters.

        Returns the count of links removed.
        """
        if direction not in (None, "outgoing", "incoming"):
            raise ValueError(
                f"Invalid direction {direction!r}. "
                f"Must be 'outgoing', 'incoming', or None"
            )
        target_id = None
        if target is not None:
            if isinstance(target, str):
                target_id = target
            elif isinstance(target, _WorkItem):
                target_id = target.id
            else:
                raise TypeError(
                    f"Expected Dream, Goal, Task, or str ID, got {type(target).__name__}"
                )

        to_remove = []
        for lid in list(self._link_ids):
            lk = self._atlas._links.get(lid)
            if lk is None:
                continue
            if direction == "outgoing" and lk.source_id != self._id:
                continue
            if direction == "incoming" and lk.target_id != self._id:
                continue
            if target_id is not None:
                other_side = lk.target_id if lk.source_id == self._id else lk.source_id
                if other_side != target_id:
                    continue
            if kind is not None and lk.kind != kind:
                continue
            to_remove.append(lid)

        removed = 0
        for lid in to_remove:
            lk = self._atlas._links.pop(lid, None)
            if lk is None:
                continue
            if lid in self._link_ids:
                self._link_ids.remove(lid)
            other_id = lk.target_id if lk.source_id == self._id else lk.source_id
            other = self._atlas._find_entity(other_id)
            if other is not None and lid in other._link_ids:
                other._link_ids.remove(lid)
            self._emit(
                "link_removed",
                reason=reason,
                actor=actor,
                link_id=lid,
                kind=lk.kind,
                source_id=lk.source_id,
                target_id=lk.target_id,
            )
            removed += 1

        if removed:
            self._touch()
        return removed

    def get_links(self, kind=None, direction=None):
        """Return ``Link`` instances involving this entity."""
        if direction not in (None, "outgoing", "incoming"):
            raise ValueError(
                f"Invalid direction {direction!r}. "
                f"Must be 'outgoing', 'incoming', or None"
            )
        result = []
        for lid in self._link_ids:
            lk = self._atlas._links.get(lid)
            if lk is None:
                continue
            if kind is not None and lk.kind != kind:
                continue
            if direction == "outgoing" and lk.source_id != self._id:
                continue
            if direction == "incoming" and lk.target_id != self._id:
                continue
            result.append(lk)
        return result

    def _related_stubs(self):
        """Hydrate non-causal links (relates_to, derived_from) for context()."""
        items = []
        for lk in self.get_links():
            if lk.kind == "depends_on":
                continue
            is_outgoing = lk.source_id == self._id
            other_id = lk.target_id if is_outgoing else lk.source_id
            other = self._atlas._find_entity(other_id)
            if other is None:
                continue
            entry = _entity_stub(other)
            entry["link_kind"] = lk.kind
            entry["direction"] = "outgoing" if is_outgoing else "incoming"
            items.append(entry)
        return items

    # ------------------------------------------------------------------
    # History (single source of truth in Atlas._events_by_entity)
    # ------------------------------------------------------------------

    def history(self, limit=None, event_type=None):
        """Return historical events for this entity, newest first."""
        events = self._atlas._events_by_entity.get(self._id, ())
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        ordered = list(reversed(events))
        if limit is not None:
            ordered = ordered[:limit]
        return ordered

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _base_to_dict(self):
        return {
            "id": self._id,
            "title": self._title,
            "summary": self._summary,
            "priority": self._priority,
            "tags": list(self._tags),
            "notes": copy.deepcopy(self._notes),
            "meta": copy.deepcopy(self._meta),
            "archived": self._archived,
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "link_ids": list(self._link_ids),
        }

    def _base_load(self, data):
        self._notes = copy.deepcopy(data.get("notes", []))
        self._link_ids = list(data.get("link_ids", []))


class _CausalWorkItem(_WorkItem):
    """Shared causal dependency and external-hold mechanics for Goal and Task.

    Dreams intentionally inherit from ``_WorkItem`` directly rather than
    ``_CausalWorkItem`` because open-horizon Dreams cannot act as causal
    prerequisites or carry workflow holds.
    """

    def __init__(self, atlas=None, opts=None, *, _token=None, **kwargs):
        if _token is not _FACTORY_TOKEN or atlas is None:
            super().__init__(atlas, opts, _token=_token, **kwargs)
        opts = opts or {}
        hold_reason = opts.get("hold_reason")
        if hold_reason is not None:
            if not isinstance(hold_reason, str) or not hold_reason.strip():
                raise ValueError("hold_reason must be a non-empty string or None")
        super().__init__(atlas, opts, _token=_token)
        self._hold_reason = hold_reason

    def _is_satisfied(self):
        """Whether this item satisfies an incoming ``depends_on`` prerequisite."""
        raise NotImplementedError

    def _is_terminal(self):
        """Whether this item has reached a terminal lifecycle state."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # External holds (orthogonal to workflow stage / goal status)
    # ------------------------------------------------------------------

    @property
    def hold_reason(self):
        """Active external hold description, or None when not held."""
        return self._hold_reason

    @hold_reason.setter
    def hold_reason(self, value):
        raise AttributeError(
            "Cannot assign to 'hold_reason' directly; use hold(reason) or unhold()"
        )

    @property
    def is_held(self):
        """True when an explicit external hold is active on a non-terminal item."""
        if self._is_terminal():
            return False
        return self._hold_reason is not None

    def hold(self, reason, *, actor=None):
        """Place an external hold on this item without overwriting stage/status."""
        if self._is_terminal():
            raise ValueError(
                f"Cannot place terminal {self._entity_type} {self._id!r} on hold"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("hold() requires a non-empty reason string")
        if self._hold_reason == reason:
            return
        previous = self._hold_reason
        self._hold_reason = reason
        self._touch()
        self._emit(
            "held",
            reason=reason,
            actor=actor,
            previous_hold_reason=previous,
        )

    def unhold(self, reason=None, *, actor=None):
        """Clear an active external hold and restore normal readiness."""
        if self._hold_reason is None:
            return
        previous = self._hold_reason
        self._hold_reason = None
        self._touch()
        self._emit(
            "unheld",
            reason=reason,
            actor=actor,
            previous_hold_reason=previous,
        )

    # ------------------------------------------------------------------
    # Causal dependencies and live blockage computation
    # ------------------------------------------------------------------

    def blocks(self, target, *, meta=None, reason=None, actor=None):
        """Record that ``self`` blocks ``target`` as a canonical ``depends_on`` edge.

        Writing ``b.blocks(a)`` records ``a.link(b, kind='depends_on')`` so all
        dependency queries inspect one canonical edge kind and direction.
        """
        if isinstance(target, str):
            target = self._atlas.get_entity(target)
        if not isinstance(target, _CausalWorkItem):
            raise ValueError(
                "blocks() target must be a Goal or Task (Dreams cannot be causally blocked)"
            )
        return target.link(
            self,
            kind="depends_on",
            meta=meta,
            reason=reason,
            actor=actor,
        )

    def dependencies(self, *, unsatisfied_only=False):
        """Return Goal/Task prerequisites that ``self`` directly depends on."""
        prereqs = []
        for lk in self.get_links(kind="depends_on", direction="outgoing"):
            target = self._atlas._find_entity(lk.target_id)
            if target is None or not isinstance(target, _CausalWorkItem):
                continue
            if unsatisfied_only and target._is_satisfied():
                continue
            prereqs.append(target)
        return prereqs

    def blockers(self):
        """Return currently unsatisfied Goal/Task prerequisites blocking ``self``."""
        if self._is_terminal():
            return []
        return self.dependencies(unsatisfied_only=True)

    def dependents(self, *, unsatisfied_only=False):
        """Return Goal/Task items that directly depend on ``self``."""
        waiting = []
        for lk in self.get_links(kind="depends_on", direction="incoming"):
            source = self._atlas._find_entity(lk.source_id)
            if source is None or not isinstance(source, _CausalWorkItem):
                continue
            if unsatisfied_only and source._is_terminal():
                continue
            waiting.append(source)
        return waiting

    @property
    def is_topologically_blocked(self):
        """True when non-terminal and at least one prerequisite is unsatisfied."""
        if self._is_terminal():
            return False
        return len(self.blockers()) > 0

    @property
    def is_blocked(self):
        """True when non-terminal and either externally held or topologically blocked."""
        if self._is_terminal():
            return False
        return self.is_held or self.is_topologically_blocked
