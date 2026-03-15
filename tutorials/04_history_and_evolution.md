# History and Evolution

One of the most important design properties of `taskatlas` is that **every meaningful mutation generates a historical event automatically**. You never have to manually log what happened. The library does it for you.

This tutorial explores the event system, how to query history, and how to use it for understanding how work evolves over time.

---

## The Principle

Every time you call a method that changes state — moving a task, changing a status, adding a note, creating a link, attaching a task to a goal — an `Event` is created and appended to two places:

1. The **entity's** local event list (accessible via `entity.history()`)
2. The **atlas's** global event list (accessible via `atlas.get_events()` and `atlas.recent()`)

You get both a per-item audit trail and a global activity feed, with zero manual bookkeeping.

---

## What Gets Recorded

```python
import taskatlas as ta

atlas = ta.Atlas({"name": "History Demo"})
goal = atlas.add_goal({
    "title": "Design the API",
    "status": "proposed",
    "priority": "high",
})
```

Just by creating and adding this goal, an event already exists:

```python
events = atlas.get_events()
for ev in events:
    print(f"{ev.event_type}: {ev.data}")
```

```
goal_created: {'title': 'Design the API'}
```

Now let's generate more history:

```python
# Status change
goal.set_status("active", reason="Scope approved by team lead")

# Priority change
goal.set_priority("urgent", reason="Deadline moved up")

# Note
goal.note("Need to finalize naming conventions before implementation begins.")

# Task attachment
task = goal.add_task({
    "title": "Draft class interface",
    "stage": "ready",
    "priority": "high",
})

# Subtask
subtask = task.add_task({
    "title": "Define constructor pattern",
    "stage": "inbox",
})

# Task movement
task.move("active", reason="Starting implementation")
task.move("blocked", reason="Waiting on naming decision")

# Link
task.link(goal, kind="supports")

# Link removal
task.unlink(target=goal, kind="supports")
```

---

## Querying Entity History

Every goal and task has its own local history:

```python
for ev in goal.history():
    print(f"[{ev.timestamp}] {ev.event_type}")
    if ev.reason:
        print(f"    reason: {ev.reason}")
    if ev.data:
        print(f"    data: {ev.data}")
```

Output (newest first):

```
[2025-...] task_attached_to_goal
    data: {'task_id': 't-...'}
[2025-...] note_added
    data: {'note_id': 'n-...'}
[2025-...] priority_changed
    reason: Deadline moved up
    data: {'old': 'high', 'new': 'urgent'}
[2025-...] goal_status_changed
    reason: Scope approved by team lead
    data: {'old_status': 'proposed', 'new_status': 'active'}
```

### Filtering by event type

```python
# Only status changes
status_changes = goal.history(event_type="goal_status_changed")

# Only notes
note_events = goal.history(event_type="note_added")
```

### Limiting results

```python
# Last 3 events
recent = task.history(limit=3)
```

---

## Querying Atlas-Wide History

The atlas has a global event log that captures everything across all entities:

```python
# All events, newest first
all_events = atlas.get_events()

# Shortcut for recent activity
recent = atlas.recent(limit=10)

# Filter by entity
goal_events = atlas.get_events(entity_id=goal.id)

# Filter by event type
all_stage_changes = atlas.get_events(event_type="task_stage_changed")

# Combine filters
task_notes = atlas.get_events(entity_id=task.id, event_type="note_added")
```

---

## The Event Object

Each event is an `Event` instance with these fields:

| Field | Description |
|---|---|
| `id` | Unique event ID (prefixed `ev-`) |
| `event_type` | What happened (e.g., `task_stage_changed`) |
| `entity_id` | The ID of the goal or task that was mutated |
| `entity_type` | `"goal"` or `"task"` |
| `timestamp` | ISO 8601 UTC timestamp |
| `data` | Dict of change details (varies by event type) |
| `reason` | Optional human-readable reason |

### Event types and their data

| Event type | Entity type | Data fields |
|---|---|---|
| `goal_created` | goal | `title` |
| `task_created` | task | `title` |
| `goal_status_changed` | goal | `old_status`, `new_status` |
| `task_stage_changed` | task | `old_stage`, `new_stage` |
| `priority_changed` | goal/task | `old`, `new` |
| `note_added` | goal/task | `note_id` |
| `task_attached_to_goal` | goal | `task_id` |
| `task_detached_from_goal` | goal | `task_id` |
| `subgoal_added` | goal | `child_id` |
| `subtask_added` | task | `child_id` |
| `link_added` | goal/task | `link_id`, `target_id`, `kind` |
| `link_removed` | goal/task | `link_id`, `kind` |

---

## Reasons: Capturing the Why

Many mutation methods accept an optional `reason` parameter:

```python
task.move("blocked", reason="Waiting on schema decision")
goal.set_status("paused", reason="Reprioritized to next quarter")
task.set_priority("urgent", reason="Customer escalation")
```

Reasons are preserved in the event and appear in history queries. They're invaluable for understanding *why* something changed, not just *what* changed.

---

## Building a Changelog

You can use the event system to generate a human-readable changelog:

```python
def format_event(ev):
    line = f"[{ev.timestamp[:19]}] {ev.event_type}"
    if ev.reason:
        line += f" — {ev.reason}"

    if ev.event_type == "task_stage_changed":
        line += f" ({ev.data['old_stage']} → {ev.data['new_stage']})"
    elif ev.event_type == "goal_status_changed":
        line += f" ({ev.data['old_status']} → {ev.data['new_status']})"
    elif ev.event_type == "priority_changed":
        line += f" ({ev.data['old']} → {ev.data['new']})"

    return line

print("Recent Activity:")
for ev in atlas.recent(limit=15):
    print(f"  {format_event(ev)}")
```

---

## Tracking a Task's Full Journey

One powerful pattern is reconstructing the full journey of a single task:

```python
task = atlas.add_task({"title": "Implement auth", "stage": "inbox"})
task.move("ready", reason="Requirements finalized")
task.note("Using JWT with RS256")
task.move("active", reason="Dev started")
task.note("Decided against OAuth2 for v1")
task.move("blocked", reason="Waiting on key management service")
task.set_priority("urgent", reason="Security review requires this first")
task.move("active", reason="KMS available")
task.move("review", reason="PR submitted")
task.note("Reviewer: @security-team")
task.move("done", reason="Merged and deployed")

# The full story, oldest first
for ev in reversed(task.history()):
    print(format_event(ev))
```

This produces a complete narrative of the task from creation through completion, including every decision point and reason.

---

## History Survives Serialization

Events are preserved through save/load cycles:

```python
import json

payload = atlas.to_dict()
atlas2 = ta.Atlas.from_dict(payload)

# History is intact
restored_task = atlas2.get_task(task.id)
assert len(restored_task.history()) == len(task.history())

restored_events = atlas2.get_events()
assert len(restored_events) == len(atlas.get_events())
```

This means you can persist an atlas to disk, load it weeks later, and still have the complete history of every change.

---

## Design Philosophy

The event system in `taskatlas` follows a few deliberate principles:

1. **Automatic, not manual.** You never call "create event." Mutations do it.
2. **Append-only.** Events are never edited or deleted. The log is truthful.
3. **Dual storage.** Each entity has its own history *and* the atlas has the global timeline.
4. **Structured data.** Events carry typed data dicts, not just strings. This makes them programmatically useful.
5. **Reasons are optional but encouraged.** The `reason` parameter costs nothing when omitted but provides enormous value when used.

The result is that every atlas carries its own narrative history — not just what the current state is, but how it got there.
