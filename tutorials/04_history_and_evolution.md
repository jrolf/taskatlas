# History, Provenance, and Temporal Deltas

Every meaningful mutation in `taskatlas` generates an immutable `Event` automatically inside a single, append-only `Atlas` event log.

---

## 1. Automatic Immutable Events & Actor Provenance

Events are stored once on `Atlas` and indexed per entity in O(1) memory, so `entity.history()` and `atlas.get_events(entity_id=...)` always agree without duplicating events in serialized JSON.

Use `atlas.as_actor(...)` (or per-call `actor=...`) to attribute changes across humans and specialized agents:

```python
import taskatlas as ta

atlas = ta.Atlas("Evolution Demo")

with atlas.as_actor("human:james"):
    dream = atlas.add_dream("Zero-Ops Edge Runtime", status="active")
    goal = dream.add_goal("Cold start under 25ms", status="active", priority="high")

with atlas.as_actor("agent:profiler"):
    task = goal.add_task("Audit import graph", stage="ready", priority="high")
    task.claim(move_active=True, reason="Running importtime profile")
    task.note("Removed lazy regex compilation overhead.", meta={"saved_ms": 9.4})
    task.complete("Cold start reduced from 31ms to 19ms.", artifacts=["benchmarks/cold.json"])
```

`Event` instances are strictly immutable (`ev.reason = ...` raises `AttributeError`, and `ev.data` is read-only):

```python
for ev in task.history():
    print(f"[{ev.timestamp}] {ev.event_type} by {ev.actor} - {ev.reason or ''}")
```

---

## 2. Incremental Tailing With `atlas.cursor` and `events_since()`

For tick-based `CHRON` jobs or multi-turn agent sessions, capture `atlas.cursor` and query chronological events (`oldest -> newest`) since that checkpoint:

```python
checkpoint = atlas.cursor

with atlas.as_actor("agent:reviewer"):
    followup = goal.add_task("Add CI cold-start regression gate", stage="ready")
    followup.move("active", reason="Wiring benchmark into GitHub Actions")

for ev in atlas.events_since(checkpoint):
    print(ev.event_type, ev.entity_id, ev.actor)
# task_created t-... agent:reviewer
# task_attached_to_goal g-... agent:reviewer
# task_stage_changed t-... agent:reviewer
```

`events_since()` accepts either an `"ev-..."` cursor ID (raising `KeyError` if unknown) or an ISO-8601 UTC timestamp string.

---

## 3. Comparing Snapshots With `atlas.diff()`

When running a sub-agent on an isolated copy (`branch = atlas.copy()`), compute a structured delta between `before` and `after`:

```python
before = atlas.copy()

followup_copy = before.get_task(followup.id)  # baseline stays untouched
# Mutate the live atlas
followup.complete("Regression threshold enforced at 25ms.")

delta = before.diff(atlas)
print(delta["task_changes"])
# {'t-...': {'stage': {'before': 'active', 'after': 'done'}, 'result': ...}}
```

`diff()` also surfaces `"newly_unblocked_tasks"` and `"newly_blocked_tasks"` so coordinators immediately see what downstream work opened up during a run.
