"""Rendering helpers — board, tree, queue, and summary views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from taskatlas._types import PRIORITY_ORDER

if TYPE_CHECKING:
    from taskatlas._atlas import Atlas


def _task_summary(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "stage": task.stage,
        "priority": task.priority,
        "tags": task.tags,
    }


# ------------------------------------------------------------------
# Board view — tasks grouped by stage
# ------------------------------------------------------------------

def render_board(atlas: Atlas, goal_id: str | None = None, **filters) -> dict:
    """Return tasks bucketed by stage.

    Optionally scoped to a single goal via *goal_id*.
    """
    from taskatlas._filtering import filter_items

    tasks = list(atlas._tasks.values())

    if goal_id is not None:
        goal = atlas._goals.get(goal_id)
        if goal is None:
            raise KeyError(f"No goal with id {goal_id!r}")
        tasks = [t for t in tasks if t.id in goal.task_ids]

    if filters:
        tasks = filter_items(tasks, **filters)
    else:
        tasks = [t for t in tasks if t.stage != "archived"]

    stages: dict[str, list[dict]] = {s: [] for s in atlas.task_stages if s != "archived"}
    for t in tasks:
        bucket = stages.get(t.stage)
        if bucket is not None:
            bucket.append(_task_summary(t))

    return {"stages": stages}


# ------------------------------------------------------------------
# Tree view — hierarchical goal → task structure
# ------------------------------------------------------------------

def _task_tree_node(task, atlas: Atlas) -> dict:
    node: dict = {
        "id": task.id,
        "title": task.title,
        "stage": task.stage,
        "priority": task.priority,
    }
    children = [
        atlas._tasks[cid]
        for cid in task.child_task_ids
        if cid in atlas._tasks
    ]
    if children:
        node["subtasks"] = [_task_tree_node(c, atlas) for c in children]
    return node


def _goal_tree_node(goal, atlas: Atlas) -> dict:
    node: dict = {
        "id": goal.id,
        "title": goal.title,
        "status": goal.status,
        "priority": goal.priority,
    }

    child_goals = [
        atlas._goals[cid]
        for cid in goal.child_goal_ids
        if cid in atlas._goals
    ]
    if child_goals:
        node["subgoals"] = [_goal_tree_node(cg, atlas) for cg in child_goals]

    attached_tasks = [
        atlas._tasks[tid]
        for tid in goal.task_ids
        if tid in atlas._tasks
    ]
    root_tasks = [t for t in attached_tasks if t.parent_task_id is None]
    if root_tasks:
        node["tasks"] = [_task_tree_node(t, atlas) for t in root_tasks]

    return node


def render_tree(atlas: Atlas) -> dict:
    """Return a nested hierarchy of goals and tasks."""
    top_goals = [
        g for g in atlas._goals.values()
        if g.parent_goal_id is None and g.status != "archived"
    ]

    orphan_tasks = [
        t for t in atlas._tasks.values()
        if t.parent_task_id is None
        and not t.goal_ids
        and t.stage != "archived"
    ]

    tree: dict = {}
    if top_goals:
        tree["goals"] = [_goal_tree_node(g, atlas) for g in top_goals]
    if orphan_tasks:
        tree["unattached_tasks"] = [_task_tree_node(t, atlas) for t in orphan_tasks]

    return tree


# ------------------------------------------------------------------
# Queue view — priority-ordered actionable tasks
# ------------------------------------------------------------------

def render_queue(
    atlas: Atlas,
    goal_id: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return a priority-sorted list of actionable tasks."""
    tasks = list(atlas._tasks.values())

    if goal_id is not None:
        goal = atlas._goals.get(goal_id)
        if goal is None:
            raise KeyError(f"No goal with id {goal_id!r}")
        tasks = [t for t in tasks if t.id in goal.task_ids]

    actionable = [
        t for t in tasks
        if t.stage not in ("done", "archived")
        and not t.child_task_ids
    ]

    actionable.sort(
        key=lambda t: PRIORITY_ORDER.get(t.priority, 0),
        reverse=True,
    )

    if limit is not None:
        actionable = actionable[:limit]

    return [
        {
            "id": t.id,
            "title": t.title,
            "stage": t.stage,
            "priority": t.priority,
            "tags": t.tags,
            "goal_ids": t.goal_ids,
        }
        for t in actionable
    ]


# ------------------------------------------------------------------
# Summary view — aggregate counts
# ------------------------------------------------------------------

def render_summary(atlas: Atlas) -> dict:
    """Return aggregate counts and recent activity."""
    goals = list(atlas._goals.values())
    tasks = list(atlas._tasks.values())

    by_stage: dict[str, int] = {}
    for t in tasks:
        by_stage[t.stage] = by_stage.get(t.stage, 0) + 1

    by_status: dict[str, int] = {}
    for g in goals:
        by_status[g.status] = by_status.get(g.status, 0) + 1

    recent = atlas.get_events(limit=10)

    return {
        "goal_count": len(goals),
        "task_count": len(tasks),
        "by_stage": by_stage,
        "by_status": by_status,
        "recent_events": [e.to_dict() for e in recent],
    }
