# taskatlas

A lean Python library for representing goals, tasks, relationships, priority, evolution, and history.

---

## What is this?

`taskatlas` gives you a clean, Pythonic object model for tracking work. It sits in the space between a simple task list and an enterprise issue tracker — expressive enough to model real project structure, lightweight enough to feel like writing regular Python.

An **Atlas** is a navigable world of:

- **Goals** — intended outcomes (what you're trying to achieve)
- **Tasks** — actionable work (what needs to be done)
- **Relationships** — typed links between entities (dependencies, blockers, support)
- **History** — automatic event records of every meaningful change
- **Views** — board, tree, queue, and summary representations of the current state

The library has **zero external dependencies**. It runs on Python 3.10+ using only the standard library.

---

## Install

```bash
pip install taskatlas
```

For development (includes pytest):

```bash
git clone https://github.com/jrolf/taskatlas.git
cd taskatlas
pip install -e ".[dev]"
```

---

## Quick Example

```python
import taskatlas as ta

# Create an atlas
atlas = ta.Atlas({"name": "My Project"})

# Define a goal — an intended outcome
goal = ta.Goal({
    "title": "Launch the public API",
    "summary": "Ship a stable, documented v1.",
    "status": "active",
    "priority": "high",
    "tags": ["api", "launch"],
})
atlas.add_goal(goal)

# Add tasks — actionable work
design = goal.add_task({
    "title": "Design endpoint schema",
    "stage": "active",
    "priority": "high",
})

tests = goal.add_task({
    "title": "Write integration tests",
    "stage": "ready",
    "priority": "high",
})

# Decompose complex tasks into subtasks
design.add_task({"title": "Define auth endpoints", "stage": "done"})
design.add_task({"title": "Define data endpoints", "stage": "active"})

# Model dependencies with typed links
tests.link(design, kind="depends_on")

# Move tasks through stages
design.move("review", reason="Implementation complete")

# Add notes to capture context
design.note("Using OpenAPI 3.1 for all endpoint specs.")

# Check goal progress
print(goal.progress())
# {'goal_id': 'g-...', 'task_count': 2, 'by_stage': {'review': 1, 'ready': 1},
#  'done_count': 0, 'done_ratio': 0.0, ...}

# View the board
print(atlas.board())

# Inspect history — every mutation is recorded automatically
for event in atlas.recent(limit=5):
    print(f"{event.event_type}: {event.reason or ''}")

# Save the entire atlas to JSON
atlas.save("project.json")

# Reload it later — everything is preserved
atlas2 = ta.Atlas.load("project.json")
```

---

## Core Concepts

### Atlas

The root container. It owns all goals, tasks, links, and events. It's the single object you serialize and restore.

```python
atlas = ta.Atlas({"name": "Q3 Roadmap"})
```

### Goal

A higher-order intended outcome. Goals have **statuses**: `proposed`, `active`, `paused`, `achieved`, `archived`.

```python
goal = ta.Goal({"title": "Improve reliability", "status": "active", "priority": "high"})
atlas.add_goal(goal)
```

### Task

An actionable work unit. Tasks have **stages**: `inbox`, `ready`, `active`, `blocked`, `review`, `done`, `archived`.

```python
task = ta.Task({"title": "Add retry logic", "stage": "ready", "priority": "high"})
atlas.add_task(task)
```

### Containment vs. Links

These are two distinct relationship types that are never conflated:

**Containment** is structural nesting — subtasks under tasks, subgoals under goals, tasks attached to goals:

```python
goal.add_task(task)         # attach task to goal
task.add_task(subtask)      # nest subtask under task
goal.add_goal(subgoal)      # nest subgoal under goal
```

**Links** are typed cross-references — dependencies, blockers, and other semantic relationships:

```python
task_a.link(task_b, kind="depends_on")
task_c.link(task_d, kind="blocks")
goal.link(other_goal, kind="supports")
```

Available link kinds: `depends_on`, `blocks`, `relates_to`, `supports`, `duplicates`, `derived_from`, `conflicts_with`.

### Notes

Append-only, timestamped annotations on any goal or task:

```python
task.note("Switched approach after profiling showed the bottleneck.")
task.note("Results look good.", meta={"runtime_ms": 340})
```

### Automatic History

Every mutation generates an `Event` — stage changes, status changes, priority changes, notes, links, attachments. You never manually log history; the library does it.

```python
task.history()                    # per-entity, newest first
atlas.get_events(limit=20)        # global, newest first
atlas.recent(limit=10)            # shortcut for recent activity
```

---

## Filtering and Retrieval

Simple keyword arguments, conjunctive (AND) logic:

```python
atlas.get_tasks(stage="active", priority="high")
atlas.get_tasks(tags=["backend"], order_by="priority")
atlas.get_tasks(goal_id=goal.id, blocked=True)
atlas.get_tasks(title_contains="auth")

atlas.get_goals(status="active")
atlas.get_goals(priority="high", tags=["core"])
```

Archived items are excluded by default. Use `archived=True` to query them explicitly.

---

## Views

Four built-in views return structured Python data (dicts and lists), ready for rendering however you need:

| Method | Returns | Purpose |
|---|---|---|
| `atlas.board()` | Tasks grouped by stage | Kanban-style workflow view |
| `atlas.tree()` | Nested goal/task hierarchy | Structural overview |
| `atlas.queue()` | Priority-sorted actionable tasks | "What should I do next?" |
| `atlas.summary()` | Aggregate counts and recent events | Dashboard / status check |

Each goal and task also has a `.context()` method that returns a focused situational summary:

```python
task.context()              # compact: id, title, stage, priority, latest note
task.context(mode="full")   # everything: links, notes, events, parent/children
goal.context(mode="full")   # includes progress snapshot
```

---

## Serialization

Full round-trip serialization to JSON files or JSON-compatible dicts:

```python
# File-based (recommended)
atlas.save("atlas.json")
atlas = ta.Atlas.load("atlas.json")

# Dict-based
payload = atlas.to_dict()           # atlas → dict
atlas = ta.Atlas.from_dict(payload) # dict → atlas
```

Everything is preserved: IDs, relationships, notes, links, events, timestamps, metadata.

---

## Project Structure

```
taskatlas/
├── __init__.py        # Public API: Atlas, Goal, Task, Link, Event
├── _atlas.py          # Atlas container and registry
├── _goal.py           # Goal class
├── _task.py           # Task class
├── _base.py           # Shared WorkItem base class
├── _link.py           # Typed relationship model
├── _event.py          # Historical event model
├── _filtering.py      # Query and sort helpers
├── _views.py          # Board, tree, queue, summary renderers
├── _identity.py       # ID generation
└── _types.py          # Constants and defaults
```

---

## Tutorials

The `tutorials/` directory contains detailed walkthroughs:

1. **[Quickstart](tutorials/01_quickstart.md)** — Your first atlas, goals, tasks, and board
2. **[Modeling a Real Project](tutorials/02_modeling_a_real_project.md)** — End-to-end example with a data platform
3. **[Relationships and Structure](tutorials/03_relationships_and_structure.md)** — Containment vs. links in depth
4. **[History and Evolution](tutorials/04_history_and_evolution.md)** — Automatic events and audit trails
5. **[Views and Context](tutorials/05_views_and_context.md)** — Board, tree, queue, summary, and context()
6. **[Persistence and Programmatic Use](tutorials/06_persistence_and_programmatic_use.md)** — Serialization, agents, and automation
7. **[Filtering and Retrieval](tutorials/07_filtering_and_retrieval.md)** — Every filter option with examples

---

## Running Tests

```bash
pytest
```

The test suite contains 213 tests covering all modules, relationships, history, views, and serialization round-trips.

---

## Design Philosophy

- **Goals are not tasks.** Goals represent intended outcomes. Tasks represent work. They have different lifecycles and different semantics.
- **Containment is not linking.** Subtask nesting is structural. Dependencies and blockers are cross-references. These are kept separate.
- **History is automatic.** Every meaningful mutation creates an event. You never have to manually log what happened.
- **Retrieval returns context, not rows.** The library should feel like asking a colleague, not querying a database.
- **The board is a view, not the ontology.** Tasks may move through stages, but the underlying reality is richer than columns on a board.
- **Stay lean.** Zero dependencies. Small API surface. No enterprise ceremony.

---

## License

MIT
