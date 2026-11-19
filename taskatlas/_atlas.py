"""Atlas - the root container, factory, single event store, and persistence boundary."""

import copy
import json
import os
import tempfile
import warnings
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType

from taskatlas._base import _FACTORY_TOKEN, _check_unknown_keys, _now
from taskatlas._dream import Dream
from taskatlas._event import Event
from taskatlas._filtering import filter_items
from taskatlas._goal import Goal
from taskatlas._identity import make_id
from taskatlas._link import Link
from taskatlas._task import Task

_SCHEMA_VERSION = "0.3.0"


def _parse_atlas_options(first, kwargs):
    """Normalize Atlas(name_or_dict, **kwargs) arguments."""
    merged = {}
    if first is None:
        pass
    elif isinstance(first, str):
        merged["name"] = first
    elif isinstance(first, dict):
        merged.update(first)
    else:
        raise TypeError(
            f"Expected str name, dict payload, or keyword arguments for Atlas, "
            f"got {type(first).__name__}"
        )
    merged.update(kwargs)
    return merged


def _normalize_legacy_goal(gdata):
    """Migrate schema 0.2.0 goal fields into schema 0.3.0 in a fresh dict."""
    out = copy.deepcopy(gdata)
    if out.get("status") == "archived":
        out["status"] = "abandoned"
        out["archived"] = True
    return out


def _normalize_legacy_task(tdata):
    """Migrate schema 0.2.0 task fields into schema 0.3.0 in a fresh dict."""
    out = copy.deepcopy(tdata)
    stage = out.get("stage", "inbox")
    if stage == "archived":
        out["stage"] = "canceled"
        out["archived"] = True
    elif stage == "blocked":
        out["stage"] = "ready"
        out.setdefault("hold_reason", "Migrated from legacy blocked stage")
    return out


def _normalize_legacy_link(ldata):
    """Migrate schema 0.2.0 link kinds ('blocks', 'supports', etc.) to canonical 3 kinds."""
    out = copy.deepcopy(ldata)
    kind = out.get("kind")
    if kind == "blocks":
        # B --blocks--> A becomes canonical A --depends_on--> B
        out["kind"] = "depends_on"
        out["source_id"], out["target_id"] = out["target_id"], out["source_id"]
        out["source_type"], out["target_type"] = out["target_type"], out["source_type"]
    elif kind in ("supports", "duplicates", "conflicts_with"):
        meta = dict(out.get("meta") or {})
        meta.setdefault("legacy_kind", kind)
        out["meta"] = meta
        out["kind"] = "relates_to"
    return out


class Atlas:
    """The navigable world and sole factory in which Dreams, Goals, and Tasks live.

    An ``Atlas`` owns:
    - All ``Dream``, ``Goal``, ``Task``, and ``Link`` registries
    - The single append-only ``Event`` log plus an O(1) per-entity event index
    - Actor provenance context (``atlas.as_actor(...)``)
    - Query, readiness queue, view, and Markdown briefing methods
    - Temporal cursors, snapshot diffs, archival compaction, and POSIX-atomic JSON I/O
    - Zero-dependency agent tool schemas and structured tool dispatch
    """

    _ALLOWED_KEYS = frozenset({
        "name",
        "meta",
        "actor",
        "created_at",
        "updated_at",
    })

    def __init__(self, name_or_payload=None, **kwargs):
        opts = _parse_atlas_options(name_or_payload, kwargs)
        _check_unknown_keys(opts, self._ALLOWED_KEYS, "Atlas")

        name = opts.get("name", "")
        if not isinstance(name, str):
            raise TypeError("Atlas name must be a string")

        raw_meta = opts.get("meta") or {}
        if not isinstance(raw_meta, dict):
            raise TypeError("Atlas meta must be a dict")

        actor = opts.get("actor")
        if actor is not None and (not isinstance(actor, str) or not actor.strip()):
            raise ValueError("actor must be a non-empty string or None")

        now = _now()
        self._name = name
        self._meta = copy.deepcopy(raw_meta)
        self._active_actor = actor
        self._created_at = opts.get("created_at") or now
        self._updated_at = opts.get("updated_at") or self._created_at

        self._dreams = {}
        self._goals = {}
        self._tasks = {}
        self._links = {}
        self._events = []
        self._event_ids = set()
        self._events_by_entity = {}

    # ------------------------------------------------------------------
    # Metadata, actor provenance, and copy
    # ------------------------------------------------------------------

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str):
            raise TypeError("Atlas name must be a string")
        self._name = value
        self._updated_at = _now()

    @property
    def meta(self):
        return MappingProxyType(self._meta)

    def update_meta(self, mapping=None, **kwargs):
        """Merge key-value pairs into ``atlas.meta``."""
        updates = {}
        if mapping is not None:
            if not isinstance(mapping, dict):
                raise TypeError("mapping must be a dict")
            updates.update(mapping)
        updates.update(kwargs)
        if updates:
            self._meta.update(copy.deepcopy(updates))
            self._updated_at = _now()

    @property
    def actor(self):
        """Currently active default actor stamped onto mutations, or None."""
        return self._active_actor

    @contextmanager
    def as_actor(self, actor):
        """Temporarily stamp mutations and notes with *actor* inside a ``with`` block."""
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("as_actor() requires a non-empty actor string")
        previous = self._active_actor
        self._active_actor = actor
        try:
            yield self
        finally:
            self._active_actor = previous

    @property
    def created_at(self):
        return self._created_at

    @property
    def updated_at(self):
        return self._updated_at

    def copy(self):
        """Return an independent deep copy of this Atlas via clean round-trip."""
        return Atlas.from_dict(self.to_dict())

    # ------------------------------------------------------------------
    # Internal registry & graph helpers
    # ------------------------------------------------------------------

    def _all_entity_ids(self):
        return set(self._dreams) | set(self._goals) | set(self._tasks)

    def _find_entity(self, entity_id):
        if entity_id in self._tasks:
            return self._tasks[entity_id]
        if entity_id in self._goals:
            return self._goals[entity_id]
        if entity_id in self._dreams:
            return self._dreams[entity_id]
        return None

    def _record_event(self, event):
        self._events.append(event)
        self._event_ids.add(event.id)
        self._events_by_entity.setdefault(event.entity_id, []).append(event)
        self._updated_at = _now()

    def _rebuild_event_index(self):
        self._event_ids = set()
        self._events_by_entity = {}
        for ev in self._events:
            self._event_ids.add(ev.id)
            self._events_by_entity.setdefault(ev.entity_id, []).append(ev)

    def _register_link(self, link):
        self._links[link.id] = link

    def _has_dependency_path(self, start_id, target_id):
        """Return True if *start_id* transitively ``depends_on`` *target_id*."""
        if start_id == target_id:
            return True
        visited = set()
        stack = [start_id]
        while stack:
            curr_id = stack.pop()
            if curr_id == target_id:
                return True
            if curr_id in visited:
                continue
            visited.add(curr_id)
            entity = self._find_entity(curr_id)
            if entity is None:
                continue
            for lk in entity.get_links(kind="depends_on", direction="outgoing"):
                if lk.target_id not in visited:
                    stack.append(lk.target_id)
        return False

    def _resolve_dream(self, dream_or_id):
        if isinstance(dream_or_id, Dream):
            return dream_or_id
        if isinstance(dream_or_id, str):
            return self.get_dream(dream_or_id)
        raise TypeError(
            f"Expected Dream or str ID, got {type(dream_or_id).__name__}"
        )

    def _resolve_goal(self, goal_or_id):
        if isinstance(goal_or_id, Goal):
            return goal_or_id
        if isinstance(goal_or_id, str):
            return self.get_goal(goal_or_id)
        raise TypeError(
            f"Expected Goal or str ID, got {type(goal_or_id).__name__}"
        )

    def _resolve_task(self, task_or_id):
        if isinstance(task_or_id, Task):
            return task_or_id
        if isinstance(task_or_id, str):
            return self.get_task(task_or_id)
        raise TypeError(
            f"Expected Task or str ID, got {type(task_or_id).__name__}"
        )

    def _ensure_unique_id(self, entity_id):
        if entity_id in self._all_entity_ids():
            raise ValueError(f"An entity with id {entity_id!r} already exists in this Atlas")

    def _create_dream(self, opts):
        actor = opts.get("actor")
        if "id" in opts and opts["id"] is not None:
            self._ensure_unique_id(opts["id"])
        dream = Dream(self, opts, _token=_FACTORY_TOKEN)
        self._dreams[dream.id] = dream
        dream._emit("dream_created", actor=actor, title=dream.title)
        return dream

    def _create_goal(self, opts):
        actor = opts.get("actor")
        if "id" in opts and opts["id"] is not None:
            self._ensure_unique_id(opts["id"])

        dream_id = opts.get("dream_id")
        parent_goal_id = opts.get("parent_goal_id")
        if dream_id is not None and parent_goal_id is not None:
            raise ValueError(
                "A subgoal inherits its parent Goal's Dream; cannot specify both "
                "dream_id and parent_goal_id"
            )
        if dream_id is not None and dream_id not in self._dreams:
            raise KeyError(f"No dream with id {dream_id!r}")
        if parent_goal_id is not None and parent_goal_id not in self._goals:
            raise KeyError(f"No goal with id {parent_goal_id!r}")

        goal = Goal(self, opts, _token=_FACTORY_TOKEN)
        self._goals[goal.id] = goal
        goal._emit("goal_created", actor=actor, title=goal.title)
        return goal

    def _create_task(self, opts):
        actor = opts.get("actor")
        if "id" in opts and opts["id"] is not None:
            self._ensure_unique_id(opts["id"])

        parent_task_id = opts.get("parent_task_id")
        if parent_task_id is not None and parent_task_id not in self._tasks:
            raise KeyError(f"No task with id {parent_task_id!r}")
        for gid in opts.get("goal_ids") or []:
            if gid not in self._goals:
                raise KeyError(f"No goal with id {gid!r}")

        task = Task(self, opts, _token=_FACTORY_TOKEN)
        self._tasks[task.id] = task
        task._emit("task_created", actor=actor, title=task.title)
        return task

    # ------------------------------------------------------------------
    # Public factory methods: add_dream, add_goal, add_task
    # ------------------------------------------------------------------

    def add_dream(self, title_or_payload=None, **kwargs):
        """Create and register a new Dream in this Atlas."""
        from taskatlas._base import _parse_options

        opts = _parse_options(title_or_payload, "title", kwargs, "dream")
        return self._create_dream(opts)

    def add_goal(self, title_or_payload=None, **kwargs):
        """Create and register a new Goal in this Atlas.

        Optionally accepts ``dream_id=...`` or ``parent_goal_id=...`` to wire
        containment in a single call while emitting proper attachment events.
        """
        from taskatlas._base import _parse_options

        opts = _parse_options(title_or_payload, "title", kwargs, "goal")
        dream_id = opts.get("dream_id")
        parent_goal_id = opts.get("parent_goal_id")
        actor = opts.get("actor")

        goal = self._create_goal(opts)
        if dream_id is not None:
            dream = self._dreams[dream_id]
            if goal.id not in dream._goal_ids:
                dream._goal_ids.append(goal.id)
                dream._touch()
                dream._emit("goal_attached_to_dream", actor=actor, goal_id=goal.id)
        if parent_goal_id is not None:
            parent = self._goals[parent_goal_id]
            if goal.id not in parent._child_goal_ids:
                parent._child_goal_ids.append(goal.id)
                parent._touch()
                parent._emit("subgoal_added", actor=actor, child_id=goal.id)
        return goal

    def add_task(self, title_or_payload=None, **kwargs):
        """Create and register a new Task in this Atlas.

        Optionally accepts ``goal_ids=[...]`` or ``parent_task_id=...`` to wire
        containment in a single call while emitting proper attachment events.
        """
        from taskatlas._base import _parse_options

        opts = _parse_options(title_or_payload, "title", kwargs, "task")
        parent_task_id = opts.get("parent_task_id")
        goal_ids = list(opts.get("goal_ids") or [])
        actor = opts.get("actor")

        task = self._create_task(opts)
        for gid in goal_ids:
            goal = self._goals[gid]
            if task.id not in goal._task_ids:
                goal._task_ids.append(task.id)
                goal._touch()
                goal._emit("task_attached_to_goal", actor=actor, task_id=task.id)
        if parent_task_id is not None:
            parent = self._tasks[parent_task_id]
            if task.id not in parent._child_task_ids:
                parent._child_task_ids.append(task.id)
                parent._touch()
                parent._emit("subtask_added", actor=actor, child_id=task.id)
        return task

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_dream(self, dream_id):
        """Return a Dream by ID, raising KeyError when absent."""
        try:
            return self._dreams[dream_id]
        except KeyError:
            raise KeyError(f"No dream with id {dream_id!r}") from None

    def get_goal(self, goal_id):
        """Return a Goal by ID, raising KeyError when absent."""
        try:
            return self._goals[goal_id]
        except KeyError:
            raise KeyError(f"No goal with id {goal_id!r}") from None

    def get_task(self, task_id):
        """Return a Task by ID, raising KeyError when absent."""
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"No task with id {task_id!r}") from None

    def get_entity(self, entity_id):
        """Return any Dream, Goal, or Task by ID, raising KeyError when absent."""
        found = self._find_entity(entity_id)
        if found is None:
            raise KeyError(f"No entity with id {entity_id!r}")
        return found

    def get_dreams(self, **filters):
        """Query Dreams with conjunctive keyword filters."""
        return filter_items(list(self._dreams.values()), **filters)

    def get_goals(self, **filters):
        """Query Goals with conjunctive keyword filters."""
        return filter_items(list(self._goals.values()), **filters)

    def get_tasks(self, **filters):
        """Query Tasks with conjunctive keyword filters."""
        return filter_items(list(self._tasks.values()), **filters)

    # ------------------------------------------------------------------
    # Events, temporal cursors, snapshot diffs, and compaction
    # ------------------------------------------------------------------

    @property
    def cursor(self):
        """Latest event ID in this Atlas, or None when the event log is empty."""
        if not self._events:
            return None
        return self._events[-1].id

    def get_events(self, *, entity_id=None, event_type=None, actor=None, limit=None):
        """Return historical events (newest first) matching optional filters."""
        if entity_id is not None:
            events = list(self._events_by_entity.get(entity_id, ()))
        else:
            events = list(self._events)

        if event_type is not None:
            events = [e for e in events if e.event_type == event_type]
        if actor is not None:
            events = [e for e in events if e.actor == actor]

        events.reverse()
        if limit is not None:
            events = events[:limit]
        return events

    def recent(self, limit=20):
        """Return the *limit* most recent events across the Atlas (newest first)."""
        return self.get_events(limit=limit)

    def events_since(self, cursor=None, *, entity_id=None, event_type=None, actor=None):
        """Return events strictly after *cursor* in chronological order (oldest first).

        Parameters
        ----------
        cursor : str or None
            Either an event ID (``'ev-...'``) from an earlier ``atlas.cursor``
            checkpoint, an ISO-8601 UTC timestamp string, or ``None`` for all
            events from the beginning. Raises ``KeyError`` if an unknown
            ``'ev-...'`` ID is supplied so stale cursors never fail silently.
        """
        if cursor is None:
            sliced = list(self._events)
        elif not isinstance(cursor, str) or not cursor:
            raise ValueError("cursor must be a non-empty string or None")
        elif cursor.startswith("ev-"):
            idx = None
            for i, ev in enumerate(self._events):
                if ev.id == cursor:
                    idx = i
                    break
            if idx is None:
                raise KeyError(f"Event cursor {cursor!r} not found in Atlas history")
            sliced = self._events[idx + 1 :]
        else:
            sliced = [ev for ev in self._events if ev.timestamp > cursor]

        if entity_id is not None:
            sliced = [ev for ev in sliced if ev.entity_id == entity_id]
        if event_type is not None:
            sliced = [ev for ev in sliced if ev.event_type == event_type]
        if actor is not None:
            sliced = [ev for ev in sliced if ev.actor == actor]
        return sliced

    def diff(self, other):
        """Compute structured state deltas from ``self`` (before) to ``other`` (after).

        Useful for reviewing sub-agent runs on a copied Atlas, summarizing
        changes across ``CHRON`` ticks, and spotting newly unblocked work.
        """
        if not isinstance(other, Atlas):
            raise TypeError(f"diff() expects another Atlas, got {type(other).__name__}")

        def _diff_fields(old_obj, new_obj, attrs):
            delta = {}
            for attr in attrs:
                before_val = getattr(old_obj, attr)
                after_val = getattr(new_obj, attr)
                if before_val != after_val:
                    if isinstance(before_val, tuple):
                        before_val = list(before_val)
                    if isinstance(after_val, tuple):
                        after_val = list(after_val)
                    delta[attr] = {"before": before_val, "after": after_val}
            return delta

        dreams_added = [
            {"id": d.id, "title": d.title, "status": d.status}
            for did, d in other._dreams.items()
            if did not in self._dreams
        ]
        dreams_removed = [
            {"id": d.id, "title": d.title}
            for did, d in self._dreams.items()
            if did not in other._dreams
        ]
        dream_changes = {}
        for did, new_d in other._dreams.items():
            old_d = self._dreams.get(did)
            if old_d is None:
                continue
            delta = _diff_fields(
                old_d,
                new_d,
                ("title", "status", "priority", "vision", "archived"),
            )
            if delta:
                dream_changes[did] = delta

        goals_added = [
            {"id": g.id, "title": g.title, "status": g.status}
            for gid, g in other._goals.items()
            if gid not in self._goals
        ]
        goals_removed = [
            {"id": g.id, "title": g.title}
            for gid, g in self._goals.items()
            if gid not in other._goals
        ]
        goal_changes = {}
        for gid, new_g in other._goals.items():
            old_g = self._goals.get(gid)
            if old_g is None:
                continue
            delta = _diff_fields(
                old_g,
                new_g,
                (
                    "title",
                    "status",
                    "priority",
                    "criteria",
                    "outcome",
                    "hold_reason",
                    "archived",
                ),
            )
            if delta:
                goal_changes[gid] = delta

        tasks_added = [
            {"id": t.id, "title": t.title, "stage": t.stage}
            for tid, t in other._tasks.items()
            if tid not in self._tasks
        ]
        tasks_removed = [
            {"id": t.id, "title": t.title}
            for tid, t in self._tasks.items()
            if tid not in other._tasks
        ]
        task_changes = {}
        newly_unblocked = []
        newly_blocked = []

        for tid, new_t in other._tasks.items():
            old_t = self._tasks.get(tid)
            if old_t is None:
                continue
            delta = _diff_fields(
                old_t,
                new_t,
                (
                    "title",
                    "stage",
                    "priority",
                    "owner",
                    "hold_reason",
                    "archived",
                    "result",
                ),
            )
            if delta:
                task_changes[tid] = delta

            if old_t.is_blocked and not new_t.is_blocked and not new_t._is_terminal():
                newly_unblocked.append({"id": new_t.id, "title": new_t.title})
            elif not old_t.is_blocked and new_t.is_blocked:
                newly_blocked.append({"id": new_t.id, "title": new_t.title})

        links_added = [
            lk.to_dict()
            for lid, lk in other._links.items()
            if lid not in self._links
        ]
        links_removed = [
            lk.to_dict()
            for lid, lk in self._links.items()
            if lid not in other._links
        ]

        notes_added = []
        for eid in other._all_entity_ids():
            new_ent = other._find_entity(eid)
            old_ent = self._find_entity(eid)
            old_note_ids = {n["id"] for n in old_ent._notes} if old_ent else set()
            for n in new_ent._notes:
                if n["id"] not in old_note_ids:
                    notes_added.append({
                        "entity_id": eid,
                        "note_id": n["id"],
                        "text": n["text"],
                    })

        new_event_count = sum(
            1 for ev in other._events if ev.id not in self._event_ids
        )

        return {
            "dreams_added": dreams_added,
            "dreams_removed": dreams_removed,
            "dream_changes": dream_changes,
            "goals_added": goals_added,
            "goals_removed": goals_removed,
            "goal_changes": goal_changes,
            "tasks_added": tasks_added,
            "tasks_removed": tasks_removed,
            "task_changes": task_changes,
            "newly_unblocked_tasks": newly_unblocked,
            "newly_blocked_tasks": newly_blocked,
            "links_added": links_added,
            "links_removed": links_removed,
            "notes_added": notes_added,
            "new_event_count": new_event_count,
        }

    def compact(
        self,
        *,
        archive_terminal_tasks=False,
        archive_terminal_goals=False,
        prune_archived=False,
        keep_recent_events=None,
        actor=None,
    ):
        """Roll up or evict archived state to keep long-running Atlases fast and lean.

        - ``archive_terminal_tasks``: shelves unarchived ``done``/``canceled`` tasks.
        - ``archive_terminal_goals``: shelves unarchived ``achieved``/``abandoned`` goals.
        - ``prune_archived``: evicts archived entities that have *no* active
          (non-archived) children or incoming active dependencies, recording
          historical counts in ``atlas.meta['_compaction_ledger']``.
        - ``keep_recent_events``: trims the global event log to the newest *N* events.
        """
        if keep_recent_events is not None and (
            not isinstance(keep_recent_events, int) or keep_recent_events < 1
        ):
            raise ValueError("keep_recent_events must be a positive integer or None")

        archived_tasks = 0
        archived_goals = 0
        if archive_terminal_tasks:
            for t in list(self._tasks.values()):
                if t._is_terminal() and not t.archived:
                    t.archive(reason="Compacted terminal task", actor=actor)
                    archived_tasks += 1

        if archive_terminal_goals:
            for g in list(self._goals.values()):
                if g._is_terminal() and not g.archived:
                    g.archive(reason="Compacted terminal goal", actor=actor)
                    archived_goals += 1

        pruned_tasks = 0
        pruned_goals = 0
        pruned_dreams = 0

        def _purge_entity_links(entity):
            """Silently remove all links touching an evicted archived entity."""
            for lid in list(entity._link_ids):
                lk = self._links.pop(lid, None)
                if lk is None:
                    continue
                other_id = (
                    lk.target_id if lk.source_id == entity.id else lk.source_id
                )
                other = self._find_entity(other_id)
                if other is not None and lid in other._link_ids:
                    other._link_ids.remove(lid)
            entity._link_ids.clear()

        if prune_archived:
            ledger = copy.deepcopy(
                self._meta.get(
                    "_compaction_ledger",
                    {
                        "done_tasks": 0,
                        "canceled_tasks": 0,
                        "achieved_goals": 0,
                        "abandoned_goals": 0,
                        "archived_dreams": 0,
                    },
                )
            )

            # Prune archived tasks only when their owning parent/goals are also archived,
            # so active unarchived Goals never lose completed task counts from progress().
            changed = True
            while changed:
                changed = False
                for tid, task in list(self._tasks.items()):
                    if not task.archived:
                        continue
                    if (
                        task._parent_task_id
                        and task._parent_task_id in self._tasks
                        and not self._tasks[task._parent_task_id].archived
                    ):
                        continue
                    if any(
                        gid in self._goals and not self._goals[gid].archived
                        for gid in task._goal_ids
                    ):
                        continue
                    if any(
                        cid in self._tasks and not self._tasks[cid].archived
                        for cid in task._child_task_ids
                    ):
                        continue
                    if any(
                        not dep.archived
                        for dep in task.dependents(unsatisfied_only=False)
                    ):
                        continue
                    _purge_entity_links(task)
                    if task._parent_task_id and task._parent_task_id in self._tasks:
                        parent = self._tasks[task._parent_task_id]
                        if tid in parent._child_task_ids:
                            parent._child_task_ids.remove(tid)
                    for gid in list(task._goal_ids):
                        g = self._goals.get(gid)
                        if g is not None and tid in g._task_ids:
                            g._task_ids.remove(tid)
                    if task.stage == "done":
                        ledger["done_tasks"] += 1
                    elif task.stage == "canceled":
                        ledger["canceled_tasks"] += 1
                    del self._tasks[tid]
                    pruned_tasks += 1
                    changed = True

            # Prune archived goals only when their parent goal and dream are also archived,
            # so active Dreams never lose achieved_goal_count milestones from progress().
            changed = True
            while changed:
                changed = False
                for gid, goal in list(self._goals.items()):
                    if not goal.archived:
                        continue
                    if (
                        goal._parent_goal_id
                        and goal._parent_goal_id in self._goals
                        and not self._goals[goal._parent_goal_id].archived
                    ):
                        continue
                    if (
                        goal._dream_id
                        and goal._dream_id in self._dreams
                        and not self._dreams[goal._dream_id].archived
                    ):
                        continue
                    if any(tid in self._tasks for tid in goal._task_ids):
                        continue
                    if any(cid in self._goals for cid in goal._child_goal_ids):
                        continue
                    if any(
                        not dep.archived
                        for dep in goal.dependents(unsatisfied_only=False)
                    ):
                        continue
                    _purge_entity_links(goal)
                    if goal._parent_goal_id and goal._parent_goal_id in self._goals:
                        pg = self._goals[goal._parent_goal_id]
                        if gid in pg._child_goal_ids:
                            pg._child_goal_ids.remove(gid)
                    if goal._dream_id and goal._dream_id in self._dreams:
                        dr = self._dreams[goal._dream_id]
                        if gid in dr._goal_ids:
                            dr._goal_ids.remove(gid)
                    if goal.status == "achieved":
                        ledger["achieved_goals"] += 1
                    elif goal.status == "abandoned":
                        ledger["abandoned_goals"] += 1
                    del self._goals[gid]
                    pruned_goals += 1
                    changed = True

            # Prune archived dreams with no remaining goals
            for did, dream in list(self._dreams.items()):
                if not dream.archived:
                    continue
                if any(gid in self._goals for gid in dream._goal_ids):
                    continue
                _purge_entity_links(dream)
                ledger["archived_dreams"] += 1
                del self._dreams[did]
                pruned_dreams += 1

            if pruned_tasks or pruned_goals or pruned_dreams:
                self._meta["_compaction_ledger"] = ledger

        trimmed_events = 0
        has_entity_changes = any((
            archived_tasks,
            archived_goals,
            pruned_tasks,
            pruned_goals,
            pruned_dreams,
        ))
        if keep_recent_events is not None:
            # Reserve 1 slot for atlas_compacted when compaction emits an event
            will_emit = has_entity_changes or len(self._events) > keep_recent_events
            cap = max(keep_recent_events - 1, 0) if will_emit else keep_recent_events
            if len(self._events) > cap:
                trimmed_events = len(self._events) - cap
                self._events = self._events[-cap:] if cap else []
                self._rebuild_event_index()

        report = {
            "archived_tasks": archived_tasks,
            "archived_goals": archived_goals,
            "pruned_tasks": pruned_tasks,
            "pruned_goals": pruned_goals,
            "pruned_dreams": pruned_dreams,
            "trimmed_events": trimmed_events,
        }
        if any(report.values()):
            resolved_actor = actor if actor is not None else self._active_actor
            ev = Event(
                event_type="atlas_compacted",
                entity_id="atlas",
                entity_type="atlas",
                data=report,
                actor=resolved_actor,
                id=make_id("ev", existing=self._event_ids),
            )
            self._record_event(ev)
        return report

    # ------------------------------------------------------------------
    # Views and briefings (delegated to _views)
    # ------------------------------------------------------------------

    def board(self, *, goal_id=None, dream_id=None, **filters):
        """Return tasks bucketed by workflow stage."""
        from taskatlas._views import render_board

        return render_board(self, goal_id=goal_id, dream_id=dream_id, **filters)

    def tree(self, *, include_archived=False):
        """Return a nested hierarchy across Dreams (if present), Goals, and Tasks."""
        from taskatlas._views import render_tree

        return render_tree(self, include_archived=include_archived)

    def queue(
        self,
        *,
        goal_id=None,
        dream_id=None,
        stages=None,
        include_claimed=False,
        owner=None,
        limit=None,
    ):
        """Return critical-path prioritized, unblocked leaf tasks ready for work."""
        from taskatlas._views import render_queue

        return render_queue(
            self,
            goal_id=goal_id,
            dream_id=dream_id,
            stages=stages,
            include_claimed=include_claimed,
            owner=owner,
            limit=limit,
        )

    def summary(self):
        """Return aggregate counts, stalled dreams, and recent activity."""
        from taskatlas._views import render_summary

        return render_summary(self)

    def brief(self, *, dream_id=None, goal_id=None, queue_limit=5, recent_limit=5):
        """Render a token-tight Markdown situational briefing for humans or LLMs."""
        from taskatlas._views import render_atlas_brief

        return render_atlas_brief(
            self,
            dream_id=dream_id,
            goal_id=goal_id,
            queue_limit=queue_limit,
            recent_limit=recent_limit,
        )

    # ------------------------------------------------------------------
    # Zero-dependency agent tool seam (delegated to _tools)
    # ------------------------------------------------------------------

    @staticmethod
    def tool_schemas():
        """Return portable JSON-Schema tool descriptors for LLM tool use."""
        from taskatlas._tools import get_tool_schemas

        return get_tool_schemas()

    def dispatch(self, tool_name, arguments=None, *, actor=None):
        """Execute one named agent tool call and return a structured receipt dict."""
        from taskatlas._tools import dispatch_tool

        return dispatch_tool(self, tool_name, arguments, actor=actor)

    def as_tools(self, *, actor=None):
        """Return ``[{name, description, parameters, fn}, ...]`` specs ready for ThoughtFlow."""
        from taskatlas._tools import build_bound_tools

        return build_bound_tools(self, actor=actor)

    # ------------------------------------------------------------------
    # Serialization, POSIX-atomic file I/O, and referential integrity
    # ------------------------------------------------------------------

    def to_dict(self):
        """Serialize the entire Atlas into a plain JSON-compatible dict.

        Events are stored once at the root ``events`` key rather than duplicated
        inside every entity record.
        """
        return {
            "version": _SCHEMA_VERSION,
            "name": self._name,
            "meta": copy.deepcopy(self._meta),
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "dreams": {did: d.to_dict() for did, d in self._dreams.items()},
            "goals": {gid: g.to_dict() for gid, g in self._goals.items()},
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
            "links": {lid: lk.to_dict() for lid, lk in self._links.items()},
            "events": [e.to_dict() for e in self._events],
        }

    def save(self, path):
        """Atomically persist the Atlas to *path* using temp-file + fsync + os.replace."""
        target = Path(path)
        parent_dir = target.parent if str(target.parent) else Path(".")
        parent_dir.mkdir(parents=True, exist_ok=True)

        payload = self.to_dict()
        serialized = json.dumps(payload, indent=2)

        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=str(parent_dir),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, str(target))
        except Exception:
            if os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
            raise

    @classmethod
    def load(cls, path):
        """Load and validate an Atlas from a JSON file on disk."""
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    @classmethod
    def from_dict(cls, payload):
        """Reconstruct an Atlas from a serialized dict and verify graph integrity."""
        if not isinstance(payload, dict):
            raise ValueError(
                f"Invalid atlas data: expected dict, got {type(payload).__name__}"
            )

        version = payload.get("version")
        is_legacy = version != _SCHEMA_VERSION
        if version is None:
            warnings.warn(
                "Atlas data has no 'version' key - migrating legacy format.",
                stacklevel=2,
            )

        try:
            atlas = cls({
                "name": payload.get("name", ""),
                "meta": payload.get("meta", {}),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
            })

            raw_dreams = payload.get("dreams", {})
            raw_goals = payload.get("goals", {})
            raw_tasks = payload.get("tasks", {})
            raw_links = payload.get("links", {})
            if not all(
                isinstance(m, dict)
                for m in (raw_dreams, raw_goals, raw_tasks, raw_links)
            ):
                raise TypeError("dreams, goals, tasks, and links must be dicts")

            for did, ddata in raw_dreams.items():
                if not isinstance(ddata, dict):
                    raise TypeError(f"Dream {did!r} payload must be a dict")
                if ddata.get("id", did) != did:
                    raise ValueError(f"Dream key {did!r} mismatches id {ddata.get('id')!r}")
                dcopy = dict(ddata, id=did)
                atlas._dreams[did] = Dream._from_dict(atlas, dcopy)

            for gid, gdata in raw_goals.items():
                if not isinstance(gdata, dict):
                    raise TypeError(f"Goal {gid!r} payload must be a dict")
                if gdata.get("id", gid) != gid:
                    raise ValueError(f"Goal key {gid!r} mismatches id {gdata.get('id')!r}")
                gcopy = _normalize_legacy_goal(gdata) if is_legacy else dict(gdata)
                gcopy["id"] = gid
                atlas._goals[gid] = Goal._from_dict(atlas, gcopy)

            for tid, tdata in raw_tasks.items():
                if not isinstance(tdata, dict):
                    raise TypeError(f"Task {tid!r} payload must be a dict")
                if tdata.get("id", tid) != tid:
                    raise ValueError(f"Task key {tid!r} mismatches id {tdata.get('id')!r}")
                tcopy = _normalize_legacy_task(tdata) if is_legacy else dict(tdata)
                tcopy["id"] = tid
                atlas._tasks[tid] = Task._from_dict(atlas, tcopy)

            seen_legacy_edges = set()
            dropped_legacy_lids = set()
            for lid, ldata in raw_links.items():
                if not isinstance(ldata, dict):
                    raise TypeError(f"Link {lid!r} payload must be a dict")
                if ldata.get("id", lid) != lid:
                    raise ValueError(f"Link key {lid!r} mismatches id {ldata.get('id')!r}")
                lcopy = _normalize_legacy_link(ldata) if is_legacy else dict(ldata)
                lcopy["id"] = lid
                lk = Link.from_dict(lcopy)
                edge_sig = (lk.source_id, lk.target_id, lk.kind)
                if is_legacy and edge_sig in seen_legacy_edges:
                    dropped_legacy_lids.add(lid)
                    continue
                seen_legacy_edges.add(edge_sig)
                atlas._links[lid] = lk

            if dropped_legacy_lids:
                for ent in list(atlas._goals.values()) + list(atlas._tasks.values()):
                    ent._link_ids = [
                        lid for lid in ent._link_ids if lid not in dropped_legacy_lids
                    ]

            raw_events = payload.get("events", [])
            if not isinstance(raw_events, list):
                raise TypeError("events must be a list")
            seen_ev_ids = set()
            loaded_events = []
            for edata in raw_events:
                ev = Event.from_dict(edata)
                if ev.id not in seen_ev_ids:
                    seen_ev_ids.add(ev.id)
                    loaded_events.append(ev)

            # Merge any legacy entity-local events that were not recorded in root events
            if is_legacy:
                for collection in (raw_goals.values(), raw_tasks.values()):
                    for item_data in collection:
                        for edata in item_data.get("events", []):
                            ev = Event.from_dict(edata)
                            if ev.id not in seen_ev_ids:
                                seen_ev_ids.add(ev.id)
                                loaded_events.append(ev)
                loaded_events.sort(key=lambda e: e.timestamp)

            atlas._events = loaded_events
            atlas._rebuild_event_index()
            atlas._validate_integrity()
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith("Invalid atlas data:"):
                raise
            raise ValueError(f"Invalid atlas data: {exc}") from exc

        return atlas

    def _validate_integrity(self):
        """Verify bidirectional pointers and acyclicity across containment and links."""
        # Check cross-collection ID collisions
        total_unique = len(self._all_entity_ids())
        total_count = len(self._dreams) + len(self._goals) + len(self._tasks)
        if total_unique != total_count:
            raise ValueError("Duplicate entity ID across Dream/Goal/Task registries")

        # Validate Dream <-> Goal containment
        for did, dream in self._dreams.items():
            for gid in dream._goal_ids:
                goal = self._goals.get(gid)
                if goal is None:
                    raise ValueError(f"Dream {did!r} references missing Goal {gid!r}")
                if goal._dream_id != did:
                    raise ValueError(
                        f"Dream {did!r} lists Goal {gid!r}, "
                        f"but Goal.dream_id is {goal._dream_id!r}"
                    )
                if goal._parent_goal_id is not None:
                    raise ValueError(
                        f"Subgoal {gid!r} cannot be attached directly to Dream {did!r}"
                    )

        # Validate Goal hierarchy and Goal <-> Task attachments
        for gid, goal in self._goals.items():
            if goal._dream_id is not None:
                dream = self._dreams.get(goal._dream_id)
                if dream is None:
                    raise ValueError(
                        f"Goal {gid!r} references missing Dream {goal._dream_id!r}"
                    )
                if gid not in dream._goal_ids:
                    raise ValueError(
                        f"Goal {gid!r} sets dream_id={goal._dream_id!r}, "
                        f"but is missing from Dream.goal_ids"
                    )

            if goal._parent_goal_id is not None:
                parent = self._goals.get(goal._parent_goal_id)
                if parent is None:
                    raise ValueError(
                        f"Goal {gid!r} references missing parent Goal "
                        f"{goal._parent_goal_id!r}"
                    )
                if gid not in parent._child_goal_ids:
                    raise ValueError(
                        f"Goal {gid!r} sets parent_goal_id={parent.id!r}, "
                        f"but is missing from parent.child_goal_ids"
                    )

            for cid in goal._child_goal_ids:
                child = self._goals.get(cid)
                if child is None:
                    raise ValueError(
                        f"Goal {gid!r} references missing child Goal {cid!r}"
                    )
                if child._parent_goal_id != gid:
                    raise ValueError(
                        f"Goal {gid!r} lists child Goal {cid!r}, "
                        f"but child.parent_goal_id is {child._parent_goal_id!r}"
                    )

            # Check Goal containment cycles
            seen = set()
            curr = goal
            while curr is not None:
                if curr.id in seen:
                    raise ValueError(f"Cyclic goal containment involving {gid!r}")
                seen.add(curr.id)
                curr = (
                    self._goals.get(curr._parent_goal_id)
                    if curr._parent_goal_id
                    else None
                )

            for tid in goal._task_ids:
                task = self._tasks.get(tid)
                if task is None:
                    raise ValueError(f"Goal {gid!r} references missing Task {tid!r}")
                if gid not in task._goal_ids:
                    raise ValueError(
                        f"Goal {gid!r} lists Task {tid!r}, "
                        f"but Task.goal_ids omits {gid!r}"
                    )

        # Validate Task hierarchy and reverse Goal attachments
        for tid, task in self._tasks.items():
            for gid in task._goal_ids:
                goal = self._goals.get(gid)
                if goal is None:
                    raise ValueError(f"Task {tid!r} references missing Goal {gid!r}")
                if tid not in goal._task_ids:
                    raise ValueError(
                        f"Task {tid!r} lists Goal {gid!r}, "
                        f"but Goal.task_ids omits {tid!r}"
                    )

            if task._parent_task_id is not None:
                parent = self._tasks.get(task._parent_task_id)
                if parent is None:
                    raise ValueError(
                        f"Task {tid!r} references missing parent Task "
                        f"{task._parent_task_id!r}"
                    )
                if tid not in parent._child_task_ids:
                    raise ValueError(
                        f"Task {tid!r} sets parent_task_id={parent.id!r}, "
                        f"but is missing from parent.child_task_ids"
                    )

            for cid in task._child_task_ids:
                child = self._tasks.get(cid)
                if child is None:
                    raise ValueError(
                        f"Task {tid!r} references missing child Task {cid!r}"
                    )
                if child._parent_task_id != tid:
                    raise ValueError(
                        f"Task {tid!r} lists child Task {cid!r}, "
                        f"but child.parent_task_id is {child._parent_task_id!r}"
                    )

            seen = set()
            curr = task
            while curr is not None:
                if curr.id in seen:
                    raise ValueError(f"Cyclic task containment involving {tid!r}")
                seen.add(curr.id)
                curr = (
                    self._tasks.get(curr._parent_task_id)
                    if curr._parent_task_id
                    else None
                )

        # Validate Links and causal acyclicity
        for lid, lk in self._links.items():
            src = self._find_entity(lk.source_id)
            dst = self._find_entity(lk.target_id)
            if src is None:
                raise ValueError(
                    f"Link {lid!r} references missing source {lk.source_id!r}"
                )
            if dst is None:
                raise ValueError(
                    f"Link {lid!r} references missing target {lk.target_id!r}"
                )
            if src._entity_type != lk.source_type:
                raise ValueError(
                    f"Link {lid!r} source_type {lk.source_type!r} mismatches "
                    f"{src._entity_type!r}"
                )
            if dst._entity_type != lk.target_type:
                raise ValueError(
                    f"Link {lid!r} target_type {lk.target_type!r} mismatches "
                    f"{dst._entity_type!r}"
                )
            if lid not in src._link_ids:
                src._link_ids.append(lid)
            if lid not in dst._link_ids:
                dst._link_ids.append(lid)

        all_entities = (
            list(self._dreams.values())
            + list(self._goals.values())
            + list(self._tasks.values())
        )
        for entity in all_entities:
            for lid in entity._link_ids:
                if lid not in self._links:
                    raise ValueError(
                        f"Entity {entity.id!r} references missing Link {lid!r}"
                    )

        for lk in self._links.values():
            if lk.kind == "depends_on":
                if self._has_dependency_path(lk.target_id, lk.source_id):
                    raise ValueError(
                        f"Cyclic depends_on graph involving {lk.source_id!r} "
                        f"and {lk.target_id!r}"
                    )

    def __repr__(self):
        parts = [f"name={self._name!r}"]
        if self._dreams:
            parts.append(f"dreams={len(self._dreams)}")
        parts.append(f"goals={len(self._goals)}")
        parts.append(f"tasks={len(self._tasks)}")
        return f"Atlas({', '.join(parts)})"
