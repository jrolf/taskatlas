# Filtering and Retrieval

`taskatlas` uses readable, conjunctive keyword arguments across `atlas.get_dreams()`, `atlas.get_goals()`, and `atlas.get_tasks()` - backed by transitive hierarchy resolution and Python predicate escape hatches.

---

## Setup

```python
import taskatlas as ta

atlas = ta.Atlas("Retrieval Demo")

lab = atlas.add_dream("Autonomous Lab", status="active", priority="high", tags=["research"])
idle = atlas.add_dream("Future Moonshot", status="active", priority="low")

platform = lab.add_goal("Experiment Platform", status="active", priority="urgent", tags=["core"])
runners = platform.add_goal("Sandbox Runners", status="active", priority="high")

runner_task = runners.add_task("Build microVM wrapper", stage="active", priority="urgent", tags=["infra", "core"])
seccomp = runner_task.add_task("Write seccomp policy", stage="ready", priority="high", tags=["security"])

docs_goal = atlas.add_goal("Operator Docs", status="proposed", priority="medium", tags=["docs"])
guide = docs_goal.add_task("Write quickstart", stage="ready", priority="low", tags=["docs"])
guide.hold("Waiting on CLI flag freeze")

old = docs_goal.add_task("Draft v0 notes", stage="inbox")
old.cancel("Obsolete", archive=True)

runner_task.claim("agent:worker-1")
```

---

## 1. Transitive Hierarchy Filters (`dream_id`, `goal_id`, `parent_id`)

`dream_id` and `goal_id` traverse subgoals and subtasks automatically:

```python
# Finds both 'runner_task' AND nested 'seccomp' through child subgoal 'runners'
atlas.get_tasks(goal_id=platform.id)

# Finds all goals and tasks belonging to the 'lab' Dream at any depth
atlas.get_goals(dream_id=lab.id)
atlas.get_tasks(dream_id=lab.id)

# Tasks not governed by any Dream
atlas.get_tasks(dream_id=None)

# Root goals or direct children of a specific parent
atlas.get_goals(parent_id=None)
atlas.get_tasks(parent_id=runner_task.id)
```

---

## 2. State, Blockage, Claim, and Stall Filters

```python
# Multi-value match (OR within field, AND across fields)
atlas.get_tasks(stage=["ready", "active"], priority=["high", "urgent"])

# Live blockage (topological depends_on OR external hold) and explicit holds
atlas.get_tasks(blocked=True)     # [Task(..., title='Write quickstart')]
atlas.get_tasks(held=True)        # [Task(..., title='Write quickstart')]

# Worker ownership
atlas.get_tasks(claimed=True)
atlas.get_tasks(owner="agent:worker-1")

# Stalled active Dreams (no active goals, no open tasks, or all open tasks blocked)
atlas.get_dreams(stalled=True)    # [Dream(..., title='Future Moonshot')]
```

---

## 3. Archival Visibility (`archived`) and Python Predicates (`where`)

Archived items are excluded by default (`archived=False`):

```python
atlas.get_tasks()                 # excludes 'old'
atlas.get_tasks(archived=True)    # ONLY archived items: [old]
atlas.get_tasks(archived=None)    # BOTH active and archived items

# Arbitrary Python predicate when keyword filters aren't enough
atlas.get_tasks(where=lambda t: len(t.tags) >= 2)
```

---

## 4. Sorting and Slicing

```python
# Priority defaults to urgent-first; timestamps default to newest-first; title defaults to A-Z
atlas.get_tasks(order_by="priority", limit=3)

# Override sort direction explicitly with descending=True/False
atlas.get_tasks(order_by="priority", descending=False)
atlas.get_tasks(order_by="title", descending=True)
```

---

## Filter Reference

| Filter | Applies To | Behavior |
|---|---|---|
| `id` | All | Exact ID or collection of IDs |
| `stage` | Tasks | Single stage or collection (`inbox`, `ready`, `active`, `review`, `done`, `canceled`) |
| `status` | Dreams, Goals | Single status or collection |
| `priority` | All | Single priority or collection (`low`, `medium`, `high`, `urgent`) |
| `tags` | All | Any-match tag or collection of tags |
| `title_contains` | All | Case-insensitive title substring |
| `dream_id` | Goals, Tasks | Transitive Dream membership (`None` matches unattached to any Dream) |
| `goal_id` | Tasks | Transitive Goal membership (single ID or collection) |
| `parent_id` | Goals, Tasks | Direct parent ID (`None` matches root items) |
| `blocked` / `is_blocked` | Goals, Tasks | Live topological or external-hold blockage |
| `held` / `is_held` | Goals, Tasks | Explicit external `hold()` active |
| `stalled` | Dreams | Active Dream lacking active goals or unblocked open tasks |
| `claimed` / `owner` | Tasks | Claimed boolean or exact owner string(s) |
| `has_tasks` | Dreams, Goals | Has non-archived tasks in transitive scope |
| `has_goals` | Dreams | Has non-archived goals in transitive scope |
| `linked_to` | All | Has any link (incoming or outgoing) to entity ID(s) |
| `archived` | All | `False` (default), `True` (archived only), or `None` (both) |
| `where` | All | Callable predicate `fn(item) -> bool` |
| `order_by` | All | `priority`, `created_at`, `updated_at`, `title`, `id`, `stage`, `status` |
| `descending` | All | Optional `bool` overriding `order_by` default direction |
| `limit` | All | Max items returned after sorting |
