# Quickstart: Your First Atlas

This tutorial walks through the core workflow of `taskatlas` - creating an `Atlas`, defining `Goal` outcomes and `Task` work items, optionally anchoring them to a `Dream`, completing work with deliverable receipts, and inspecting project state.

---

## Install & Import

```bash
pip install taskatlas
```

```python
import taskatlas as ta
```

The public API exposes `Atlas`, `Dream`, `Goal`, `Task`, `Link`, and `Event`.

---

## Create an Atlas (The Sole Factory)

An `Atlas` is the root container and factory for all work. Every `Dream`, `Goal`, and `Task` is created through the `Atlas` (or a bound parent) so it is always wired into history, queries, and readiness views from birth:

```python
atlas = ta.Atlas("My First Atlas")
# Dict payloads and keyword arguments also work everywhere:
# atlas = ta.Atlas({"name": "My First Atlas"})
```

---

## Create a Goal and Tasks

A `Goal` represents a convergent, falsifiable outcome (`proposed`, `active`, `paused`, `achieved`, `abandoned`):

```python
goal = atlas.add_goal(
    "Launch the public API",
    summary="Ship a stable, documented v1 of the public API.",
    status="active",
    priority="high",
    criteria=["OpenAPI 3.1 spec published", "Integration tests green"],
    tags=["api", "launch"],
)
```

Create `Task` items directly under the goal (`inbox`, `ready`, `active`, `review`, `done`, `canceled`):

```python
spec = goal.add_task(
    "Write endpoint specifications",
    stage="active",
    priority="high",
    tags=["docs", "api"],
)

tests = goal.add_task(
    "Write integration tests",
    stage="ready",
    priority="urgent",
    tags=["testing", "api"],
)

# Express causal prerequisite: 'tests' cannot run until 'spec' is done
tests.link(spec, kind="depends_on")
```

*(Note: `Dream` sits optionally above `Goal` via `dream = atlas.add_dream(...)` and `dream.add_goal(...)` when tracking long-horizon visions across multiple waves of goals. You never have to create a `Dream` for straightforward Goal -> Task projects.)*

---

## Check the Ready Queue and Complete Work

`atlas.queue()` computes actual readiness and critical-path urgency. Because `spec` blocks the `urgent` `tests` task, `spec` automatically inherits `urgent` effective priority while `tests` waits until unblocked:

```python
print(atlas.queue())
# [{'id': 't-...', 'title': 'Write endpoint specifications',
#   'priority': 'high', 'effective_priority': 'urgent',
#   'priority_boosted': True, 'unblocks_count': 1, ...}]
```

Record narrative notes and finish `spec` with a structured completion receipt:

```python
spec.note("Standardized error envelopes on RFC 9457 Problem Details.")
spec.complete(
    "Published OpenAPI 3.1 schema covering all 14 endpoints.",
    artifacts=["specs/openapi.yaml"],
    data={"endpoints": 14},
)
```

Completing `spec` automatically unblocks `tests` and surfaces `specs/openapi.yaml` inside `tests.context(mode="full")["satisfied_dependencies"]`.

---

## Inspect Progress, Briefings, and History

```python
print(goal.progress())
# {'goal_id': 'g-...', 'task_count': 2, 'done_count': 1, 'done_ratio': 0.5, ...}

# Compact Markdown briefing ready for terminal display or an LLM prompt
print(atlas.brief())

# Every mutation is recorded automatically in the Atlas event log
for ev in atlas.recent(limit=5):
    print(f"{ev.event_type} on {ev.entity_id}: {ev.reason or ''}")
```

---

## Save and Load Atomically

```python
atlas.save("my_atlas.json")
restored = ta.Atlas.load("my_atlas.json")

assert restored.get_goal(goal.id).title == "Launch the public API"
```
