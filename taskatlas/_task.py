"""Task - an executable unit of work with stages, claims, holds, and receipts."""

import copy

from taskatlas._base import (
    _FACTORY_TOKEN,
    _CausalWorkItem,
    _check_unknown_keys,
    _entity_stub,
    _now,
    _parse_options,
)
from taskatlas._types import TASK_STAGES, TERMINAL_TASK_STAGES


def _validate_receipt(raw_result):
    """Validate and deep-copy a serialized completion/cancellation receipt."""
    if raw_result is None:
        return None
    if not isinstance(raw_result, dict):
        raise TypeError("result receipt must be a dict or None")
    copied = copy.deepcopy(raw_result)
    copied.setdefault("status", "done")
    copied.setdefault("summary", "")
    copied.setdefault("artifacts", [])
    copied.setdefault("data", {})
    return copied


class Task(_CausalWorkItem):
    """An actionable work unit that moves through stages and produces receipts.

    Tasks support hierarchical subtask decomposition, attachment to one or more
    Goals, causal ``depends_on`` links, non-destructive external holds
    (``hold()`` / ``unhold()``), multi-worker ownership claims (``claim()`` /
    ``release()``), and structured completion receipts (``complete()`` /
    ``cancel()``) that propagate automatically into downstream task context.
    """

    _entity_type = "task"
    _id_prefix = "t"
    _ALLOWED_KEYS = _CausalWorkItem._BASE_KEYS | frozenset({
        "stage",
        "parent_task_id",
        "goal_ids",
        "owner",
        "hold_reason",
        "result",
    })

    def __init__(self, atlas=None, opts=None, *, _token=None, **kwargs):
        if _token is not _FACTORY_TOKEN or atlas is None:
            super().__init__(atlas, opts, _token=_token, **kwargs)
        opts = opts or {}
        _check_unknown_keys(opts, self._ALLOWED_KEYS, "Task")
        stage = opts.get("stage", "inbox")
        if stage not in TASK_STAGES:
            raise ValueError(
                f"Invalid task stage {stage!r}. Must be one of {list(TASK_STAGES)}"
            )
        owner = opts.get("owner")
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            raise ValueError("owner must be a non-empty string or None")

        result = _validate_receipt(opts.get("result"))
        raw_goal_ids = opts.get("goal_ids") or []
        if isinstance(raw_goal_ids, str) or not isinstance(
            raw_goal_ids, (list, tuple, set)
        ):
            raise TypeError("goal_ids must be a list, tuple, or set of Goal IDs")
        deduped_goal_ids = []
        for gid in raw_goal_ids:
            if gid not in deduped_goal_ids:
                deduped_goal_ids.append(gid)

        super().__init__(atlas, opts, _token=_token)
        self._stage = stage
        self._parent_task_id = opts.get("parent_task_id")
        self._child_task_ids = []
        self._goal_ids = deduped_goal_ids
        self._owner = owner
        self._result = result

        if stage in TERMINAL_TASK_STAGES and self._result is None:
            self._result = {
                "status": stage,
                "summary": "",
                "artifacts": [],
                "data": {},
                "completed_at": self._updated_at,
            }

    def _is_satisfied(self):
        return self._stage == "done"

    def _is_terminal(self):
        return self._stage in TERMINAL_TASK_STAGES

    # ------------------------------------------------------------------
    # Stage transitions and completion/cancellation receipts
    # ------------------------------------------------------------------

    @property
    def stage(self):
        return self._stage

    @stage.setter
    def stage(self, value):
        raise AttributeError(
            "Cannot assign to 'stage' directly; "
            "use move(stage, reason=...), complete(...), or cancel(...)"
        )

    @property
    def result(self):
        """Return a copy of the completion/cancellation receipt dict, or None."""
        if self._result is None:
            return None
        return copy.deepcopy(self._result)

    @result.setter
    def result(self, value):
        raise AttributeError(
            "Cannot assign to 'result' directly; use complete(...) or cancel(...)"
        )

    def move(self, stage, reason=None, *, actor=None):
        """Move this Task to a workflow stage and emit ``task_stage_changed``."""
        if stage not in TASK_STAGES:
            raise ValueError(
                f"Invalid task stage {stage!r}. Must be one of {list(TASK_STAGES)}"
            )
        if self._stage == stage:
            return

        old = self._stage
        self._stage = stage
        resolved_actor = self._resolve_actor(actor)
        now = _now()

        if stage in TERMINAL_TASK_STAGES:
            self._hold_reason = None
            self._owner = None
            self._result = {
                "status": stage,
                "summary": reason or "",
                "artifacts": [],
                "data": {},
                "completed_at": now,
            }
            if resolved_actor is not None:
                self._result["actor"] = resolved_actor
        elif old in TERMINAL_TASK_STAGES:
            # Reopening a terminal task clears its prior terminal receipt
            self._result = None

        self._updated_at = now
        self._emit(
            "task_stage_changed",
            reason=reason,
            actor=resolved_actor,
            old_stage=old,
            new_stage=stage,
        )

    def complete(
        self,
        summary="",
        *,
        artifacts=None,
        data=None,
        reason=None,
        archive=False,
        actor=None,
    ):
        """Complete this Task (`stage='done'`) and record a structured receipt.

        Downstream tasks that depend on this task automatically receive this
        receipt inside ``satisfied_dependencies`` when calling ``context()``.
        """
        if not isinstance(summary, str):
            raise TypeError("complete() summary must be a string")
        if artifacts is not None:
            if isinstance(artifacts, str) or not isinstance(artifacts, (list, tuple)):
                raise TypeError("artifacts must be a list or tuple of strings")
            for item in artifacts:
                if not isinstance(item, str) or not item.strip():
                    raise ValueError("Each artifact path/URI must be a non-empty string")
        if data is not None and not isinstance(data, dict):
            raise TypeError("complete() data must be a dict or None")

        resolved_actor = self._resolve_actor(actor)
        now = _now()
        receipt = {
            "status": "done",
            "summary": summary,
            "artifacts": list(artifacts) if artifacts else [],
            "data": copy.deepcopy(data) if data else {},
            "completed_at": now,
        }
        if resolved_actor is not None:
            receipt["actor"] = resolved_actor

        old = self._stage
        self._stage = "done"
        self._hold_reason = None
        self._owner = None
        self._result = receipt
        self._updated_at = now

        effective_reason = reason or summary or "Completed"
        self._emit(
            "task_stage_changed",
            reason=effective_reason,
            actor=resolved_actor,
            old_stage=old,
            new_stage="done",
            receipt=copy.deepcopy(receipt),
        )
        if archive:
            self.archive(reason=effective_reason, actor=resolved_actor)
        return copy.deepcopy(receipt)

    def cancel(
        self,
        reason=None,
        *,
        superseded_by=None,
        archive=False,
        actor=None,
    ):
        """Cancel this Task (`stage='canceled'`) without counting it as completed.

        Canceled tasks are excluded from active ``Goal.progress()`` denominators
        so dropping obsolete work never stalls goal completion percentages.
        """
        if superseded_by is not None:
            if hasattr(superseded_by, "id"):
                superseded_by = superseded_by.id
            if not isinstance(superseded_by, str) or not superseded_by.strip():
                raise ValueError("superseded_by must be a task ID or Task instance")

        resolved_actor = self._resolve_actor(actor)
        now = _now()
        effective_reason = reason or "Canceled"
        receipt = {
            "status": "canceled",
            "summary": effective_reason,
            "artifacts": [],
            "data": {},
            "completed_at": now,
        }
        if superseded_by is not None:
            receipt["superseded_by"] = superseded_by
        if resolved_actor is not None:
            receipt["actor"] = resolved_actor

        old = self._stage
        self._stage = "canceled"
        self._hold_reason = None
        self._owner = None
        self._result = receipt
        self._updated_at = now

        self._emit(
            "task_stage_changed",
            reason=effective_reason,
            actor=resolved_actor,
            old_stage=old,
            new_stage="canceled",
            receipt=copy.deepcopy(receipt),
        )
        if archive:
            self.archive(reason=effective_reason, actor=resolved_actor)
        return copy.deepcopy(receipt)

    # ------------------------------------------------------------------
    # Worker ownership claims (multi-agent coordination)
    # ------------------------------------------------------------------

    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value):
        raise AttributeError(
            "Cannot assign to 'owner' directly; use claim(owner) or release()"
        )

    def claim(self, owner=None, *, move_active=False, reason=None, actor=None):
        """Claim exclusive worker ownership of this Task.

        Raises ``ValueError`` if the Task is terminal or already claimed by a
        different owner (preventing race-like double pickup across workers).
        """
        if self._is_terminal():
            raise ValueError(f"Cannot claim terminal task {self._id!r}")

        resolved_actor = self._resolve_actor(actor)
        claimer = owner if owner is not None else resolved_actor
        if not isinstance(claimer, str) or not claimer.strip():
            raise ValueError("claim() requires a non-empty owner or active actor")

        if self._owner is not None and self._owner != claimer:
            raise ValueError(
                f"Task {self._id!r} is already claimed by {self._owner!r}; "
                f"release it before claiming for {claimer!r}"
            )

        if self._owner != claimer:
            self._owner = claimer
            self._touch()
            self._emit(
                "task_claimed",
                reason=reason,
                actor=resolved_actor or claimer,
                owner=claimer,
            )

        if move_active and self._stage in ("inbox", "ready"):
            self.move(
                "active",
                reason=reason or f"Claimed by {claimer}",
                actor=resolved_actor or claimer,
            )

    def release(self, *, reason=None, actor=None):
        """Release worker ownership on this Task so other workers can pick it up."""
        if self._owner is None:
            return
        previous = self._owner
        self._owner = None
        self._touch()
        self._emit(
            "task_released",
            reason=reason,
            actor=actor,
            previous_owner=previous,
        )

    # ------------------------------------------------------------------
    # Containment hierarchy (Task -> Subtask) & transitive lineage
    # ------------------------------------------------------------------

    @property
    def parent_task_id(self):
        return self._parent_task_id

    @property
    def child_task_ids(self):
        return tuple(self._child_task_ids)

    @property
    def goal_ids(self):
        """Direct Goal IDs this Task was explicitly attached to."""
        return tuple(self._goal_ids)

    @property
    def effective_goal_ids(self):
        """Goal IDs governing this Task directly, via parent Tasks, or ancestor Goals."""
        direct_and_task_ancestors = []
        seen_goals = set()
        for t in [self] + self.ancestor_tasks():
            for gid in t._goal_ids:
                if gid not in seen_goals and gid in self._atlas._goals:
                    seen_goals.add(gid)
                    direct_and_task_ancestors.append(gid)
                    goal = self._atlas._goals[gid]
                    for anc_goal in goal.ancestor_goals():
                        if anc_goal.id not in seen_goals:
                            seen_goals.add(anc_goal.id)
                            direct_and_task_ancestors.append(anc_goal.id)
        return tuple(direct_and_task_ancestors)

    @property
    def effective_dream_ids(self):
        """Dream IDs governing this Task through its effective Goals."""
        dreams = []
        seen = set()
        for gid in self.effective_goal_ids:
            goal = self._atlas._goals.get(gid)
            if goal is None:
                continue
            did = goal.effective_dream_id
            if did is not None and did not in seen and did in self._atlas._dreams:
                seen.add(did)
                dreams.append(did)
        return tuple(dreams)

    @property
    def effective_dream_id(self):
        """Primary Dream ID governing this Task, or None when unattached to Dreams."""
        dids = self.effective_dream_ids
        return dids[0] if dids else None

    def ancestor_tasks(self):
        """Return ancestor Tasks from immediate parent up to the root Task."""
        ancestors = []
        seen = {self._id}
        pid = self._parent_task_id
        while pid is not None and pid not in seen:
            seen.add(pid)
            parent = self._atlas._tasks.get(pid)
            if parent is None:
                break
            ancestors.append(parent)
            pid = parent._parent_task_id
        return ancestors

    def descendant_tasks(self, *, include_archived=False):
        """Return all transitive subtasks beneath this Task in pre-order."""
        descendants = []
        seen = {self._id}

        def _walk(task):
            for cid in task._child_task_ids:
                if cid in seen:
                    continue
                seen.add(cid)
                child = self._atlas._tasks.get(cid)
                if child is None:
                    continue
                if include_archived or not child.archived:
                    descendants.append(child)
                _walk(child)

        _walk(self)
        return descendants

    def add_task(self, title_or_payload=None, **kwargs):
        """Create a new subtask nested under this Task."""
        opts = _parse_options(title_or_payload, "title", kwargs, "task")
        if opts.get("parent_task_id") is not None and opts["parent_task_id"] != self._id:
            raise ValueError(
                f"Conflicting parent_task_id {opts['parent_task_id']!r} passed to "
                f"Task({self._id!r}).add_task(...)"
            )
        opts["parent_task_id"] = self._id
        return self._atlas.add_task(opts)

    def attach_task(self, task_or_id, *, reason=None, actor=None):
        """Nest an existing unparented Task as a subtask under this Task."""
        child = self._atlas._resolve_task(task_or_id)
        self._require_same_atlas(child)

        if child.id == self._id:
            raise ValueError("A task cannot be its own subtask")
        if child._parent_task_id == self._id:
            return
        if child._parent_task_id is not None:
            raise ValueError(
                f"Task {child.id!r} already has parent {child._parent_task_id!r}; "
                f"detach it first"
            )
        for anc in self.ancestor_tasks():
            if anc.id == child.id:
                raise ValueError(
                    f"Cyclic task containment detected: {child.id!r} is an ancestor "
                    f"of {self._id!r}"
                )

        child._parent_task_id = self._id
        if child.id not in self._child_task_ids:
            self._child_task_ids.append(child.id)
        child._touch()
        self._touch()
        self._emit("subtask_added", reason=reason, actor=actor, child_id=child.id)

    def detach_task(self, task_or_id, *, reason=None, actor=None):
        """Detach a direct subtask from this Task without deleting it."""
        if isinstance(task_or_id, str):
            cid = task_or_id
            child = self._atlas._tasks.get(cid)
        else:
            child = self._atlas._resolve_task(task_or_id)
            cid = child.id

        if cid not in self._child_task_ids:
            return

        self._child_task_ids.remove(cid)
        if child is not None and child._parent_task_id == self._id:
            child._parent_task_id = None
            child._touch()

        self._touch()
        self._emit("subtask_detached", reason=reason, actor=actor, child_id=cid)

    def get_tasks(self, *, recursive=False, include_archived=False):
        """Return child subtasks (direct only by default, or recursive)."""
        if recursive:
            return self.descendant_tasks(include_archived=include_archived)
        children = [
            self._atlas._tasks[cid]
            for cid in self._child_task_ids
            if cid in self._atlas._tasks
        ]
        if include_archived:
            return children
        return [c for c in children if not c.archived]

    # ------------------------------------------------------------------
    # Hydrated context (with upstream receipts & dream breadcrumb) and brief
    # ------------------------------------------------------------------

    def context(self, mode="compact"):
        """Return a hydrated situational summary for this Task."""
        if mode not in ("compact", "full"):
            raise ValueError(
                f"Invalid context mode {mode!r}. Must be 'compact' or 'full'"
            )

        ctx = {
            "id": self._id,
            "title": self._title,
            "stage": self._stage,
            "priority": self._priority,
            "is_blocked": self.is_blocked,
            "tags": list(self._tags),
        }
        if self._archived:
            ctx["archived"] = True
        if self._owner is not None:
            ctx["owner"] = self._owner
        if self.is_held:
            ctx["hold_reason"] = self._hold_reason

        parent_obj = (
            self._atlas._tasks.get(self._parent_task_id)
            if self._parent_task_id
            else None
        )
        parent_stub = _entity_stub(parent_obj) if parent_obj is not None else None

        eff_goals = [
            self._atlas._goals[gid]
            for gid in self.effective_goal_ids
            if gid in self._atlas._goals
        ]
        goal_stubs = [
            {"id": g.id, "title": g.title, "status": g.status, "priority": g.priority}
            for g in eff_goals
        ]

        dream_id = self.effective_dream_id
        dream_obj = self._atlas._dreams.get(dream_id) if dream_id else None
        dream_stub = (
            {
                "id": dream_obj.id,
                "title": dream_obj.title,
                "status": dream_obj.status,
            }
            if dream_obj is not None
            else None
        )

        unsatisfied = self.blockers()

        if mode == "compact":
            if unsatisfied:
                ctx["blocker_ids"] = [b.id for b in unsatisfied]
            if parent_stub is not None:
                ctx["parent"] = parent_stub
            if self._child_task_ids:
                ctx["subtask_count"] = len(self._child_task_ids)
            if goal_stubs:
                ctx["goals"] = [
                    {"id": g["id"], "title": g["title"], "status": g["status"]}
                    for g in goal_stubs
                ]
            if dream_stub is not None:
                ctx["dream"] = dream_stub
            if self._result and self._result.get("summary"):
                ctx["result_summary"] = self._result["summary"]
            if self._notes:
                ctx["latest_note"] = self._notes[-1]["text"]
            return ctx

        satisfied_deps = []
        for dep in self.dependencies(unsatisfied_only=False):
            if dep._is_satisfied():
                entry = _entity_stub(dep)
                if dep._entity_type == "task" and dep.result is not None:
                    entry["result"] = dep.result
                elif dep._entity_type == "goal" and dep.outcome:
                    entry["outcome"] = dep.outcome
                satisfied_deps.append(entry)

        ctx.update({
            "summary": self._summary,
            "archived": self._archived,
            "owner": self._owner,
            "hold_reason": self._hold_reason,
            "result": self.result,
            "parent": parent_stub,
            "subtasks": [
                _entity_stub(st)
                for st in self.get_tasks(recursive=False, include_archived=False)
            ],
            "goals": goal_stubs,
            "dream": dream_stub,
            "unsatisfied_blockers": [_entity_stub(b) for b in unsatisfied],
            "satisfied_dependencies": satisfied_deps,
            "unlocks": [
                _entity_stub(d) for d in self.dependents(unsatisfied_only=True)
            ],
            "related": self._related_stubs(),
            "notes": copy.deepcopy(self._notes[-5:]),
            "recent_events": [e.to_dict() for e in self.history(limit=10)],
        })
        return ctx

    def brief(self):
        """Render a token-tight Markdown briefing for this Task."""
        from taskatlas._views import render_task_brief

        return render_task_brief(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        data = self._base_to_dict()
        data.update({
            "stage": self._stage,
            "parent_task_id": self._parent_task_id,
            "child_task_ids": list(self._child_task_ids),
            "goal_ids": list(self._goal_ids),
            "owner": self._owner,
            "hold_reason": self._hold_reason,
            "result": copy.deepcopy(self._result),
        })
        return data

    @classmethod
    def _from_dict(cls, atlas, data):
        task = cls(
            atlas,
            {
                "id": data["id"],
                "title": data.get("title") or "Untitled Task",
                "summary": data.get("summary", ""),
                "stage": data.get("stage", "inbox"),
                "priority": data.get("priority", "medium"),
                "tags": data.get("tags", []),
                "meta": data.get("meta", {}),
                "archived": data.get("archived", False),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "parent_task_id": data.get("parent_task_id"),
                "goal_ids": data.get("goal_ids", []),
                "owner": data.get("owner"),
                "hold_reason": data.get("hold_reason"),
                "result": data.get("result"),
            },
            _token=_FACTORY_TOKEN,
        )
        task._child_task_ids = list(data.get("child_task_ids", []))
        task._base_load(data)
        return task
