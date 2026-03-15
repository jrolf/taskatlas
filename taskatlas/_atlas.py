"""Atlas — the root container and registry for goals, tasks, links, and events."""

from __future__ import annotations

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

from taskatlas._base import _parse_payload
from taskatlas._event import Event
from taskatlas._filtering import filter_items
from taskatlas._goal import Goal
from taskatlas._link import Link
from taskatlas._task import Task
from taskatlas._types import DEFAULT_GOAL_STATUSES, DEFAULT_TASK_STAGES

_SCHEMA_VERSION = "0.2.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Atlas:
    """The navigable world in which goals and tasks live.

    Owns all registries, indexes, and provides query/render helpers.
    """

    def __init__(self, payload: dict | None = None, **kwargs) -> None:
        opts = _parse_payload(payload, kwargs)

        self.name: str = opts.get("name", "")
        self.meta: dict = dict(opts.get("meta") or {})
        self.task_stages: tuple[str, ...] = tuple(
            opts.get("task_stages", DEFAULT_TASK_STAGES)
        )
        self.goal_statuses: tuple[str, ...] = tuple(
            opts.get("goal_statuses", DEFAULT_GOAL_STATUSES)
        )

        now = _now()
        self.created_at: str = opts.get("created_at", now)
        self.updated_at: str = opts.get("updated_at", now)

        self._goals: dict[str, Goal] = {}
        self._tasks: dict[str, Task] = {}
        self._links: dict[str, Link] = {}
        self._events: list[Event] = []

    # ------------------------------------------------------------------
    # Internal registration
    # ------------------------------------------------------------------

    def _bind(self, item) -> None:
        """Set the atlas back-reference on a work item."""
        item._atlas = self

    def _record_event(self, event: Event) -> None:
        self._events.append(event)
        self.updated_at = _now()

    def _register_goal(self, goal: Goal) -> None:
        """Idempotent registration. Emits goal_created on first registration."""
        if goal.id in self._goals:
            return
        self._goals[goal.id] = goal
        self._bind(goal)
        goal._emit("goal_created", title=goal.title)

    def _register_task(self, task: Task) -> None:
        """Idempotent registration. Emits task_created on first registration."""
        if task.id in self._tasks:
            return
        self._tasks[task.id] = task
        self._bind(task)
        task._emit("task_created", title=task.title)

    def _register_link(self, link: Link) -> None:
        self._links[link.id] = link

    # ------------------------------------------------------------------
    # Public: add goals / tasks
    # ------------------------------------------------------------------

    def add_goal(self, goal_or_payload) -> Goal:
        """Add a goal to the atlas. Accepts Goal instance or dict payload."""
        if isinstance(goal_or_payload, dict):
            goal = Goal(goal_or_payload)
        elif isinstance(goal_or_payload, Goal):
            goal = goal_or_payload
        else:
            raise TypeError(
                f"Expected Goal or dict, got {type(goal_or_payload).__name__}"
            )

        if goal.id in self._goals:
            if self._goals[goal.id] is not goal:
                raise ValueError(f"A different goal with id {goal.id!r} already exists")
            return goal

        self._register_goal(goal)
        return goal

    def add_task(self, task_or_payload) -> Task:
        """Add a task to the atlas. Accepts Task instance or dict payload."""
        if isinstance(task_or_payload, dict):
            task = Task(task_or_payload)
        elif isinstance(task_or_payload, Task):
            task = task_or_payload
        else:
            raise TypeError(
                f"Expected Task or dict, got {type(task_or_payload).__name__}"
            )

        if task.id in self._tasks:
            if self._tasks[task.id] is not task:
                raise ValueError(f"A different task with id {task.id!r} already exists")
            return task

        self._register_task(task)
        return task

    # ------------------------------------------------------------------
    # Public: retrieval
    # ------------------------------------------------------------------

    def get_goal(self, goal_id: str) -> Goal:
        try:
            return self._goals[goal_id]
        except KeyError:
            raise KeyError(f"No goal with id {goal_id!r}")

    def get_task(self, task_id: str) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError:
            raise KeyError(f"No task with id {task_id!r}")

    def get_goals(self, **filters) -> list[Goal]:
        return filter_items(list(self._goals.values()), **filters)

    def get_tasks(self, **filters) -> list[Task]:
        return filter_items(list(self._tasks.values()), **filters)

    # ------------------------------------------------------------------
    # Public: events / history
    # ------------------------------------------------------------------

    def get_events(
        self,
        entity_id: str | None = None,
        event_type: str | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        events = self._events
        if entity_id:
            events = [e for e in events if e.entity_id == entity_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        events = list(reversed(events))  # newest first
        if limit is not None:
            events = events[:limit]
        return events

    def recent(self, limit: int = 20) -> list[Event]:
        return self.get_events(limit=limit)

    # ------------------------------------------------------------------
    # Public: rendering helpers (delegated to _views)
    # ------------------------------------------------------------------

    def board(self, goal_id: str | None = None, **filters) -> dict:
        from taskatlas._views import render_board
        return render_board(self, goal_id=goal_id, **filters)

    def tree(self) -> dict:
        from taskatlas._views import render_tree
        return render_tree(self)

    def queue(self, goal_id: str | None = None, limit: int | None = None) -> list[dict]:
        from taskatlas._views import render_queue
        return render_queue(self, goal_id=goal_id, limit=limit)

    def summary(self) -> dict:
        from taskatlas._views import render_summary
        return render_summary(self)

    # ------------------------------------------------------------------
    # Public: serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": _SCHEMA_VERSION,
            "name": self.name,
            "meta": dict(self.meta),
            "task_stages": list(self.task_stages),
            "goal_statuses": list(self.goal_statuses),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "goals": {gid: g.to_dict() for gid, g in self._goals.items()},
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
            "links": {lid: lk.to_dict() for lid, lk in self._links.items()},
            "events": [e.to_dict() for e in self._events],
        }

    def save(self, path: str) -> None:
        """Serialize the atlas to a JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> Atlas:
        """Load an atlas from a JSON file."""
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_dict(cls, payload: dict) -> Atlas:
        if not isinstance(payload, dict):
            raise ValueError(
                f"Invalid atlas data: expected dict, got {type(payload).__name__}"
            )
        if "version" not in payload:
            warnings.warn(
                "Atlas data has no 'version' key — assuming legacy format.",
                stacklevel=2,
            )

        try:
            atlas = cls({
                "name": payload.get("name", ""),
                "meta": payload.get("meta", {}),
                "task_stages": payload.get("task_stages", list(DEFAULT_TASK_STAGES)),
                "goal_statuses": payload.get("goal_statuses", list(DEFAULT_GOAL_STATUSES)),
                "created_at": payload.get("created_at"),
                "updated_at": payload.get("updated_at"),
            })

            atlas._events = [Event.from_dict(e) for e in payload.get("events", [])]

            for lid, ldata in payload.get("links", {}).items():
                atlas._links[lid] = Link.from_dict(ldata)

            for gid, gdata in payload.get("goals", {}).items():
                goal = Goal.from_dict(gdata)
                atlas._goals[gid] = goal
                goal._atlas = atlas

            for tid, tdata in payload.get("tasks", {}).items():
                task = Task.from_dict(tdata)
                atlas._tasks[tid] = task
                task._atlas = atlas

        except (KeyError, TypeError) as exc:
            raise ValueError(f"Invalid atlas data: {exc}") from exc

        return atlas

    def __repr__(self) -> str:
        return (
            f"Atlas(name={self.name!r}, "
            f"goals={len(self._goals)}, "
            f"tasks={len(self._tasks)})"
        )
