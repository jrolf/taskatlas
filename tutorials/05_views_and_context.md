# Views and Context

`taskatlas` provides multiple ways to look at the same body of work. Each view answers a different question, and the `context()` method gives you focused situational awareness on any single entity.

This tutorial walks through all the built-in views and shows when to use each one.

---

## Setup

We'll build a project with enough structure to make the views interesting:

```python
import taskatlas as ta
import json

atlas = ta.Atlas({"name": "Views Demo"})

# Goals
backend = atlas.add_goal({
    "title": "Backend service",
    "status": "active",
    "priority": "high",
    "tags": ["backend"],
})

frontend = atlas.add_goal({
    "title": "Frontend app",
    "status": "active",
    "priority": "high",
    "tags": ["frontend"],
})

# Backend tasks
auth = backend.add_task({"title": "Authentication", "stage": "review", "priority": "high"})
database = backend.add_task({"title": "Database layer", "stage": "active", "priority": "urgent"})
api_routes = backend.add_task({"title": "API routes", "stage": "blocked", "priority": "high"})
caching = backend.add_task({"title": "Caching layer", "stage": "inbox", "priority": "low"})

# Frontend tasks
components = frontend.add_task({"title": "Component library", "stage": "active", "priority": "high"})
state_mgmt = frontend.add_task({"title": "State management", "stage": "ready", "priority": "medium"})
design_system = frontend.add_task({"title": "Design system", "stage": "done", "priority": "medium"})

# Subtasks under database
database.add_task({"title": "Schema migrations", "stage": "done", "priority": "high"})
database.add_task({"title": "Connection pooling", "stage": "active", "priority": "high"})
database.add_task({"title": "Query optimization", "stage": "inbox", "priority": "medium"})

# Dependencies
api_routes.link(database, kind="depends_on")
api_routes.link(auth, kind="depends_on")
components.link(design_system, kind="depends_on")
state_mgmt.link(components, kind="depends_on")

# Some notes
api_routes.note("Blocked until database and auth layers are both complete.")
database.note("Connection pooling proving trickier than expected.")
backend.note("On track despite the API routes blockage.")
```

---

## Board View

**Question it answers:** *Where is everything right now?*

The board groups tasks by stage — like a kanban board in data form.

```python
board = atlas.board()

for stage, tasks in board["stages"].items():
    if tasks:
        print(f"\n{stage.upper()} ({len(tasks)}):")
        for t in tasks:
            print(f"  [{t['priority']:>6}] {t['title']}")
```

Output:

```
INBOX (2):
  [   low] Caching layer
  [medium] Query optimization

READY (1):
  [medium] State management

ACTIVE (2):
  [urgent] Database layer
  [  high] Component library

BLOCKED (1):
  [  high] API routes

REVIEW (1):
  [  high] Authentication

DONE (2):
  [medium] Design system
  [  high] Schema migrations
```

### Scoped to a goal

Focus the board on a single goal to see only the work that contributes to it:

```python
backend_board = atlas.board(goal_id=backend.id)
```

This shows only tasks attached to the backend goal.

### With filters

```python
high_priority_board = atlas.board(priority="high")
```

---

## Tree View

**Question it answers:** *What is the shape of this project?*

The tree reveals the hierarchical structure — goals containing tasks containing subtasks.

```python
tree = atlas.tree()
print(json.dumps(tree, indent=2))
```

Output structure:

```json
{
  "goals": [
    {
      "id": "g-...",
      "title": "Backend service",
      "status": "active",
      "priority": "high",
      "tasks": [
        {
          "id": "t-...",
          "title": "Authentication",
          "stage": "review",
          "priority": "high"
        },
        {
          "id": "t-...",
          "title": "Database layer",
          "stage": "active",
          "priority": "urgent",
          "subtasks": [
            {"id": "t-...", "title": "Schema migrations", "stage": "done", "priority": "high"},
            {"id": "t-...", "title": "Connection pooling", "stage": "active", "priority": "high"},
            {"id": "t-...", "title": "Query optimization", "stage": "inbox", "priority": "medium"}
          ]
        },
        ...
      ]
    },
    {
      "id": "g-...",
      "title": "Frontend app",
      ...
    }
  ]
}
```

Key behaviors:

- Only top-level goals appear at the root (subgoals nest inside their parents).
- Only root-level tasks appear under each goal (subtasks nest under their parents).
- Archived items are excluded.
- Tasks not attached to any goal appear in an `unattached_tasks` key.

---

## Queue View

**Question it answers:** *What should I work on next?*

The queue is a priority-sorted list of actionable work. It applies opinionated filtering to surface what matters:

```python
queue = atlas.queue()

for i, item in enumerate(queue, 1):
    goals = ", ".join(item["goal_ids"]) if item["goal_ids"] else "unattached"
    print(f"{i}. [{item['priority']:>6}] {item['title']} ({item['stage']}) — {goals}")
```

Output:

```
1. [urgent] Connection pooling (active) — ...
2. [  high] API routes (blocked) — ...
3. [  high] Authentication (review) — ...
4. [  high] Component library (active) — ...
5. [medium] State management (ready) — ...
6. [medium] Query optimization (inbox) — ...
7. [   low] Caching layer (inbox) — ...
```

Key behaviors:

- **Excludes done and archived tasks** — only shows work that still needs attention.
- **Excludes parent/container tasks** — if a task has subtasks, the subtasks appear instead. This prevents showing "Database layer" alongside its own children.
- **Sorted by priority** — urgent first, then high, medium, low.

### Scoped to a goal

```python
backend_queue = atlas.queue(goal_id=backend.id)
```

---

## Summary View

**Question it answers:** *What does the big picture look like?*

```python
summary = atlas.summary()

print(f"Goals: {summary['goal_count']}")
print(f"Tasks: {summary['task_count']}")
print(f"\nTasks by stage:")
for stage, count in summary['by_stage'].items():
    print(f"  {stage}: {count}")
print(f"\nGoals by status:")
for status, count in summary['by_status'].items():
    print(f"  {status}: {count}")
print(f"\nRecent events: {len(summary['recent_events'])}")
```

The summary gives you a fast aggregate snapshot. It's useful for dashboards, status reports, or quick sanity checks.

---

## Context: Focused Situational Awareness

While views show the big picture, `context()` zooms into a single entity and returns everything relevant about it.

### Task context (compact)

```python
ctx = api_routes.context()
print(json.dumps(ctx, indent=2))
```

```json
{
  "id": "t-...",
  "title": "API routes",
  "stage": "blocked",
  "priority": "high",
  "tags": [],
  "goal_ids": ["g-..."],
  "latest_note": "Blocked until database and auth layers are both complete."
}
```

Compact mode gives you the essentials: identity, state, and the latest note. It includes structural references (parent, children, goals) only when they exist.

### Task context (full)

```python
ctx = api_routes.context(mode="full")
print(json.dumps(ctx, indent=2, default=str))
```

Full mode adds everything: summary, all structural IDs, all links (with full link data), the last 5 notes, and the 10 most recent events.

### Goal context (compact)

```python
ctx = backend.context()
print(json.dumps(ctx, indent=2))
```

```json
{
  "id": "g-...",
  "title": "Backend service",
  "status": "active",
  "priority": "high",
  "tags": ["backend"],
  "task_count": 4,
  "latest_note": "On track despite the API routes blockage."
}
```

### Goal context (full)

```python
ctx = backend.context(mode="full")
```

Full goal context includes the progress snapshot (task counts by stage, done ratio), which is especially useful for status reporting:

```json
{
  "id": "g-...",
  "title": "Backend service",
  "status": "active",
  "priority": "high",
  "tags": ["backend"],
  "summary": "",
  "parent_goal_id": null,
  "child_goal_ids": [],
  "task_ids": ["t-...", "t-...", "t-...", "t-..."],
  "links": [],
  "progress": {
    "goal_id": "g-...",
    "task_count": 4,
    "by_stage": {"review": 1, "active": 1, "blocked": 1, "inbox": 1},
    "done_count": 0,
    "blocked_count": 1,
    "active_count": 1,
    "done_ratio": 0.0
  },
  "notes": [...],
  "recent_events": [...]
}
```

---

## Progress

The `progress()` method on goals gives you a quick readout of how work is advancing:

```python
for goal in atlas.get_goals():
    p = goal.progress()
    bar = "█" * p["done_count"] + "░" * (p["task_count"] - p["done_count"])
    print(f"{goal.title}: [{bar}] {p['done_ratio']:.0%} ({p['done_count']}/{p['task_count']})")
```

```
Backend service: [░░░░] 0% (0/4)
Frontend app: [█░░] 33% (1/3)
```

---

## Choosing the Right View

| You want to know... | Use |
|---|---|
| Where all tasks are in the workflow | `atlas.board()` |
| The structural shape of the project | `atlas.tree()` |
| What to work on next | `atlas.queue()` |
| High-level counts and health | `atlas.summary()` |
| Everything about one task | `task.context(mode="full")` |
| Everything about one goal | `goal.context(mode="full")` |
| How much is done for a goal | `goal.progress()` |

All views return structured Python dicts and lists. They're designed to be consumed programmatically — rendered into text, piped to a UI, formatted as markdown, or passed to an AI agent as context.
