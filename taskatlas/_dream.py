"""Dream - an optional, open-horizon vision sitting above Goals."""

import copy

from taskatlas._base import (
    _FACTORY_TOKEN,
    _check_unknown_keys,
    _entity_stub,
    _parse_options,
    _WorkItem,
)
from taskatlas._types import DREAM_STATUSES, TERMINAL_TASK_STAGES


class Dream(_WorkItem):
    """An enduring vision or north star that organizes waves of Goals.

    Dreams are intentionally open-world: unlike a ``Goal`` (which converges on
    falsifiable completion criteria), a ``Dream`` evolves across multiple waves
    of goals and is evaluated by milestone momentum and stall detection rather
    than a single task completion percentage.

    Dreams are flat (no sub-dreams) and cannot attach Tasks directly; executable
    work always translates through one or more Goals.
    """

    _entity_type = "dream"
    _id_prefix = "d"
    _ALLOWED_KEYS = _WorkItem._BASE_KEYS | frozenset({
        "vision",
        "status",
    })

    def __init__(self, atlas=None, opts=None, *, _token=None, **kwargs):
        if _token is not _FACTORY_TOKEN or atlas is None:
            super().__init__(atlas, opts, _token=_token, **kwargs)
        opts = opts or {}
        _check_unknown_keys(opts, self._ALLOWED_KEYS, "Dream")
        status = opts.get("status", "seed")
        if status not in DREAM_STATUSES:
            raise ValueError(
                f"Invalid dream status {status!r}. "
                f"Must be one of {list(DREAM_STATUSES)}"
            )
        vision = opts.get("vision", "") or ""
        if not isinstance(vision, str):
            raise TypeError("vision must be a string")

        super().__init__(atlas, opts, _token=_token)
        self._status = status
        self._vision = vision
        self._goal_ids = []

    # ------------------------------------------------------------------
    # Status and vision
    # ------------------------------------------------------------------

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        raise AttributeError(
            "Cannot assign to 'status' directly; use set_status(status, reason=...)"
        )

    def set_status(self, status, reason=None, *, actor=None):
        """Transition this Dream's lifecycle status."""
        if status not in DREAM_STATUSES:
            raise ValueError(
                f"Invalid dream status {status!r}. "
                f"Must be one of {list(DREAM_STATUSES)}"
            )
        if self._status == status:
            return
        old = self._status
        self._status = status
        self._touch()
        self._emit(
            "dream_status_changed",
            reason=reason,
            actor=actor,
            old_status=old,
            new_status=status,
        )

    @property
    def vision(self):
        return self._vision

    @vision.setter
    def vision(self, value):
        raise AttributeError(
            "Cannot assign to 'vision' directly; use set_vision(vision, reason=...)"
        )

    def set_vision(self, vision, reason=None, *, actor=None):
        """Update the narrative vision statement for this Dream."""
        if not isinstance(vision, str):
            raise TypeError("vision must be a string")
        if self._vision == vision:
            return
        old = self._vision
        self._vision = vision
        self._touch()
        self._emit("vision_changed", reason=reason, actor=actor, old=old, new=vision)

    # ------------------------------------------------------------------
    # Goal containment (Dream -> Goal)
    # ------------------------------------------------------------------

    @property
    def goal_ids(self):
        """Direct top-level Goal IDs attached to this Dream."""
        return tuple(self._goal_ids)

    def add_goal(self, title_or_payload=None, **kwargs):
        """Create a new top-level Goal and attach it to this Dream."""
        opts = _parse_options(title_or_payload, "title", kwargs, "goal")
        if opts.get("dream_id") is not None and opts["dream_id"] != self._id:
            raise ValueError(
                f"Conflicting dream_id {opts['dream_id']!r} passed to "
                f"Dream({self._id!r}).add_goal(...)"
            )
        opts["dream_id"] = self._id
        return self._atlas.add_goal(opts)

    def attach_goal(self, goal_or_id, *, reason=None, actor=None):
        """Attach an existing top-level Goal to this Dream."""
        goal = self._atlas._resolve_goal(goal_or_id)
        self._require_same_atlas(goal)

        if goal.parent_goal_id is not None:
            raise ValueError(
                f"Cannot attach subgoal {goal.id!r} directly to a Dream; "
                f"attach its root Goal instead so subgoals inherit the Dream cleanly"
            )
        if goal.dream_id is not None and goal.dream_id != self._id:
            raise ValueError(
                f"Goal {goal.id!r} already belongs to Dream {goal.dream_id!r}; "
                f"detach it first"
            )
        if goal.id in self._goal_ids:
            return

        goal._dream_id = self._id
        self._goal_ids.append(goal.id)
        self._touch()
        goal._touch()
        self._emit(
            "goal_attached_to_dream",
            reason=reason,
            actor=actor,
            goal_id=goal.id,
        )

    def detach_goal(self, goal_or_id, *, reason=None, actor=None):
        """Detach a Goal from this Dream without deleting the Goal."""
        if isinstance(goal_or_id, str):
            gid = goal_or_id
            goal = self._atlas._goals.get(gid)
        else:
            goal = self._atlas._resolve_goal(goal_or_id)
            gid = goal.id

        if gid not in self._goal_ids:
            return

        self._goal_ids.remove(gid)
        if goal is not None and goal._dream_id == self._id:
            goal._dream_id = None
            goal._touch()

        self._touch()
        self._emit(
            "goal_detached_from_dream",
            reason=reason,
            actor=actor,
            goal_id=gid,
        )

    def get_goals(self, *, recursive=False, include_archived=False):
        """Return Goals under this Dream (top-level only, or transitive with subgoals)."""
        roots = [
            self._atlas._goals[gid]
            for gid in self._goal_ids
            if gid in self._atlas._goals
        ]
        if not recursive:
            if include_archived:
                return roots
            return [g for g in roots if not g.archived]

        collected = []
        seen = set()
        for root in roots:
            for item in [root] + root.descendant_goals(include_archived=True):
                if item.id in seen:
                    continue
                seen.add(item.id)
                if include_archived or not item.archived:
                    collected.append(item)
        return collected

    def scope_tasks(self, *, leaves_only=False, include_archived=True):
        """Return deduplicated Tasks across all Goals belonging to this Dream."""
        tasks = []
        seen = set()
        for goal in self.get_goals(recursive=True, include_archived=True):
            for task in goal.scope_tasks(
                recursive=True,
                leaves_only=leaves_only,
                include_archived=include_archived,
            ):
                if task.id not in seen:
                    seen.add(task.id)
                    tasks.append(task)
        return tasks

    # ------------------------------------------------------------------
    # Open-world momentum and stall detection
    # ------------------------------------------------------------------

    def progress(self):
        """Evaluate open-horizon momentum, milestone counts, and stall status.

        Unlike ``Goal.progress()``, a Dream does not pretend to know all future
        goals upfront. Instead it reports:
        - Milestone ledger across transitive goals (achieved, active, proposed, etc.)
        - Current wave task execution across *active* goals
        - Stall diagnostics when an ``active`` Dream lacks forward motion
        """
        all_goals = self.get_goals(recursive=True, include_archived=True)
        goals_by_status = {}
        for g in all_goals:
            goals_by_status[g.status] = goals_by_status.get(g.status, 0) + 1

        active_goals = [g for g in all_goals if g.status == "active" and not g.archived]
        wave_leaves = []
        seen_tasks = set()
        for ag in active_goals:
            for t in ag.scope_tasks(
                recursive=True,
                leaves_only=True,
                include_archived=True,
            ):
                if t.id not in seen_tasks:
                    seen_tasks.add(t.id)
                    wave_leaves.append(t)

        wave_effective = [t for t in wave_leaves if t.stage != "canceled"]
        wave_done = sum(1 for t in wave_effective if t.stage == "done")
        wave_open = [t for t in wave_effective if t.stage not in TERMINAL_TASK_STAGES]
        wave_blocked = sum(1 for t in wave_open if t.is_blocked)
        wave_actionable = sum(
            1 for t in wave_open if not t.is_blocked and t.stage != "review"
        )
        wave_total = len(wave_effective)

        stalled = False
        stall_reason = None
        if self._status == "active":
            if not active_goals:
                stalled = True
                stall_reason = "no_active_goals"
            elif not wave_open:
                stalled = True
                stall_reason = "no_open_tasks"
            elif wave_blocked == len(wave_open):
                stalled = True
                stall_reason = "all_tasks_blocked"

        last_activity = self._updated_at
        scope_ids = {self._id} | {g.id for g in all_goals}
        for t in self.scope_tasks(leaves_only=False, include_archived=True):
            scope_ids.add(t.id)
        for eid in scope_ids:
            evs = self._atlas._events_by_entity.get(eid)
            if evs and evs[-1].timestamp > last_activity:
                last_activity = evs[-1].timestamp

        abandoned_count = goals_by_status.get("abandoned", 0)
        return {
            "dream_id": self._id,
            "status": self._status,
            "goal_count": len(all_goals) - abandoned_count,
            "goals_by_status": goals_by_status,
            "achieved_goal_count": goals_by_status.get("achieved", 0),
            "active_goal_count": len(active_goals),
            "proposed_goal_count": goals_by_status.get("proposed", 0),
            "paused_goal_count": goals_by_status.get("paused", 0),
            "abandoned_goal_count": abandoned_count,
            "active_wave": {
                "task_count": wave_total,
                "done_count": wave_done,
                "open_count": len(wave_open),
                "blocked_count": wave_blocked,
                "actionable_count": wave_actionable,
                "done_ratio": wave_done / wave_total if wave_total else 0.0,
            },
            "actionable_task_count": wave_actionable,
            "stalled": stalled,
            "stall_reason": stall_reason,
            "last_activity_at": last_activity,
        }

    # ------------------------------------------------------------------
    # Situational context and Markdown brief
    # ------------------------------------------------------------------

    def context(self, mode="compact"):
        """Return a hydrated situational summary for this Dream."""
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
            "stalled": prog["stalled"],
            "tags": list(self._tags),
        }
        if prog["stall_reason"]:
            ctx["stall_reason"] = prog["stall_reason"]
        if self._archived:
            ctx["archived"] = True

        if mode == "compact":
            if self._goal_ids:
                ctx["goal_count"] = prog["goal_count"]
                ctx["achieved_goal_count"] = prog["achieved_goal_count"]
                ctx["active_goal_count"] = prog["active_goal_count"]
            if self._notes:
                ctx["latest_note"] = self._notes[-1]["text"]
            return ctx

        goal_summaries = []
        for g in self.get_goals(recursive=False, include_archived=False):
            gp = g.progress()
            stub = _entity_stub(g)
            stub["done_ratio"] = gp["done_ratio"]
            stub["task_count"] = gp["task_count"]
            goal_summaries.append(stub)

        ctx.update({
            "summary": self._summary,
            "vision": self._vision,
            "archived": self._archived,
            "goals": goal_summaries,
            "progress": prog,
            "related": self._related_stubs(),
            "notes": copy.deepcopy(self._notes[-5:]),
            "recent_events": [e.to_dict() for e in self.history(limit=10)],
        })
        return ctx

    def brief(self):
        """Render a token-tight Markdown briefing for this Dream."""
        from taskatlas._views import render_dream_brief

        return render_dream_brief(self)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self):
        data = self._base_to_dict()
        data.update({
            "status": self._status,
            "vision": self._vision,
            "goal_ids": list(self._goal_ids),
        })
        return data

    @classmethod
    def _from_dict(cls, atlas, data):
        dream = cls(
            atlas,
            {
                "id": data["id"],
                "title": data.get("title") or "Untitled Dream",
                "summary": data.get("summary", ""),
                "vision": data.get("vision", ""),
                "status": data.get("status", "seed"),
                "priority": data.get("priority", "medium"),
                "tags": data.get("tags", []),
                "meta": data.get("meta", {}),
                "archived": data.get("archived", False),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
            },
            _token=_FACTORY_TOKEN,
        )
        dream._goal_ids = list(data.get("goal_ids", []))
        dream._base_load(data)
        return dream
