"""Goal - a convergent, falsifiable outcome that Tasks work toward."""

import copy

from taskatlas._base import (
    _FACTORY_TOKEN,
    _CausalWorkItem,
    _check_unknown_keys,
    _entity_stub,
    _parse_options,
)
from taskatlas._types import GOAL_STATUSES, TERMINAL_GOAL_STATUSES


def _normalize_criteria(raw_criteria):
    """Validate and deduplicate acceptance criteria strings."""
    if raw_criteria is None:
        return []
    if isinstance(raw_criteria, str) or not isinstance(
        raw_criteria, (list, tuple)
    ):
        raise TypeError("criteria must be a list or tuple of non-empty strings")
    cleaned = []
    for item in raw_criteria:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Each criterion must be a non-empty string")
        if item not in cleaned:
            cleaned.append(item)
    return cleaned


class Goal(_CausalWorkItem):
    """A concrete, falsifiable intended outcome.

    Goals sit between optional ``Dream`` visions above and executable ``Task``
    units below. They support subgoal hierarchies, acceptance ``criteria``, an
    ``outcome`` summary upon completion/abandonment, causal ``depends_on``
    relationships, external holds, and transitive leaf-task progress calculation.
    """

    _entity_type = "goal"
    _id_prefix = "g"
    _ALLOWED_KEYS = _CausalWorkItem._BASE_KEYS | frozenset({
        "status",
        "dream_id",
        "parent_goal_id",
        "criteria",
        "outcome",
        "hold_reason",
    })

    def __init__(self, atlas=None, opts=None, *, _token=None, **kwargs):
        if _token is not _FACTORY_TOKEN or atlas is None:
            super().__init__(atlas, opts, _token=_token, **kwargs)
        opts = opts or {}
        _check_unknown_keys(opts, self._ALLOWED_KEYS, "Goal")
        status = opts.get("status", "proposed")
        if status not in GOAL_STATUSES:
            raise ValueError(
                f"Invalid goal status {status!r}. "
                f"Must be one of {list(GOAL_STATUSES)}"
            )
        criteria = _normalize_criteria(opts.get("criteria"))
        outcome = opts.get("outcome", "") or ""
        if not isinstance(outcome, str):
            raise TypeError("outcome must be a string")

        super().__init__(atlas, opts, _token=_token)
        self._status = status
        self._dream_id = opts.get("dream_id")
        self._parent_goal_id = opts.get("parent_goal_id")
        self._child_goal_ids = []
        self._task_ids = []
        self._criteria = criteria
        self._outcome = outcome

    def _is_satisfied(self):
        return self._status == "achieved"

    def _is_terminal(self):
        return self._status in TERMINAL_GOAL_STATUSES

    # ------------------------------------------------------------------
    # Lifecycle status, criteria, and outcome
    # ------------------------------------------------------------------

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        raise AttributeError(
            "Cannot assign to 'status' directly; "
            "use set_status(status, reason=...), achieve(...), or abandon(...)"
        )

    def set_status(self, status, reason=None, *, outcome=None, actor=None):
        """Transition this Goal's status and emit ``goal_status_changed``."""
        if status not in GOAL_STATUSES:
            raise ValueError(
                f"Invalid goal status {status!r}. "
                f"Must be one of {list(GOAL_STATUSES)}"
            )
        if outcome is not None:
            if not isinstance(outcome, str):
                raise TypeError("outcome must be a string")
            self._outcome = outcome

        if self._status == status and outcome is None:
            return

        old = self._status
        self._status = status
        if status in TERMINAL_GOAL_STATUSES:
            self._hold_reason = None
        self._touch()
        event_data = {"old_status": old, "new_status": status}
        if outcome is not None:
            event_data["outcome"] = outcome
        self._emit("goal_status_changed", reason=reason, actor=actor, **event_data)

    def achieve(self, outcome="", *, reason=None, archive=False, actor=None):
        """Mark this Goal as ``achieved`` with an optional outcome summary."""
        effective_reason = reason or outcome or "Goal achieved"
        self.set_status(
            "achieved",
            reason=effective_reason,
            outcome=outcome if outcome else None,
            actor=actor,
        )
        if archive:
            self.archive(reason=effective_reason, actor=actor)

    def abandon(self, reason=None, *, outcome="", archive=False, actor=None):
        """Mark this Goal as ``abandoned`` so it is distinguished from completion."""
        effective_reason = reason or outcome or "Goal abandoned"
        self.set_status(
            "abandoned",
            reason=effective_reason,
            outcome=outcome if outcome else None,
            actor=actor,
        )
        if archive:
            self.archive(reason=effective_reason, actor=actor)

    @property
    def criteria(self):
        """Return verifiable acceptance criteria as an immutable tuple."""
        return tuple(self._criteria)

    @criteria.setter
    def criteria(self, value):
        raise AttributeError(
            "Cannot assign to 'criteria' directly; "
            "use add_criterion(text) or remove_criterion(text)"
        )

    def add_criterion(self, text, *, actor=None):
        """Append a falsifiable acceptance criterion (idempotent)."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Criterion must be a non-empty string")
        if text in self._criteria:
            return
        self._criteria.append(text)
        self._touch()
        self._emit("criterion_added", actor=actor, criterion=text)

    def remove_criterion(self, text, *, actor=None):
        """Remove an existing acceptance criterion."""
        if text not in self._criteria:
            raise ValueError(f"Criterion {text!r} not present on {self._id!r}")
        self._criteria.remove(text)
        self._touch()
        self._emit("criterion_removed", actor=actor, criterion=text)

    @property
    def outcome(self):
        return self._outcome

    @outcome.setter
    def outcome(self, value):
        raise AttributeError(
            "Cannot assign to 'outcome' directly; "
            "use set_outcome(text, reason=...) or achieve(outcome=...)"
        )

    def set_outcome(self, outcome, reason=None, *, actor=None):
        """Record or revise the outcome summary for this Goal."""
        if not isinstance(outcome, str):
            raise TypeError("outcome must be a string")
        if self._outcome == outcome:
            return
        old = self._outcome
        self._outcome = outcome
        self._touch()
        self._emit("outcome_changed", reason=reason, actor=actor, old=old, new=outcome)

    # ------------------------------------------------------------------
    # Lineage properties (Dream <-> Goal <-> Subgoal)
    # ------------------------------------------------------------------

    @property
    def dream_id(self):
        """Direct Dream ID on root goals, or None."""
        return self._dream_id

    @property
    def effective_dream_id(self):
        """Dream ID governing this Goal directly or inherited via ancestor Goals."""
        curr = self
        visited = set()
        while curr is not None and curr.id not in visited:
            visited.add(curr.id)
            if curr._dream_id is not None:
                return curr._dream_id
            if curr._parent_goal_id is None:
                return None
            curr = self._atlas._goals.get(curr._parent_goal_id)
        return None

    @property
    def parent_goal_id(self):
        return self._parent_goal_id

    @property
    def child_goal_ids(self):
        return tuple(self._child_goal_ids)

    @property
    def task_ids(self):
        return tuple(self._task_ids)

    def ancestor_goals(self):
        """Return ancestor Goals from immediate parent up to the root Goal."""
        ancestors = []
        seen = {self._id}
        pid = self._parent_goal_id
        while pid is not None and pid not in seen:
            seen.add(pid)
            parent = self._atlas._goals.get(pid)
            if parent is None:
                break
            ancestors.append(parent)
            pid = parent._parent_goal_id
        return ancestors

    def descendant_goals(self, *, include_archived=False):
        """Return all transitive subgoals beneath this Goal in pre-order."""
        descendants = []
        seen = {self._id}

        def _walk(goal):
            for cid in goal._child_goal_ids:
                if cid in seen:
                    continue
                seen.add(cid)
                child = self._atlas._goals.get(cid)
                if child is None:
                    continue
                if include_archived or not child.archived:
                    descendants.append(child)
                _walk(child)

        _walk(self)
        return descendants

    # ------------------------------------------------------------------
    # Subgoal management
    # ------------------------------------------------------------------

    def add_goal(self, title_or_payload=None, **kwargs):
        """Create a new subgoal nested under this Goal."""
        opts = _parse_options(title_or_payload, "title", kwargs, "goal")
        if opts.get("dream_id") is not None:
            raise ValueError(
                "Subgoals inherit their parent Goal's Dream; "
                "do not pass dream_id to goal.add_goal(...)"
            )
        if opts.get("parent_goal_id") is not None and opts["parent_goal_id"] != self._id:
            raise ValueError(
                f"Conflicting parent_goal_id {opts['parent_goal_id']!r} passed to "
                f"Goal({self._id!r}).add_goal(...)"
            )
        opts["parent_goal_id"] = self._id
        return self._atlas.add_goal(opts)

    def attach_goal(self, goal_or_id, *, reason=None, actor=None):
        """Nest an existing unparented Goal as a subgoal under this Goal."""
        child = self._atlas._resolve_goal(goal_or_id)
        self._require_same_atlas(child)

        if child.id == self._id:
            raise ValueError("A goal cannot be its own subgoal")
        if child._parent_goal_id == self._id:
            return
        if child._parent_goal_id is not None:
            raise ValueError(
                f"Goal {child.id!r} already has parent {child._parent_goal_id!r}; "
                f"detach it first"
            )
        for anc in self.ancestor_goals():
            if anc.id == child.id:
                raise ValueError(
                    f"Cyclic goal containment detected: {child.id!r} is an ancestor "
                    f"of {self._id!r}"
                )

        if child._dream_id is not None:
            if child._dream_id != self.effective_dream_id:
                raise ValueError(
                    f"Goal {child.id!r} belongs to Dream {child._dream_id!r}, "
                    f"which conflicts with parent Goal Dream {self.effective_dream_id!r}"
                )
            # Cleanly promote under parent so child does not appear twice under the Dream
            dream = self._atlas._dreams.get(child._dream_id)
            if dream is not None:
                dream.detach_goal(child, reason="Nested as subgoal under same Dream", actor=actor)

        child._parent_goal_id = self._id
        if child.id not in self._child_goal_ids:
            self._child_goal_ids.append(child.id)
        child._touch()
        self._touch()
        self._emit("subgoal_added", reason=reason, actor=actor, child_id=child.id)

    def detach_goal(self, goal_or_id, *, reason=None, actor=None):
        """Detach a direct subgoal from this Goal without deleting it."""
        if isinstance(goal_or_id, str):
            cid = goal_or_id
            child = self._atlas._goals.get(cid)
        else:
            child = self._atlas._resolve_goal(goal_or_id)
            cid = child.id

        if cid not in self._child_goal_ids:
            return

        self._child_goal_ids.remove(cid)
        if child is not None and child._parent_goal_id == self._id:
            child._parent_goal_id = None
            child._touch()

        self._touch()
        self._emit("subgoal_detached", reason=reason, actor=actor, child_id=cid)

    def get_goals(self, *, recursive=False, include_archived=False):
        """Return child subgoals (direct only by default, or recursive)."""
        if recursive:
            return self.descendant_goals(include_archived=include_archived)
        children = [
            self._atlas._goals[cid]
            for cid in self._child_goal_ids
            if cid in self._atlas._goals
        ]
        if include_archived:
            return children
        return [c for c in children if not c.archived]

    # ------------------------------------------------------------------
    # Task attachment and transitive scope
    # ------------------------------------------------------------------

    def add_task(self, title_or_payload=None, **kwargs):
        """Create a new Task and attach it directly to this Goal."""
        opts = _parse_options(title_or_payload, "title", kwargs, "task")
        existing_goal_ids = list(opts.get("goal_ids") or [])
        if self._id not in existing_goal_ids:
            existing_goal_ids.append(self._id)
        opts["goal_ids"] = existing_goal_ids
        return self._atlas.add_task(opts)

    def attach_task(self, task_or_id, *, reason=None, actor=None):
        """Attach an existing Task in the same Atlas to this Goal."""
        task = self._atlas._resolve_task(task_or_id)
        self._require_same_atlas(task)

        if task.id in self._task_ids:
            return

        self._task_ids.append(task.id)
        if self._id not in task._goal_ids:
            task._goal_ids.append(self._id)
        task._touch()
        self._touch()
        self._emit(
            "task_attached_to_goal",
            reason=reason,
            actor=actor,
            task_id=task.id,
        )

    def detach_task(self, task_or_id, *, reason=None, actor=None):
        """Detach a Task from this Goal without deleting the Task."""
        if isinstance(task_or_id, str):
            tid = task_or_id
            task = self._atlas._tasks.get(tid)
        else:
            task = self._atlas._resolve_task(task_or_id)
            tid = task.id

        if tid not in self._task_ids:
            return

        self._task_ids.remove(tid)
        if task is not None and self._id in task._goal_ids:
            task._goal_ids.remove(self._id)
            task._touch()

        self._touch()
        self._emit(
            "task_detached_from_goal",
            reason=reason,
            actor=actor,
            task_id=tid,
        )

    def get_tasks(self, *, recursive=False, include_archived=False):
        """Return Tasks attached to this Goal (direct or transitive)."""
        if recursive:
            return self.scope_tasks(
                recursive=True,
                leaves_only=False,
                include_archived=include_archived,
            )
        direct = [
            self._atlas._tasks[tid]
            for tid in self._task_ids
            if tid in self._atlas._tasks
        ]
        if include_archived:
            return direct
        return [t for t in direct if not t.archived]

    def scope_tasks(self, *, recursive=True, leaves_only=False, include_archived=True):
        """Return deduplicated Tasks in this Goal's scope.

        When ``recursive=True``, walks both descendant subgoals and descendant
        subtasks so hierarchical decomposition never hides work or double-counts
        a child task that was also attached directly to the Goal.
        """
        goals_in_scope = [self]
        if recursive:
            goals_in_scope.extend(self.descendant_goals(include_archived=True))

        tasks = []
        seen = set()

        def _collect_task_tree(task):
            if task.id not in seen:
                seen.add(task.id)
                if include_archived or not task.archived:
                    tasks.append(task)
            if recursive:
                for cid in task._child_task_ids:
                    child = self._atlas._tasks.get(cid)
                    if child is not None:
                        _collect_task_tree(child)

        for g in goals_in_scope:
            for tid in g._task_ids:
                t = self._atlas._tasks.get(tid)
                if t is not None:
                    _collect_task_tree(t)

        if leaves_only:
            tasks = [t for t in tasks if not t._child_task_ids]

        return tasks

    # ------------------------------------------------------------------
    # Transitive leaf-based progress
    # ------------------------------------------------------------------

    def progress(self):
        """Compute completion metrics across transitive leaf Tasks in scope.

        - Container parent tasks delegate progress to their leaf subtasks.
        - ``canceled`` tasks are reported in ``canceled_count`` and excluded from
          the active ``task_count`` denominator so dropping obsolete work never
          locks ``done_ratio`` below ``1.0``.
        - ``archived`` completed tasks still retain ``stage == 'done'`` and
          remain counted toward completion.
        """
        leaves = self.scope_tasks(
            recursive=True,
            leaves_only=True,
            include_archived=True,
        )
        by_stage = {}
        for t in leaves:
            by_stage[t.stage] = by_stage.get(t.stage, 0) + 1

        canceled = by_stage.get("canceled", 0)
        effective_total = len(leaves) - canceled
        done = by_stage.get("done", 0)
        blocked = sum(1 for t in leaves if t.is_blocked)
        held = sum(1 for t in leaves if t.is_held)

        return {
            "goal_id": self._id,
            "task_count": effective_total,
            "canceled_count": canceled,
            "by_stage": by_stage,
            "done_count": done,
            "active_count": by_stage.get("active", 0),
            "review_count": by_stage.get("review", 0),
            "blocked_count": blocked,
            "held_count": held,
            "done_ratio": done / effective_total if effective_total else 0.0,
        }

    # ------------------------------------------------------------------
    # Hydrated context and Markdown brief
    # ------------------------------------------------------------------

    def context(self, mode="compact"):
        """Return a hydrated situational summary for this Goal."""
        if mode not in ("compact", "full"):
            raise ValueError(
                f"Invalid context mode {mode!r}. Must be 'compact' or 'full'"
            )

        prog = self.progress()
        ctx = {
            "id": self._id,
            "title": self._title,
            "status": self._status,
            "priority": self._priority,
            "is_blocked": self.is_blocked,
            "tags": list(self._tags),
        }
        if self._archived:
            ctx["archived"] = True
        if self.is_held:
            ctx["hold_reason"] = self._hold_reason

        eff_dream_id = self.effective_dream_id
        dream_obj = self._atlas._dreams.get(eff_dream_id) if eff_dream_id else None
        dream_stub = (
            {
                "id": dream_obj.id,
                "title": dream_obj.title,
                "status": dream_obj.status,
            }
            if dream_obj is not None
            else None
        )

        parent_obj = (
            self._atlas._goals.get(self._parent_goal_id)
            if self._parent_goal_id
            else None
        )
        parent_stub = _entity_stub(parent_obj) if parent_obj is not None else None

        if mode == "compact":
            if dream_stub is not None:
                ctx["dream"] = dream_stub
            if parent_stub is not None:
                ctx["parent"] = parent_stub
            if self._child_goal_ids:
                ctx["subgoal_count"] = len(self._child_goal_ids)
            if prog["task_count"] or prog["canceled_count"]:
                ctx["task_count"] = prog["task_count"]
                ctx["done_ratio"] = prog["done_ratio"]
            if self._outcome:
                ctx["outcome"] = self._outcome
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

        direct_tasks = self.get_tasks(recursive=False, include_archived=False)
        direct_ids = {t.id for t in direct_tasks}
        ctx.update({
            "summary": self._summary,
            "criteria": list(self._criteria),
            "outcome": self._outcome,
            "archived": self._archived,
            "hold_reason": self._hold_reason,
            "dream": dream_stub,
            "parent": parent_stub,
            "subgoals": [
                _entity_stub(cg)
                for cg in self.get_goals(recursive=False, include_archived=False)
            ],
            "tasks": [
                _entity_stub(t)
                for t in direct_tasks
                if t.parent_task_id is None or t.parent_task_id not in direct_ids
            ],
            "progress": prog,
            "unsatisfied_blockers": [_entity_stub(b) for b in self.blockers()],
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
        """Render a token-tight Markdown briefing for this Goal."""
        from taskatlas._views import render_goal_brief

        return render_goal_brief(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        data = self._base_to_dict()
        data.update({
            "status": self._status,
            "dream_id": self._dream_id,
            "parent_goal_id": self._parent_goal_id,
            "child_goal_ids": list(self._child_goal_ids),
            "task_ids": list(self._task_ids),
            "criteria": list(self._criteria),
            "outcome": self._outcome,
            "hold_reason": self._hold_reason,
        })
        return data

    @classmethod
    def _from_dict(cls, atlas, data):
        goal = cls(
            atlas,
            {
                "id": data["id"],
                "title": data.get("title") or "Untitled Goal",
                "summary": data.get("summary", ""),
                "status": data.get("status", "proposed"),
                "priority": data.get("priority", "medium"),
                "tags": data.get("tags", []),
                "meta": data.get("meta", {}),
                "archived": data.get("archived", False),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "dream_id": data.get("dream_id"),
                "parent_goal_id": data.get("parent_goal_id"),
                "criteria": data.get("criteria", []),
                "outcome": data.get("outcome", ""),
                "hold_reason": data.get("hold_reason"),
            },
            _token=_FACTORY_TOKEN,
        )
        goal._child_goal_ids = list(data.get("child_goal_ids", []))
        goal._task_ids = list(data.get("task_ids", []))
        goal._base_load(data)
        return goal
