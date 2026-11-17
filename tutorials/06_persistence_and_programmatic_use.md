# Persistence, Compaction, and Agent Tool Integration

`taskatlas` is designed for scripts, serverless handlers, and multi-agent loops that require crash-safe persistence, worker coordination, and zero-dependency LLM tool bindings.

---

## 1. Crash-Safe Atomic Persistence (`save` / `load`)

`atlas.save(path)` writes to a sibling temporary file, flushes and calls `os.fsync()`, and swaps via POSIX-atomic `os.replace()`. If a Lambda invocation times out or a worker crashes mid-save, the prior `atlas.json` on disk is never truncated or corrupted.

`Atlas.load(path)` and `Atlas.from_dict(payload)` verify bidirectional referential integrity and DAG acyclicity on load (and seamlessly migrate legacy `0.2.0` files):

```python
import taskatlas as ta

atlas = ta.Atlas("Production Runbook")
goal = atlas.add_goal("Zero-downtime deploy", status="active", priority="urgent")
task = goal.add_task("Drain canary nodes", stage="ready", priority="high")

atlas.save("runbook.json")
restored = ta.Atlas.load("runbook.json")
```

---

## 2. Multi-Worker Coordination With `claim()` and `release()`

When multiple agents pull from a shared Atlas, `claim()` prevents double-pickup and filters claimed tasks out of peer worker queues automatically:

```python
task.complete("Canary nodes drained")
t1 = goal.add_task("Migrate shard 1", stage="ready", priority="high")
t2 = goal.add_task("Migrate shard 2", stage="ready", priority="high")

# Worker 1 claims the top task and moves it to 'active'
w1_next = atlas.queue(owner="agent:worker-1")[0]
atlas.get_task(w1_next["id"]).claim("agent:worker-1", move_active=True)

# Worker 2 asks for work: t1 is automatically excluded; Worker 2 gets t2!
w2_next = atlas.queue(owner="agent:worker-2")[0]
assert w2_next["id"] == t2.id
```

---

## 3. Long-Horizon Hygiene With `atlas.compact()`

Over months of continuous agent operation, completed tasks and fine-grained events accumulate. `atlas.compact()` shelves terminal items, safely prunes archived items that have *no* active children or active dependents into `atlas.meta["_compaction_ledger"]`, and trims old events:

```python
t1.complete("Shard 1 migrated")
t2.complete("Shard 2 migrated")
goal.achieve(outcome="All shards migrated with zero error budget burn.")

report = atlas.compact(
    archive_terminal_tasks=True,
    archive_terminal_goals=True,
    prune_archived=True,
    keep_recent_events=100,
    actor="system:compactor",
)
print(report)
# {'archived_tasks': 3, 'archived_goals': 1, 'pruned_tasks': 2, ...}
```

---

## 4. Zero-Dependency Agent Tool Seam (`tool_schemas`, `dispatch`, `as_tools`)

Instead of writing custom tool wrappers for every agent, use `Atlas`'s built-in tool router:

```python
# 1. Inspect portable JSON-Schema definitions (9 tools)
schemas = atlas.tool_schemas()

# 2. Dispatch a tool call (accepts a Python dict or raw JSON string from an LLM)
orient = atlas.dispatch("atlas_orient", {"format": "brief"}, actor="agent:planner")
if orient["ok"]:
    print(orient["result"]["brief"])

# 3. Bind directly into ThoughtFlow in one line (zero extra dependencies):
# from thoughtflow import AGENT, LLM, TOOL
# tools = [TOOL(**spec) for spec in atlas.as_tools(actor="agent:worker")]
# agent = AGENT(llm=LLM("openai:gpt-4o"), tools=tools)
```

Every `dispatch()` call catches invalid IDs, lifecycle violations, and dependency cycles cleanly, returning `{"ok": False, "error": "...", "hint": "..."}` so tool-calling agents can self-correct on the next turn without crashing the loop.
