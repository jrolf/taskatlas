# TaskAtlas Operational Guide for Agents

This guide defines the architecture, invariants, and idiomatic workflows for AI agents operating on a `taskatlas.Atlas` instance (either directly in Python or through `atlas.tool_schemas()` / `atlas.dispatch()`).

---

## 1. The Three Horizons of Intentionality

`Atlas` is the sole factory and owner of all entities. Every entity is created through the `Atlas` (or a bound parent) and carries a prefixed ID:

| Horizon | Class | Prefix | Test of Truth | Lifecycles |
|---|---|---|---|---|
| **Open Vision** *(optional)* | `Dream` | `d-` | Directional north star across waves of goals; evaluated by milestone momentum & stall detection | `seed`, `active`, `dormant`, `realized`, `abandoned` |
| **Convergent Outcome** | `Goal` | `g-` | Falsifiable outcome with verifiable `criteria` and `outcome` summary | `proposed`, `active`, `paused`, `achieved`, `abandoned` |
| **Executable Work** | `Task` | `t-` | Concrete work producing a structured completion receipt (`summary`, `artifacts`, `data`) | `inbox`, `ready`, `active`, `review`, `done`, `canceled` |

Supporting records:
- `Link` (`lk-`): Immutable cross-references (`depends_on`, `relates_to`, `derived_from`).
- `Event` (`ev-`): Immutable, single-store audit records generated automatically on every mutation.

### Core Structural Rules (Enforced Automatically in Python)

1. **No unbound entities:** Never call `ta.Dream(...)`, `ta.Goal(...)`, or `ta.Task(...)` directly. Create entities via `atlas.add_dream(...)`, `atlas.add_goal(...)` / `dream.add_goal(...)` / `goal.add_goal(...)`, and `atlas.add_task(...)` / `goal.add_task(...)` / `task.add_task(...)`.
2. **Dreams are optional and flat:** Use `Dream` when tracking enduring visions across multiple goals. You cannot attach a `Task` directly to a `Dream` without an intervening `Goal`, and `Dream` cannot participate in causal `depends_on` links (use `Goal`/`Task` for prerequisites, and `relates_to`/`derived_from` for Dream cross-references).
3. **Creation vs. attachment:** `add_goal()` / `add_task()` always *creates* a new entity. Use `attach_goal()` / `attach_task()` and `detach_goal()` / `detach_task()` to wire or re-parent existing entities.
4. **Read-only tracked attributes:** Fields like `stage`, `status`, `priority`, `title`, `tags`, `owner`, `hold_reason`, and `archived` are read-only properties. Mutate them through audited methods (`move`, `complete`, `cancel`, `hold`, `unhold`, `claim`, `release`, `set_status`, `set_priority`, `set_title`, `add_tag`, `archive`) and supply a `reason` so history explains *why* state changed.

---

## 2. Fast Agent Loop (Python API)

```python
import taskatlas as ta

atlas = ta.Atlas.load("atlas.json")

# 1. Orient in minimal tokens
print(atlas.brief(queue_limit=5))

# 2. Pull top critical-path ready leaf task (already excludes blocked, held,
#    review, paused-goal, dormant-dream, and peer-claimed tasks)
queue = atlas.queue(owner="agent:builder")
if queue:
    task = atlas.get_task(queue[0]["id"])

    with atlas.as_actor("agent:builder"):
        # 3. Inspect full hydrated context (includes upstream artifacts & Dream breadcrumb)
        ctx = task.context(mode="full")

        # 4. Claim ownership and move to active
        task.claim(move_active=True, reason="Starting top critical-path task")

        # ... execute work, record key decisions ...
        task.note("Chose SQLite WAL mode for local state index.")

        # 5. Finish with a structured deliverable receipt (automatically unblocks dependents)
        task.complete(
            summary="Implemented WAL state index; 18 unit tests passing.",
            artifacts=["src/index.py", "tests/test_index.py"],
            data={"tests_passed": 18},
        )

        # 6. Check if parent Goal criteria are now satisfied
        for gid in task.effective_goal_ids:
            goal = atlas.get_goal(gid)
            if goal.status == "active" and goal.progress()["done_ratio"] == 1.0:
                goal.achieve(outcome="All scope tasks completed and verified.")

    # 7. Persist atomically
    atlas.save("atlas.json")
```

---

## 3. Handling Impediments, Cancellation, and Archival

- **Causal prerequisite inside the Atlas:** Link with `downstream.link(prereq, kind="depends_on")` (or `prereq.blocks(downstream)`). Cycles are rejected automatically. While `prereq` is unfinished, `downstream.is_blocked` is `True` and `downstream` is withheld from `atlas.queue()`. The instant `prereq.complete(...)` runs, `downstream` unblocks and receives `prereq.result` inside `downstream.context(mode="full")["satisfied_dependencies"]`.
- **External blocker outside the Atlas:** Call `task.hold("Waiting on API key provisioning")`. This pauses readiness without overwriting `task.stage`. Call `task.unhold("Key provisioned")` to resume.
- **Dropping obsolete work:** Call `task.cancel(reason="Superseded by v2", superseded_by=new_task)` or `goal.abandon(reason="Out of scope")`. Unlike archiving an unfinished item, `cancel()` removes the task from `goal.progress()` active denominators so remaining work can still reach `100%`.
- **Shelving finished history:** Call `entity.archive()` (or pass `archive=True` to `complete()`, `cancel()`, `achieve()`, `abandon()`, or `atlas.compact(...)`). Archiving hides closed items from default views while preserving completion credit.

---

## 4. Built-In Tool Calling (`tool_schemas`, `dispatch`, `as_tools`)

When exposing `taskatlas` to an LLM tool loop (such as `ThoughtFlow`'s `AGENT` + `TOOL`), use the built-in zero-dependency tool router instead of hand-rolling schemas:

```python
# Standard JSON-Schema descriptors (9 tools)
schemas = atlas.tool_schemas()

# Execute any tool call (accepts dict or raw JSON string; always returns {"ok": bool, ...})
res = atlas.dispatch(
    "atlas_add_task",
    {
        "title": "Write migration script",
        "goal_id": goal.id,
        "stage": "ready",
        "priority": "high",
        "depends_on_ids": [prereq.id],
    },
    actor="agent:planner",
)

# ThoughtFlow one-liner:
# from thoughtflow import TOOL
# tools = [TOOL(**spec) for spec in atlas.as_tools(actor="agent:worker")]
```

| Tool Name | Purpose |
|---|---|
| `atlas_orient` | Token-tight Markdown `brief` or structured `summary` + `queue` (optional `dream_id` / `goal_id`) |
| `atlas_inspect` | Hydrated `full` / `compact` context or Markdown `brief` for any entity ID |
| `atlas_upsert_dream` | Create or update a `Dream` (`title`, `vision`, `status`, `priority`, `archive`) |
| `atlas_upsert_goal` | Create or update a `Goal` (`title`, `status`, `dream_id`, `parent_goal_id`, `criteria`, `outcome`) |
| `atlas_add_task` | Create a `Task` with optional `goal_id`, `parent_task_id`, and `depends_on_ids` |
| `atlas_update_task` | Move non-terminal `stage`, change `priority`, `claim`/`release`, `hold_reason`/`unhold`, `archive` |
| `atlas_complete_task` | Resolve a `Task` as `done` (with `summary`, `artifacts`, `data` receipt) or `canceled` |
| `atlas_note` | Append a timestamped narrative note (with optional `meta`) to any Dream, Goal, or Task |
| `atlas_link` | Add or remove a `depends_on`, `relates_to`, or `derived_from` link |

---

## 5. Multi-Turn Continuity: Cursors, Diffs, and Compaction

- **Incremental tailing:** Store `cur = atlas.cursor` at the end of a turn; call `atlas.events_since(cur)` on the next wake-up to inspect every mutation in chronological order.
- **Optimistic sub-agent review:** Pass `child_atlas = atlas.copy()` to a sub-agent, then inspect `atlas.diff(child_atlas)` (including `newly_unblocked_tasks` and `newly_blocked_tasks`) before persisting.
- **Long-horizon hygiene:** Periodically call `atlas.compact(archive_terminal_tasks=True, prune_archived=True, keep_recent_events=500)` to roll closed archived history into `atlas.meta["_compaction_ledger"]` without breaking active dependencies.
