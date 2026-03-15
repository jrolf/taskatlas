# Quickstart: Your First Atlas

This tutorial walks through the fundamental operations of `taskatlas` — creating an atlas, defining goals and tasks, moving work forward, and inspecting the state of things.

---

## Install

```bash
pip install -e .
```

## Import

```python
import taskatlas as ta
```

The entire public API is available through this single import: `Atlas`, `Goal`, `Task`, `Link`, and `Event`.

---

## Create an Atlas

An `Atlas` is the root container — the navigable world where all goals and tasks live.

```python
atlas = ta.Atlas({"name": "My First Atlas"})
```

You can also use keyword arguments:

```python
atlas = ta.Atlas(name="My First Atlas")
```

Both forms work throughout the library. Dict-style payloads are the primary pattern because they serialize naturally and are easy to construct from JSON.

---

## Create a Goal

A `Goal` represents an intended outcome — something you're trying to achieve, not just a piece of work to do.

```python
goal = ta.Goal({
    "title": "Launch the new API",
    "summary": "Ship a stable, documented v1 of the public API.",
    "status": "active",
    "priority": "high",
    "tags": ["api", "launch"],
})

atlas.add_goal(goal)
```

Goals have statuses that reflect their lifecycle:

- `proposed` — under consideration (this is the default)
- `active` — actively being pursued
- `paused` — temporarily on hold
- `achieved` — successfully completed
- `archived` — no longer relevant

---

## Create Tasks

A `Task` represents actionable work — something concrete that can be done.

```python
task1 = ta.Task({
    "title": "Write endpoint specifications",
    "summary": "Document every endpoint with request/response schemas.",
    "stage": "active",
    "priority": "high",
    "tags": ["docs", "api"],
})

task2 = ta.Task({
    "title": "Set up CI pipeline",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["infra"],
})

atlas.add_task(task1)
atlas.add_task(task2)
```

Tasks have stages that represent where they are in a workflow:

- `inbox` — captured but not yet triaged (default)
- `ready` — triaged and ready to start
- `active` — currently being worked on
- `blocked` — stuck on something
- `review` — work is done, awaiting review
- `done` — completed
- `archived` — no longer relevant

---

## Attach Tasks to Goals

Tasks don't float in isolation — they contribute toward goals:

```python
goal.attach_task(task1)
goal.attach_task(task2)
```

Now both tasks are linked to the goal. You can also create and attach in one step:

```python
task3 = goal.add_task({
    "title": "Write integration tests",
    "stage": "ready",
    "priority": "high",
})
```

This creates a new task *and* attaches it to the goal *and* registers it in the atlas — all in one call.

---

## Move Tasks Through Stages

As work progresses, tasks move:

```python
task2.move("ready", reason="CI tooling selected")
task2.move("active", reason="Starting setup")
```

Every call to `.move()` automatically records a history event with the old stage, new stage, timestamp, and your reason.

---

## Add Notes

Capture context and decisions as append-only notes:

```python
task1.note("Decided to use OpenAPI 3.1 format for all specs.")
task1.note("Need to coordinate with the frontend team on naming.")
goal.note("Targeting end of Q2 for public launch.")
```

Each note gets its own ID and timestamp. Notes appear in context summaries and history.

---

## Check Progress

Goals track the aggregate state of their attached tasks:

```python
progress = goal.progress()
print(progress)
```

Output:

```python
{
    "goal_id": "g-...",
    "task_count": 3,
    "by_stage": {"active": 2, "ready": 1},
    "done_count": 0,
    "blocked_count": 0,
    "active_count": 2,
    "done_ratio": 0.0,
}
```

---

## Retrieve and Filter

Find what you need without writing queries:

```python
# All non-archived tasks
atlas.get_tasks()

# Just the active ones
atlas.get_tasks(stage="active")

# High-priority tasks attached to a specific goal
atlas.get_tasks(goal_id=goal.id, priority="high")

# Tasks matching a tag
atlas.get_tasks(tags=["api"])

# Search by title
atlas.get_tasks(title_contains="CI")

# Sorted by priority (urgent first)
atlas.get_tasks(order_by="priority")
```

The same patterns work for goals:

```python
atlas.get_goals(status="active")
atlas.get_goals(priority="high")
```

---

## View the Board

Get a kanban-style snapshot of all tasks grouped by stage:

```python
board = atlas.board()
print(board)
```

Output shape:

```python
{
    "stages": {
        "inbox": [],
        "ready": [{"id": "t-...", "title": "Write integration tests", ...}],
        "active": [{"id": "t-...", "title": "Write endpoint specifications", ...}, ...],
        "blocked": [],
        "review": [],
        "done": [],
    }
}
```

You can scope it to a single goal:

```python
atlas.board(goal_id=goal.id)
```

---

## Inspect History

Every mutation — stage changes, priority changes, notes, attachments — is recorded automatically:

```python
# Recent events across the whole atlas
for event in atlas.recent(limit=5):
    print(f"{event.event_type}: {event.entity_id}")

# History of a specific task
for event in task1.history():
    print(f"{event.event_type} at {event.timestamp}")
    if event.reason:
        print(f"  reason: {event.reason}")
```

---

## Save and Load

Serialize the entire atlas to a JSON-friendly dict:

```python
import json

payload = atlas.to_dict()

with open("my_atlas.json", "w") as f:
    json.dump(payload, f, indent=2)
```

Reload it later:

```python
with open("my_atlas.json") as f:
    payload = json.load(f)

atlas2 = ta.Atlas.from_dict(payload)

# Everything is preserved
restored_goal = atlas2.get_goal(goal.id)
print(restored_goal.title)  # "Launch the new API"
```

IDs, relationships, notes, history — everything survives the round-trip.

---

## Summary

In this tutorial you learned the core workflow:

1. Create an `Atlas` as the container for all work
2. Define `Goal` objects for intended outcomes
3. Define `Task` objects for actionable work
4. Attach tasks to goals
5. Move tasks through stages as work progresses
6. Add notes to capture context
7. Check progress on goals
8. Filter and retrieve tasks and goals
9. View the board
10. Inspect history
11. Save and load the atlas

These ten operations cover the vast majority of what you'll do with `taskatlas`. The following tutorials go deeper into each area.
