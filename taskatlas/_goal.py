"""Goal — a higher-order intended outcome."""

from __future__ import annotations

from taskatlas._base import _WorkItem, _parse_payload
from taskatlas._task import Task
from taskatlas._types import DEFAULT_GOAL_STATUSES


class Goal(_WorkItem):
    """A higher-order intended outcome that tasks work toward."""

    _entity_type = "goal"
    _id_prefix = "g"

    def __init__(self, payload: dict | None = None, **kwargs) -> None:
        opts = _parse_payload(payload, kwargs)
        status = opts.pop("status", "proposed")
        parent_goal_id = opts.pop("parent_goal_id", None)
        child_goal_ids = opts.pop("child_goal_ids", None)
        task_ids = opts.pop("task_ids", None)

        super().__init__(opts)

        allowed = self._allowed_statuses()
        if status not in allowed:
            raise ValueError(
                f"Invalid status {status!r}. Must be one of {list(allowed)}"
            )

        self._status: str = status
        self.parent_goal_id: str | None = parent_goal_id
        self.child_goal_ids: list[str] = list(child_goal_ids or [])
        self.task_ids: list[str] = list(task_ids or [])

    def _allowed_statuses(self) -> tuple[str, ...]:
        if self._atlas is not None:
            return self._atlas.goal_statuses
        return DEFAULT_GOAL_STATUSES

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        allowed = self._allowed_statuses()
        if value not in allowed:
            raise ValueError(
                f"Invalid status {value!r}. Must be one of {list(allowed)}"
            )
        old = self._status
        self._status = value
        if old != value:
            self._touch()
            self._emit("goal_status_changed", old_status=old, new_status=value)

    def set_status(self, status: str, reason: str | None = None) -> None:
        allowed = self._allowed_statuses()
        if status not in allowed:
            raise ValueError(
                f"Invalid status {status!r}. Must be one of {list(allowed)}"
            )
        old = self._status
        if old == status:
            return
        self._status = status
        self._touch()
        self._emit("goal_status_changed", reason=reason, old_status=old, new_status=status)

    # ------------------------------------------------------------------
    # Task attachment
    # ------------------------------------------------------------------

    def add_task(self, task_or_payload) -> Task:
        """Attach a task to this goal.

        Accepts a Task instance or dict payload (creates a new Task).
        Also registers the task in the atlas if this goal is registered.
        """
        if isinstance(task_or_payload, dict):
            task = Task(task_or_payload)
        elif isinstance(task_or_payload, Task):
            task = task_or_payload
        else:
            raise TypeError(
                f"Expected Task or dict, got {type(task_or_payload).__name__}"
            )

        if task.id not in self.task_ids:
            self.task_ids.append(task.id)
        if self.id not in task.goal_ids:
            task.goal_ids.append(self.id)

        if self._atlas is not None:
            self._atlas._register_task(task)

        self._touch()
        self._emit("task_attached_to_goal", task_id=task.id)
        return task

    def attach_task(self, task_or_id) -> None:
        """Explicitly attach an existing task by instance or ID."""
        if isinstance(task_or_id, Task):
            task = task_or_id
        elif isinstance(task_or_id, str):
            if self._atlas is None:
                raise ValueError(
                    "Cannot attach by ID when goal is not registered in an Atlas"
                )
            task = self._atlas.get_task(task_or_id)
        else:
            raise TypeError(
                f"Expected Task or str ID, got {type(task_or_id).__name__}"
            )

        if task.id not in self.task_ids:
            self.task_ids.append(task.id)
        if self.id not in task.goal_ids:
            task.goal_ids.append(self.id)

        self._touch()
        self._emit("task_attached_to_goal", task_id=task.id)

    def detach_task(self, task_or_id) -> None:
        """Detach a task from this goal.

        No-op if the task is not currently attached.
        """
        if isinstance(task_or_id, Task):
            tid = task_or_id.id
            task = task_or_id
        elif isinstance(task_or_id, str):
            tid = task_or_id
            task = self._atlas._tasks.get(tid) if self._atlas else None
        else:
            raise TypeError(
                f"Expected Task or str ID, got {type(task_or_id).__name__}"
            )

        if tid not in self.task_ids:
            return

        self.task_ids.remove(tid)
        if task is not None and self.id in task.goal_ids:
            task.goal_ids.remove(self.id)

        self._touch()
        self._emit("task_detached_from_goal", task_id=tid)

    def get_tasks(self) -> list[Task]:
        """Return all tasks attached to this goal."""
        if self._atlas is None:
            return []
        return [
            self._atlas._tasks[tid]
            for tid in self.task_ids
            if tid in self._atlas._tasks
        ]

    # ------------------------------------------------------------------
    # Subgoals
    # ------------------------------------------------------------------

    def add_goal(self, goal_or_payload) -> Goal:
        """Add a subgoal under this goal."""
        if isinstance(goal_or_payload, dict):
            child = Goal(goal_or_payload)
        elif isinstance(goal_or_payload, Goal):
            child = goal_or_payload
        else:
            raise TypeError(
                f"Expected Goal or dict, got {type(goal_or_payload).__name__}"
            )

        if child.id == self.id:
            raise ValueError("A goal cannot be its own subgoal")
        if child.parent_goal_id is not None and child.parent_goal_id != self.id:
            raise ValueError(
                f"Goal {child.id!r} already has parent {child.parent_goal_id!r}"
            )

        child.parent_goal_id = self.id
        if child.id not in self.child_goal_ids:
            self.child_goal_ids.append(child.id)

        if self._atlas is not None:
            self._atlas._register_goal(child)

        self._touch()
        self._emit("subgoal_added", child_id=child.id)
        return child

    def detach_goal(self, goal_or_id) -> None:
        """Detach a subgoal from this goal.

        Clears the parent-child relationship but does NOT remove the child
        from the atlas.
        """
        if isinstance(goal_or_id, Goal):
            child = goal_or_id
            cid = child.id
        elif isinstance(goal_or_id, str):
            cid = goal_or_id
            child = self._atlas._goals.get(cid) if self._atlas else None
        else:
            raise TypeError(
                f"Expected Goal or str ID, got {type(goal_or_id).__name__}"
            )

        if cid not in self.child_goal_ids:
            return

        self.child_goal_ids.remove(cid)
        if child is not None and child.parent_goal_id == self.id:
            child.parent_goal_id = None

        self._touch()
        self._emit("subgoal_detached", child_id=cid)

    def get_goals(self) -> list[Goal]:
        """Return direct child goals."""
        if self._atlas is None:
            return []
        return [
            self._atlas._goals[cid]
            for cid in self.child_goal_ids
            if cid in self._atlas._goals
        ]

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    def progress(self) -> dict:
        """Return a lightweight progress summary over attached tasks."""
        tasks = self.get_tasks()
        by_stage: dict[str, int] = {}
        for t in tasks:
            by_stage[t.stage] = by_stage.get(t.stage, 0) + 1

        total = len(tasks)
        done = by_stage.get("done", 0)
        return {
            "goal_id": self.id,
            "task_count": total,
            "by_stage": by_stage,
            "done_count": done,
            "blocked_count": by_stage.get("blocked", 0),
            "active_count": by_stage.get("active", 0),
            "done_ratio": done / total if total else 0.0,
        }

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def context(self, mode: str = "compact") -> dict:
        if mode not in ("compact", "full"):
            raise ValueError(
                f"Invalid context mode {mode!r}. Must be 'compact' or 'full'"
            )
        ctx: dict = {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "tags": self.tags,
        }
        if mode == "full":
            ctx.update({
                "summary": self.summary,
                "parent_goal_id": self.parent_goal_id,
                "child_goal_ids": self.child_goal_ids,
                "task_ids": self.task_ids,
                "links": [lk.to_dict() for lk in self.get_links()],
                "progress": self.progress(),
                "notes": self.notes[-5:],
                "recent_events": [e.to_dict() for e in self.history(limit=10)],
            })
        else:
            if self.task_ids:
                ctx["task_count"] = len(self.task_ids)
            if self.child_goal_ids:
                ctx["subgoal_count"] = len(self.child_goal_ids)
            if self.notes:
                ctx["latest_note"] = self.notes[-1]["text"]
        return ctx

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = self._base_to_dict()
        d.update({
            "status": self.status,
            "parent_goal_id": self.parent_goal_id,
            "child_goal_ids": list(self.child_goal_ids),
            "task_ids": list(self.task_ids),
        })
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Goal:
        goal = cls({
            "id": data["id"],
            "title": data.get("title", ""),
            "summary": data.get("summary", ""),
            "status": data.get("status", "proposed"),
            "priority": data.get("priority", "medium"),
            "tags": data.get("tags", []),
            "meta": data.get("meta", {}),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "parent_goal_id": data.get("parent_goal_id"),
            "child_goal_ids": data.get("child_goal_ids", []),
            "task_ids": data.get("task_ids", []),
        })
        goal._base_load(data)
        return goal
