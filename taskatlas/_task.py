"""Task — an actionable work unit."""

from __future__ import annotations

from taskatlas._base import _WorkItem, _parse_payload
from taskatlas._types import DEFAULT_TASK_STAGES


class Task(_WorkItem):
    """An actionable work unit that moves through stages."""

    _entity_type = "task"
    _id_prefix = "t"

    def __init__(self, payload: dict | None = None, **kwargs) -> None:
        opts = _parse_payload(payload, kwargs)
        stage = opts.pop("stage", "inbox")
        parent_task_id = opts.pop("parent_task_id", None)
        goal_ids = opts.pop("goal_ids", None)
        child_task_ids = opts.pop("child_task_ids", None)

        super().__init__(opts)

        allowed = self._allowed_stages()
        if stage not in allowed:
            raise ValueError(
                f"Invalid stage {stage!r}. Must be one of {list(allowed)}"
            )

        self._stage: str = stage
        self.parent_task_id: str | None = parent_task_id
        self.child_task_ids: list[str] = list(child_task_ids or [])
        self.goal_ids: list[str] = list(goal_ids or [])

    def _allowed_stages(self) -> tuple[str, ...]:
        if self._atlas is not None:
            return self._atlas.task_stages
        return DEFAULT_TASK_STAGES

    # ------------------------------------------------------------------
    # Stage
    # ------------------------------------------------------------------

    @property
    def stage(self) -> str:
        return self._stage

    @stage.setter
    def stage(self, value: str) -> None:
        allowed = self._allowed_stages()
        if value not in allowed:
            raise ValueError(
                f"Invalid stage {value!r}. Must be one of {list(allowed)}"
            )
        old = self._stage
        self._stage = value
        if old != value:
            self._touch()
            self._emit("task_stage_changed", old_stage=old, new_stage=value)

    def move(self, stage: str, reason: str | None = None) -> None:
        """Move this task to a new stage."""
        allowed = self._allowed_stages()
        if stage not in allowed:
            raise ValueError(
                f"Invalid stage {stage!r}. Must be one of {list(allowed)}"
            )
        old = self._stage
        if old == stage:
            return
        self._stage = stage
        self._touch()
        self._emit("task_stage_changed", reason=reason, old_stage=old, new_stage=stage)

    # ------------------------------------------------------------------
    # Subtasks
    # ------------------------------------------------------------------

    def add_task(self, task_or_payload) -> Task:
        """Add a subtask under this task.

        Accepts a Task instance or a dict payload (which creates a new Task).
        """
        if isinstance(task_or_payload, dict):
            child = Task(task_or_payload)
        elif isinstance(task_or_payload, Task):
            child = task_or_payload
        else:
            raise TypeError(
                f"Expected Task or dict, got {type(task_or_payload).__name__}"
            )

        if child.id == self.id:
            raise ValueError("A task cannot be its own subtask")
        if child.parent_task_id is not None and child.parent_task_id != self.id:
            raise ValueError(
                f"Task {child.id!r} already has parent {child.parent_task_id!r}"
            )

        child.parent_task_id = self.id
        if child.id not in self.child_task_ids:
            self.child_task_ids.append(child.id)

        if self._atlas is not None:
            self._atlas._register_task(child)

        self._touch()
        self._emit("subtask_added", child_id=child.id)
        return child

    def detach_task(self, task_or_id) -> None:
        """Detach a subtask from this task.

        Clears the parent-child relationship but does NOT remove the child
        from the atlas.
        """
        if isinstance(task_or_id, Task):
            child = task_or_id
            cid = child.id
        elif isinstance(task_or_id, str):
            cid = task_or_id
            child = self._atlas._tasks.get(cid) if self._atlas else None
        else:
            raise TypeError(
                f"Expected Task or str ID, got {type(task_or_id).__name__}"
            )

        if cid not in self.child_task_ids:
            return

        self.child_task_ids.remove(cid)
        if child is not None and child.parent_task_id == self.id:
            child.parent_task_id = None

        self._touch()
        self._emit("subtask_detached", child_id=cid)

    def get_tasks(self) -> list[Task]:
        """Return direct child tasks."""
        if self._atlas is None:
            return []
        return [
            self._atlas._tasks[cid]
            for cid in self.child_task_ids
            if cid in self._atlas._tasks
        ]

    # ------------------------------------------------------------------
    # Context
    # ------------------------------------------------------------------

    def context(self, mode: str = "compact") -> dict:
        """Return a structured situational summary."""
        if mode not in ("compact", "full"):
            raise ValueError(
                f"Invalid context mode {mode!r}. Must be 'compact' or 'full'"
            )
        ctx: dict = {
            "id": self.id,
            "title": self.title,
            "stage": self.stage,
            "priority": self.priority,
            "tags": self.tags,
        }
        if mode == "full":
            ctx.update({
                "summary": self.summary,
                "parent_task_id": self.parent_task_id,
                "child_task_ids": self.child_task_ids,
                "goal_ids": self.goal_ids,
                "links": [lk.to_dict() for lk in self.get_links()],
                "notes": self.notes[-5:],
                "recent_events": [e.to_dict() for e in self.history(limit=10)],
            })
        else:
            if self.parent_task_id:
                ctx["parent_task_id"] = self.parent_task_id
            if self.child_task_ids:
                ctx["subtask_count"] = len(self.child_task_ids)
            if self.goal_ids:
                ctx["goal_ids"] = self.goal_ids
            if self.notes:
                ctx["latest_note"] = self.notes[-1]["text"]
        return ctx

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        d = self._base_to_dict()
        d.update({
            "stage": self.stage,
            "parent_task_id": self.parent_task_id,
            "child_task_ids": list(self.child_task_ids),
            "goal_ids": list(self.goal_ids),
        })
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        task = cls({
            "id": data["id"],
            "title": data.get("title", ""),
            "summary": data.get("summary", ""),
            "stage": data.get("stage", "inbox"),
            "priority": data.get("priority", "medium"),
            "tags": data.get("tags", []),
            "meta": data.get("meta", {}),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "parent_task_id": data.get("parent_task_id"),
            "child_task_ids": data.get("child_task_ids", []),
            "goal_ids": data.get("goal_ids", []),
        })
        task._base_load(data)
        return task
