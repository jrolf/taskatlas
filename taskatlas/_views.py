"""Views, critical-path readiness engine, and token-tight Markdown briefings."""

from taskatlas._filtering import filter_items
from taskatlas._types import (
    PRIORITY_BY_RANK,
    PRIORITY_ORDER,
    TASK_STAGES,
    TERMINAL_TASK_STAGES,
)

_STAGE_READINESS_RANK = {
    "active": 2,
    "ready": 1,
    "inbox": 0,
}


def _task_card(task):
    """Build a compact workflow card dict for board outputs."""
    card = {
        "id": task.id,
        "title": task.title,
        "stage": task.stage,
        "priority": task.priority,
        "is_blocked": task.is_blocked,
        "tags": list(task.tags),
    }
    if task.owner is not None:
        card["owner"] = task.owner
    if task.is_held:
        card["hold_reason"] = task.hold_reason
    if task.archived:
        card["archived"] = True
    return card


# ------------------------------------------------------------------
# Board view - tasks bucketed by workflow stage
# ------------------------------------------------------------------


def render_board(atlas, *, goal_id=None, dream_id=None, **filters):
    """Return Tasks bucketed by workflow stage, optionally scoped transitively."""
    if goal_id is not None and goal_id not in atlas._goals:
        raise KeyError(f"No goal with id {goal_id!r}")
    if dream_id is not None and dream_id not in atlas._dreams:
        raise KeyError(f"No dream with id {dream_id!r}")

    if goal_id is not None:
        goal = atlas._goals[goal_id]
        tasks = goal.scope_tasks(recursive=True, include_archived=True)
        if dream_id is not None:
            tasks = [t for t in tasks if dream_id in t.effective_dream_ids]
    elif dream_id is not None:
        dream = atlas._dreams[dream_id]
        tasks = dream.scope_tasks(include_archived=True)
    else:
        tasks = list(atlas._tasks.values())

    filtered = filter_items(tasks, **filters)

    stages = {stage: [] for stage in TASK_STAGES}
    for task in filtered:
        bucket = stages.get(task.stage)
        if bucket is not None:
            bucket.append(_task_card(task))

    return {"stages": stages}


# ------------------------------------------------------------------
# Tree view - progressive Dream -> Goal -> Subgoal -> Task -> Subtask hierarchy
# ------------------------------------------------------------------


def _task_tree_node(task, atlas, include_archived):
    node = {
        "id": task.id,
        "title": task.title,
        "stage": task.stage,
        "priority": task.priority,
        "is_blocked": task.is_blocked,
    }
    if task.owner is not None:
        node["owner"] = task.owner
    if task.archived:
        node["archived"] = True

    children = [
        atlas._tasks[cid]
        for cid in task.child_task_ids
        if cid in atlas._tasks
        and (include_archived or not atlas._tasks[cid].archived)
    ]
    if children:
        node["subtasks"] = [
            _task_tree_node(c, atlas, include_archived) for c in children
        ]
    return node


def _goal_tree_node(goal, atlas, include_archived):
    node = {
        "id": goal.id,
        "title": goal.title,
        "status": goal.status,
        "priority": goal.priority,
    }
    if goal.archived:
        node["archived"] = True

    child_goals = [
        atlas._goals[cid]
        for cid in goal.child_goal_ids
        if cid in atlas._goals
        and (include_archived or not atlas._goals[cid].archived)
    ]
    if child_goals:
        node["subgoals"] = [
            _goal_tree_node(cg, atlas, include_archived) for cg in child_goals
        ]

    attached_tasks = [
        atlas._tasks[tid]
        for tid in goal.task_ids
        if tid in atlas._tasks
        and (include_archived or not atlas._tasks[tid].archived)
    ]
    attached_ids = {t.id for t in attached_tasks}
    # Render only root tasks of this goal's attachment set; subtasks render under parents
    root_tasks = [
        t
        for t in attached_tasks
        if t.parent_task_id is None or t.parent_task_id not in attached_ids
    ]
    if root_tasks:
        node["tasks"] = [
            _task_tree_node(t, atlas, include_archived) for t in root_tasks
        ]
    return node


def _dream_tree_node(dream, atlas, include_archived):
    prog = dream.progress()
    node = {
        "id": dream.id,
        "title": dream.title,
        "status": dream.status,
        "priority": dream.priority,
        "stalled": prog["stalled"],
    }
    if prog["stall_reason"]:
        node["stall_reason"] = prog["stall_reason"]
    if dream.archived:
        node["archived"] = True

    goals = [
        atlas._goals[gid]
        for gid in dream.goal_ids
        if gid in atlas._goals
        and (include_archived or not atlas._goals[gid].archived)
    ]
    if goals:
        node["goals"] = [
            _goal_tree_node(g, atlas, include_archived) for g in goals
        ]
    return node


def render_tree(atlas, *, include_archived=False):
    """Render the structural containment hierarchy.

    Progressive disclosure: when no visible Dreams exist in the Atlas, top-level
    Goals appear directly under ``'goals'`` with zero Dream clutter. When at
    least one visible Dream exists, ``'dreams'`` is rendered at the root and any
    top-level Goals without a Dream appear under ``'unattached_goals'``.
    """
    visible_dreams = [
        d
        for d in atlas._dreams.values()
        if include_archived or not d.archived
    ]
    visible_dream_ids = {d.id for d in visible_dreams}

    top_goals = [
        g
        for g in atlas._goals.values()
        if g.parent_goal_id is None and (include_archived or not g.archived)
    ]

    orphan_tasks = [
        t
        for t in atlas._tasks.values()
        if t.parent_task_id is None
        and not t.goal_ids
        and (include_archived or not t.archived)
    ]

    tree = {}
    if visible_dreams:
        tree["dreams"] = [
            _dream_tree_node(d, atlas, include_archived) for d in visible_dreams
        ]
        unattached_goals = [
            g for g in top_goals if g.dream_id not in visible_dream_ids
        ]
        if unattached_goals:
            tree["unattached_goals"] = [
                _goal_tree_node(g, atlas, include_archived) for g in unattached_goals
            ]
    elif top_goals:
        tree["goals"] = [
            _goal_tree_node(g, atlas, include_archived) for g in top_goals
        ]

    if orphan_tasks:
        tree["unattached_tasks"] = [
            _task_tree_node(t, atlas, include_archived) for t in orphan_tasks
        ]
    return tree


# ------------------------------------------------------------------
# Queue view - critical-path readiness and priority inheritance engine
# ------------------------------------------------------------------


def _goal_chain_is_active(goal, atlas):
    """Return True when neither *goal*, its ancestor Goals, nor its Dream are paused/dormant."""
    for item in [goal] + goal.ancestor_goals():
        if item.archived or item.status in ("paused", "abandoned"):
            return False
        if item.dream_id is not None:
            dream = atlas._dreams.get(item.dream_id)
            if dream is not None and (
                dream.archived or dream.status in ("dormant", "abandoned")
            ):
                return False
    return True


def _workstream_is_paused(task, atlas):
    """Return True when all governing Goal/Dream lineages for *task* are paused/dormant."""
    attached_goals = []
    seen = set()
    for node in [task] + task.ancestor_tasks():
        for gid in node.goal_ids:
            if gid not in seen and gid in atlas._goals:
                seen.add(gid)
                attached_goals.append(atlas._goals[gid])

    if not attached_goals:
        return False
    return not any(_goal_chain_is_active(g, atlas) for g in attached_goals)


def _has_open_subtasks(task, atlas):
    """Return True when *task* has non-terminal, non-archived subtasks that should run first."""
    for cid in task.child_task_ids:
        child = atlas._tasks.get(cid)
        if child is None or child.archived:
            continue
        if child.stage not in TERMINAL_TASK_STAGES:
            return True
    return False


def _compute_transitive_dependents(atlas):
    """Return a memoized lookup function mapping entity_id -> set of open dependents.

    Walks incoming ``depends_on`` edges transitively, and also propagates any
    external ``depends_on`` dependents of an open ancestor container task down
    to its subtasks (because a parent task cannot complete and unblock its own
    dependents until its subtasks finish).
    """
    memo = {}

    def _collect(entity_id, visiting):
        if entity_id in memo:
            return memo[entity_id]
        entity = atlas._find_entity(entity_id)
        if entity is None or not hasattr(entity, "dependents"):
            return frozenset()

        acc = set()
        next_visiting = visiting | {entity_id}
        for dep in entity.dependents(unsatisfied_only=True):
            if dep.archived or dep.id in next_visiting:
                continue
            acc.add(dep)
            acc.update(_collect(dep.id, next_visiting))

        if entity._entity_type == "task" and entity.parent_task_id is not None:
            parent = atlas._tasks.get(entity.parent_task_id)
            if (
                parent is not None
                and not parent.archived
                and not parent._is_terminal()
                and parent.id not in next_visiting
            ):
                acc.update(_collect(parent.id, next_visiting))

        frozen = frozenset(acc)
        if not visiting:
            memo[entity_id] = frozen
        return frozen

    return lambda eid: _collect(eid, frozenset())


def render_queue(
    atlas,
    *,
    goal_id=None,
    dream_id=None,
    stages=None,
    include_claimed=False,
    owner=None,
    limit=None,
):
    """Return executable leaf Tasks ordered by critical-path urgency and leverage.

    Readiness rules:
    1. Excludes ``done``, ``canceled``, ``review``, and ``archived`` tasks by default.
    2. Excludes container tasks that still have open subtasks (surfacing leaves;
       once all subtasks finish, an open parent resurfaces for wrap-up).
    3. Excludes topologically blocked tasks (unsatisfied ``depends_on`` targets)
       and externally held tasks (``hold_reason`` set).
    4. Excludes tasks whose governing Goals/Dreams are paused, dormant, or abandoned.
    5. Excludes tasks claimed by other workers unless ``include_claimed=True``.

    Ranking rules:
    - ``effective_priority`` inherits the max priority of all open downstream
      items transitively blocked by this task.
    - Ties break by ``unblocks_count``, workflow stage readiness, Goal priority,
      Dream priority (never hijacking tactical urgency), and FIFO creation order.
    """
    if goal_id is not None and goal_id not in atlas._goals:
        raise KeyError(f"No goal with id {goal_id!r}")
    if dream_id is not None and dream_id not in atlas._dreams:
        raise KeyError(f"No dream with id {dream_id!r}")

    allowed_stages = (
        frozenset(stages)
        if stages is not None
        else frozenset({"active", "ready", "inbox"})
    )

    if goal_id is not None:
        candidates = atlas._goals[goal_id].scope_tasks(
            recursive=True,
            include_archived=False,
        )
        if dream_id is not None:
            candidates = [
                t for t in candidates if dream_id in t.effective_dream_ids
            ]
    elif dream_id is not None:
        candidates = atlas._dreams[dream_id].scope_tasks(include_archived=False)
    else:
        candidates = [t for t in atlas._tasks.values() if not t.archived]

    get_dependents = _compute_transitive_dependents(atlas)
    scored = []

    for task in candidates:
        if task.stage not in allowed_stages:
            continue
        if _has_open_subtasks(task, atlas):
            continue
        if task.is_blocked:
            continue
        if any(
            anc.archived or anc._is_terminal() or anc.is_blocked
            for anc in task.ancestor_tasks()
        ):
            continue
        if _workstream_is_paused(task, atlas):
            continue

        if not include_claimed:
            if owner is not None:
                if task.owner is not None and task.owner != owner:
                    continue
            else:
                if task.owner is not None:
                    continue

        trans_deps = get_dependents(task.id)
        nominal_rank = PRIORITY_ORDER.get(task.priority, 1)
        dep_ranks = [PRIORITY_ORDER.get(d.priority, 1) for d in trans_deps]
        eff_rank = max([nominal_rank] + dep_ranks)
        unblocks_count = len(trans_deps)
        stage_rank = _STAGE_READINESS_RANK.get(task.stage, 0)

        eff_gids = task.effective_goal_ids
        goal_rank = max(
            (
                PRIORITY_ORDER.get(atlas._goals[gid].priority, 1)
                for gid in eff_gids
                if gid in atlas._goals
            ),
            default=-1,
        )

        eff_dids = task.effective_dream_ids
        dream_rank = max(
            (
                PRIORITY_ORDER.get(atlas._dreams[did].priority, 1)
                for did in eff_dids
                if did in atlas._dreams
            ),
            default=-1,
        )

        sort_key = (
            -eff_rank,
            -unblocks_count,
            -stage_rank,
            -goal_rank,
            -dream_rank,
            task.created_at,
            task.id,
        )
        entry = {
            "id": task.id,
            "title": task.title,
            "stage": task.stage,
            "priority": task.priority,
            "effective_priority": PRIORITY_BY_RANK[eff_rank],
            "priority_boosted": eff_rank > nominal_rank,
            "unblocks_count": unblocks_count,
            "owner": task.owner,
            "tags": list(task.tags),
            "goal_ids": list(eff_gids),
        }
        if task.effective_dream_id is not None:
            entry["dream_id"] = task.effective_dream_id

        scored.append((sort_key, entry))

    scored.sort(key=lambda pair: pair[0])
    ordered = [entry for _, entry in scored]
    if limit is not None:
        ordered = ordered[:limit]
    return ordered


# ------------------------------------------------------------------
# Summary view - aggregate counts, stalled dreams, and recent events
# ------------------------------------------------------------------


def render_summary(atlas):
    """Return an aggregate health snapshot across the Atlas."""
    active_dreams = [d for d in atlas._dreams.values() if not d.archived]
    active_goals = [g for g in atlas._goals.values() if not g.archived]
    active_tasks = [t for t in atlas._tasks.values() if not t.archived]

    by_stage = {}
    blocked_count = 0
    for t in active_tasks:
        by_stage[t.stage] = by_stage.get(t.stage, 0) + 1
        if t.is_blocked:
            blocked_count += 1

    by_status = {}
    for g in active_goals:
        by_status[g.status] = by_status.get(g.status, 0) + 1

    archived_counts = {
        "dreams": sum(1 for d in atlas._dreams.values() if d.archived),
        "goals": sum(1 for g in atlas._goals.values() if g.archived),
        "tasks": sum(1 for t in atlas._tasks.values() if t.archived),
    }

    summary = {
        "name": atlas.name,
        "goal_count": len(active_goals),
        "task_count": len(active_tasks),
        "blocked_task_count": blocked_count,
        "actionable_task_count": len(render_queue(atlas, include_claimed=True)),
        "by_stage": by_stage,
        "by_status": by_status,
        "archived_count": archived_counts,
        "recent_events": [e.to_dict() for e in atlas.get_events(limit=10)],
    }

    if active_dreams:
        by_dream_status = {}
        stalled_dreams = []
        for d in active_dreams:
            by_dream_status[d.status] = by_dream_status.get(d.status, 0) + 1
            prog = d.progress()
            if prog["stalled"]:
                stalled_dreams.append({
                    "id": d.id,
                    "title": d.title,
                    "stall_reason": prog["stall_reason"],
                })
        summary["dream_count"] = len(active_dreams)
        summary["by_dream_status"] = by_dream_status
        summary["stalled_dreams"] = stalled_dreams

    return summary


# ------------------------------------------------------------------
# Token-tight Markdown briefings (Atlas, Dream, Goal, Task)
# ------------------------------------------------------------------


def _format_priority_badge(entry):
    eff = entry["effective_priority"].upper()
    nom = entry["priority"].upper()
    if entry.get("priority_boosted"):
        return f"{eff}*<-{nom}"
    return eff


def render_atlas_brief(
    atlas,
    *,
    dream_id=None,
    goal_id=None,
    queue_limit=5,
    recent_limit=5,
):
    """Render a compact, high-signal Markdown situational briefing."""
    if goal_id is not None and goal_id not in atlas._goals:
        raise KeyError(f"No goal with id {goal_id!r}")
    if dream_id is not None and dream_id not in atlas._dreams:
        raise KeyError(f"No dream with id {dream_id!r}")

    title = atlas.name or "Untitled Atlas"
    lines = [f"# Atlas: {title}"]

    dreams = [d for d in atlas._dreams.values() if not d.archived]
    if dream_id is not None:
        dreams = [d for d in dreams if d.id == dream_id]
    elif goal_id is not None:
        eff_did = atlas._goals[goal_id].effective_dream_id
        dreams = [d for d in dreams if d.id == eff_did]

    goals = atlas.get_goals(dream_id=dream_id) if dream_id else atlas.get_goals()
    if goal_id is not None:
        target_goal = atlas._goals[goal_id]
        goals = [target_goal] + target_goal.descendant_goals(include_archived=False)
        if dream_id is not None:
            goals = [g for g in goals if g.effective_dream_id == dream_id]

    task_filters = {}
    if goal_id is not None:
        task_filters["goal_id"] = goal_id
    if dream_id is not None:
        task_filters["dream_id"] = dream_id
    tasks = atlas.get_tasks(**task_filters)
    ready_queue = render_queue(
        atlas,
        goal_id=goal_id,
        dream_id=dream_id,
        include_claimed=True,
        limit=queue_limit,
    )
    blocked_tasks = [t for t in tasks if t.is_blocked]

    stat_parts = []
    if dreams:
        stat_parts.append(f"{len(dreams)} dreams")
    stat_parts.append(f"{len(goals)} goals")
    stat_parts.append(f"{len(tasks)} tasks")
    stat_parts.append(f"{len(blocked_tasks)} blocked")
    lines.append(f"Scope: {', '.join(stat_parts)}")

    if dreams:
        lines.append("")
        lines.append("## Dreams")
        for d in dreams:
            dp = d.progress()
            stall_tag = (
                f" [STALLED: {dp['stall_reason']}]" if dp["stalled"] else ""
            )
            wave = dp["active_wave"]
            lines.append(
                f"- {d.id} [{d.status.upper()} | {d.priority}] {d.title}"
                f" - goals: {dp['achieved_goal_count']} achieved, "
                f"{dp['active_goal_count']} active; "
                f"wave: {wave['done_count']}/{wave['task_count']} done{stall_tag}"
            )

    active_or_proposed_goals = [
        g for g in goals if g.status in ("active", "proposed", "paused")
    ]
    if active_or_proposed_goals:
        lines.append("")
        lines.append("## Goals")
        for g in active_or_proposed_goals:
            gp = g.progress()
            pct = f"{gp['done_ratio']:.0%}"
            blk = f", {gp['blocked_count']} blocked" if gp["blocked_count"] else ""
            lines.append(
                f"- {g.id} [{g.status.upper()} | {g.priority}] {g.title}"
                f" ({gp['done_count']}/{gp['task_count']} done, {pct}{blk})"
            )

    lines.append("")
    lines.append("## Ready Queue")
    if not ready_queue:
        lines.append("- (no actionable unblocked leaf tasks)")
    else:
        for idx, item in enumerate(ready_queue, 1):
            badge = _format_priority_badge(item)
            unblocks = (
                f", unblocks {item['unblocks_count']}"
                if item["unblocks_count"]
                else ""
            )
            owner = f", owner={item['owner']}" if item.get("owner") else ""
            goal_ref = ""
            if item["goal_ids"]:
                first_goal = atlas._goals.get(item["goal_ids"][0])
                if first_goal is not None:
                    goal_ref = f" -> Goal: {first_goal.title}"
            lines.append(
                f"{idx}. [{badge} | {item['stage']}{unblocks}{owner}] "
                f"{item['id']}: {item['title']}{goal_ref}"
            )

    if blocked_tasks:
        lines.append("")
        lines.append("## Impediments")
        for bt in blocked_tasks:
            reasons = []
            if bt.is_held:
                reasons.append(f"HELD: {bt.hold_reason}")
            prereqs = bt.blockers()
            if prereqs:
                prereq_desc = ", ".join(f"{p.id} ({p.title})" for p in prereqs)
                reasons.append(f"waiting on {prereq_desc}")
            lines.append(
                f"- {bt.id} [{bt.priority}] {bt.title} - {'; '.join(reasons)}"
            )

    if recent_limit:
        if dream_id is not None or goal_id is not None:
            scope_ids = (
                {d.id for d in dreams}
                | {g.id for g in goals}
                | {t.id for t in tasks}
            )
            recent_events = [
                ev
                for ev in reversed(atlas._events)
                if ev.entity_id in scope_ids
            ][:recent_limit]
        else:
            recent_events = atlas.get_events(limit=recent_limit)
        if recent_events:
            lines.append("")
            lines.append("## Recent Activity")
            for ev in recent_events:
                who = f" by {ev.actor}" if ev.actor else ""
                why = f" - {ev.reason}" if ev.reason else ""
                lines.append(f"- {ev.event_type} on {ev.entity_id}{who}{why}")

    return "\n".join(lines)


def render_dream_brief(dream):
    """Render a compact Markdown briefing for a single Dream."""
    prog = dream.progress()
    stall_str = f" | STALLED ({prog['stall_reason']})" if prog["stalled"] else ""
    lines = [
        f"# Dream {dream.id}: {dream.title}",
        f"Status: {dream.status} | Priority: {dream.priority}{stall_str}",
    ]
    if dream.vision:
        lines.append(f"Vision: {dream.vision}")
    if dream.summary:
        lines.append(f"Summary: {dream.summary}")

    wave = prog["active_wave"]
    lines.append(
        f"Milestones: {prog['achieved_goal_count']} achieved, "
        f"{prog['active_goal_count']} active, "
        f"{prog['proposed_goal_count']} proposed | "
        f"Active wave: {wave['done_count']}/{wave['task_count']} tasks done "
        f"({wave['actionable_count']} actionable, {wave['blocked_count']} blocked)"
    )

    goals = dream.get_goals(recursive=False, include_archived=False)
    if goals:
        lines.append("")
        lines.append("## Goals")
        for g in goals:
            gp = g.progress()
            lines.append(
                f"- {g.id} [{g.status}] {g.title} "
                f"({gp['done_count']}/{gp['task_count']} done)"
            )

    if dream._notes:
        lines.append("")
        lines.append(f"Latest note: {dream._notes[-1]['text']}")
    return "\n".join(lines)


def render_goal_brief(goal):
    """Render a compact Markdown briefing for a single Goal."""
    prog = goal.progress()
    lines = [
        f"# Goal {goal.id}: {goal.title}",
        f"Status: {goal.status} | Priority: {goal.priority} | "
        f"Progress: {prog['done_count']}/{prog['task_count']} ({prog['done_ratio']:.0%})",
    ]
    did = goal.effective_dream_id
    if did and did in goal._atlas._dreams:
        d = goal._atlas._dreams[did]
        lines.append(f"Dream: {d.id} ({d.title})")
    if goal.summary:
        lines.append(f"Summary: {goal.summary}")
    if goal.is_held:
        lines.append(f"Hold: {goal.hold_reason}")
    if goal.criteria:
        lines.append("")
        lines.append("## Criteria")
        for c in goal.criteria:
            lines.append(f"- {c}")
    if goal.outcome:
        lines.append(f"Outcome: {goal.outcome}")

    tasks = goal.scope_tasks(recursive=True, leaves_only=True, include_archived=False)
    if tasks:
        lines.append("")
        lines.append("## Leaf Tasks")
        for t in tasks:
            blk = " [BLOCKED]" if t.is_blocked else ""
            lines.append(f"- {t.id} [{t.stage} | {t.priority}]{blk} {t.title}")
    return "\n".join(lines)


def render_task_brief(task):
    """Render a compact Markdown briefing for a single Task (including upstream receipts)."""
    blocked_flag = " | BLOCKED" if task.is_blocked else ""
    owner_flag = f" | Owner: {task.owner}" if task.owner else ""
    lines = [
        f"# Task {task.id}: {task.title}",
        f"Stage: {task.stage} | Priority: {task.priority}{blocked_flag}{owner_flag}",
    ]

    did = task.effective_dream_id
    if did and did in task._atlas._dreams:
        d = task._atlas._dreams[did]
        lines.append(f"Dream: {d.id} ({d.title})")

    gids = task.effective_goal_ids
    if gids:
        goal_labels = [
            f"{gid} ({task._atlas._goals[gid].title})"
            for gid in gids
            if gid in task._atlas._goals
        ]
        if goal_labels:
            lines.append(f"Goals: {', '.join(goal_labels)}")

    if task.summary:
        lines.append(f"Summary: {task.summary}")
    if task.is_held:
        lines.append(f"Hold: {task.hold_reason}")

    blockers = task.blockers()
    if blockers:
        lines.append("")
        lines.append("## Unsatisfied Blockers")
        for b in blockers:
            state = b.stage if b._entity_type == "task" else b.status
            lines.append(f"- {b.id} [{state}] {b.title}")

    satisfied = [
        dep for dep in task.dependencies(unsatisfied_only=False) if dep._is_satisfied()
    ]
    if satisfied:
        lines.append("")
        lines.append("## Upstream Receipts")
        for dep in satisfied:
            if dep._entity_type == "task" and dep.result:
                art = dep.result.get("artifacts") or []
                art_str = f" (artifacts: {', '.join(art)})" if art else ""
                summary_str = dep.result.get("summary") or "completed"
                lines.append(f"- {dep.id} ({dep.title}): {summary_str}{art_str}")
            else:
                lines.append(f"- {dep.id} ({dep.title}): achieved")

    if task.result:
        lines.append("")
        lines.append(f"Result ({task.result['status']}): {task.result.get('summary', '')}")
        if task.result.get("artifacts"):
            lines.append(f"Artifacts: {', '.join(task.result['artifacts'])}")

    if task._notes:
        lines.append("")
        lines.append(f"Latest note: {task._notes[-1]['text']}")
    return "\n".join(lines)
