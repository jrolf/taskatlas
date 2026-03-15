# Persistence and Programmatic Use

`taskatlas` is designed to be embedded into scripts, services, agent loops, and applications. This tutorial covers serialization, file-based persistence, programmatic construction from external data, and patterns for using the library in automated systems.

---

## Serialization: The Foundation

Every entity in the library has a `.to_dict()` method that produces a JSON-serializable dict. The atlas has `.from_dict()` to reconstruct the entire world from that dict.

```python
import taskatlas as ta
import json

atlas = ta.Atlas({"name": "Persistent Atlas"})
goal = atlas.add_goal({"title": "Ship v1", "status": "active", "priority": "high"})
task = goal.add_task({"title": "Finalize API", "stage": "active", "priority": "high"})
task.note("Targeting Friday release")
task.move("review", reason="Implementation complete")

# Serialize to dict
payload = atlas.to_dict()

# It's a plain Python dict — fully JSON-serializable
serialized = json.dumps(payload, indent=2)
print(f"Serialized size: {len(serialized)} chars")
```

---

## Saving to a File

```python
def save_atlas(atlas, path):
    with open(path, "w") as f:
        json.dump(atlas.to_dict(), f, indent=2)

def load_atlas(path):
    with open(path) as f:
        return ta.Atlas.from_dict(json.load(f))
```

Usage:

```python
save_atlas(atlas, "project.json")

# Later, or in a different process...
atlas2 = load_atlas("project.json")

# Everything is preserved
restored = atlas2.get_task(task.id)
print(restored.title)    # "Finalize API"
print(restored.stage)    # "review"
print(len(restored.notes))  # 1
print(len(restored.history()))  # 2 (note_added + task_stage_changed)
```

### What survives the round-trip

- All goal and task fields (title, summary, status/stage, priority, tags, meta)
- All IDs (stable across save/load)
- All notes (with their own IDs and timestamps)
- All structural relationships (goal-task attachment, subtasks, subgoals)
- All typed links
- All events (the complete history)
- Atlas metadata (name, custom stages/statuses, timestamps)

---

## Constructing an Atlas from External Data

One of the strengths of dict-style construction is that you can easily build an atlas from data that comes from elsewhere — a database, an API response, a spreadsheet, or an LLM output.

### From a list of dicts

```python
raw_tasks = [
    {"title": "Set up database", "priority": "urgent", "tags": ["infra"]},
    {"title": "Build user model", "priority": "high", "tags": ["backend"]},
    {"title": "Design login page", "priority": "medium", "tags": ["frontend"]},
    {"title": "Write API docs", "priority": "low", "tags": ["docs"]},
]

atlas = ta.Atlas({"name": "Imported Project"})
goal = atlas.add_goal({"title": "MVP Launch", "status": "active"})

for raw in raw_tasks:
    goal.add_task(raw)

print(f"Imported {len(atlas.get_tasks())} tasks")
```

### From an existing tracker export

Suppose you have a CSV or JSON export from another tool:

```python
import csv

atlas = ta.Atlas({"name": "Migrated from Trello"})
goal = atlas.add_goal({"title": "Sprint 12", "status": "active"})

stage_map = {
    "To Do": "ready",
    "In Progress": "active",
    "Done": "done",
    "Blocked": "blocked",
}

with open("trello_export.csv") as f:
    for row in csv.DictReader(f):
        goal.add_task({
            "title": row["name"],
            "summary": row.get("description", ""),
            "stage": stage_map.get(row["list"], "inbox"),
            "tags": row.get("labels", "").split(","),
            "meta": {"trello_id": row["id"]},
        })
```

The `meta` field is perfect for preserving foreign IDs or any non-standard data.

---

## Patterns for Scripts and Automation

### Load-modify-save cycle

The most common pattern for scripts is: load the atlas, make changes, save it back.

```python
atlas = load_atlas("project.json")

# Find blocked tasks and add a note
for task in atlas.get_tasks(blocked=True):
    task.note("Checked: still blocked as of today's standup")

# Move tasks that are done in review to done
for task in atlas.get_tasks(stage="review"):
    task.move("done", reason="Approved in review")

save_atlas(atlas, "project.json")
```

### Batch operations

```python
atlas = load_atlas("project.json")

# Escalate all medium-priority tasks for a specific goal
goal = atlas.get_goals(title_contains="Launch")[0]
for task in atlas.get_tasks(goal_id=goal.id, priority="medium"):
    task.set_priority("high", reason="Launch date approaching")

save_atlas(atlas, "project.json")
```

### Generating reports

```python
atlas = load_atlas("project.json")

summary = atlas.summary()
print(f"Project: {atlas.name}")
print(f"Total goals: {summary['goal_count']}")
print(f"Total tasks: {summary['task_count']}")
print(f"By stage: {json.dumps(summary['by_stage'], indent=2)}")
print()

for goal in atlas.get_goals():
    p = goal.progress()
    print(f"  {goal.title}: {p['done_ratio']:.0%} complete "
          f"({p['done_count']}/{p['task_count']} done, "
          f"{p['blocked_count']} blocked)")
```

---

## Using taskatlas with AI Agents

`taskatlas` is specifically designed to work well as a task context layer for AI agents. The structured outputs from `context()`, `board()`, `queue()`, and `summary()` are ideal for passing into LLM prompts.

### Providing task context to an agent

```python
def get_agent_context(atlas, task_id):
    """Build a context payload suitable for an LLM agent."""
    task = atlas.get_task(task_id)
    return {
        "current_task": task.context(mode="full"),
        "project_summary": atlas.summary(),
        "work_queue": atlas.queue()[:5],
    }

context = get_agent_context(atlas, task.id)
# Pass `context` as structured data in your agent's prompt
```

### Agent-driven task updates

An agent can use the library to record its own work:

```python
def agent_complete_task(atlas, task_id, summary_note):
    """Called when an agent finishes a task."""
    task = atlas.get_task(task_id)
    task.note(summary_note)
    task.move("done", reason="Completed by agent")
    save_atlas(atlas, "project.json")

def agent_report_blocker(atlas, task_id, blocker_description):
    """Called when an agent encounters a blocker."""
    task = atlas.get_task(task_id)
    task.move("blocked", reason=blocker_description)
    task.note(f"Blocker: {blocker_description}")
    save_atlas(atlas, "project.json")
```

### Agent picking the next task

```python
def agent_pick_next_task(atlas, goal_id=None):
    """Return the highest-priority actionable task."""
    queue = atlas.queue(goal_id=goal_id)
    if not queue:
        return None

    # Pick the first non-blocked task
    for item in queue:
        if item["stage"] != "blocked":
            task = atlas.get_task(item["id"])
            task.move("active", reason="Picked up by agent")
            return task
    return None
```

---

## Working with the Meta Field

Every goal, task, and atlas has a `meta` dict for arbitrary structured data:

```python
atlas = ta.Atlas({
    "name": "Agent Project",
    "meta": {
        "agent_model": "claude-4",
        "session_id": "abc-123",
        "max_concurrent_tasks": 3,
    },
})

task = atlas.add_task({
    "title": "Analyze dataset",
    "stage": "active",
    "meta": {
        "dataset_path": "/data/sales_2025.csv",
        "expected_rows": 50000,
        "assigned_to": "agent-worker-2",
    },
})
```

Meta is preserved through serialization and is completely freeform. Use it for anything that doesn't fit the standard fields.

---

## Notes with Metadata

Notes can also carry structured metadata:

```python
task.note("Analysis complete. Found 3 anomalies.", meta={
    "anomaly_count": 3,
    "runtime_seconds": 45.2,
    "output_path": "/results/anomalies.json",
})
```

This is particularly useful for agent systems that want to attach machine-readable results alongside human-readable descriptions.

---

## Pattern: Checkpoint and Resume

For long-running agent workflows, save the atlas periodically:

```python
def run_agent_loop(atlas_path):
    atlas = load_atlas(atlas_path)

    while True:
        task = agent_pick_next_task(atlas)
        if task is None:
            print("No more actionable tasks.")
            break

        print(f"Working on: {task.title}")
        # ... agent does its work ...

        task.note("Completed successfully")
        task.move("done", reason="Agent completed")

        # Checkpoint after each task
        save_atlas(atlas, atlas_path)

    return atlas
```

If the process crashes, you lose at most one task's worth of work. The atlas on disk always reflects the last known good state.

---

## Summary

`taskatlas` is built for programmatic use:

- **Dict construction** makes it easy to create entities from any data source
- **JSON serialization** means the atlas can be persisted anywhere
- **Structured views** (`context`, `board`, `queue`, `summary`) produce data that's ready for rendering, reporting, or LLM consumption
- **The meta field** accommodates arbitrary domain-specific data
- **Load-modify-save** is the natural pattern for scripts and automation
- **History preservation** means you always have a complete audit trail

The library deliberately avoids opinions about where you store data, how you render it, or what kind of system calls it. It's a representation layer — clean, portable, and easy to integrate.
