# TaskAtlas Guide for Agents

This document is the authoritative operational reference for AI agents working with the `taskatlas` library. It contains precise specifications, mandatory workflows, and best-practice mandates for every operation. Read this document in full before performing any operations on an Atlas.

---

## 1. Mental Model

`taskatlas` represents work as a navigable graph of five object types:

| Object | What it is | ID prefix |
|---|---|---|
| **Atlas** | The root container. Owns everything. One per session. | none |
| **Goal** | An intended outcome. What you are trying to achieve. | `g-` |
| **Task** | An actionable work unit. What needs to be done. | `t-` |
| **Link** | A typed, directed cross-reference between any two entities. | `lk-` |
| **Event** | An immutable record of a mutation. Generated automatically. | `ev-` |

**Critical distinction:** A Goal is NOT a large Task. Goals represent desired outcomes. Tasks represent executable work. They have different lifecycles, different state fields, and different semantics. You MUST use the correct type for each concept.

**Critical distinction:** Containment is NOT linking. Subtasks nested under a parent task is containment (structural). A `depends_on` relationship between two tasks is a link (semantic). These are stored differently and serve different purposes. You MUST NOT model structural nesting as links, and you MUST NOT model cross-cutting relationships as containment.

---

## 2. Import

```python
import taskatlas as ta
```

This exposes exactly five classes: `ta.Atlas`, `ta.Goal`, `ta.Task`, `ta.Link`, `ta.Event`.

---

## 3. Valid Values Reference

You MUST only use values from these exact sets. Any other value will raise `ValueError`.

### 3.1 Task Stages

```
"inbox"     — captured, not yet triaged (DEFAULT)
"ready"     — triaged and ready to start
"active"    — currently being worked on
"blocked"   — stuck, cannot proceed
"review"    — work done, awaiting review
"done"      — completed
"archived"  — no longer relevant
```

### 3.2 Goal Statuses

```
"proposed"  — under consideration (DEFAULT)
"active"    — being actively pursued
"paused"    — temporarily on hold
"achieved"  — successfully completed
"archived"  — no longer relevant
```

### 3.3 Priority Levels

```
"low"       — ordinal 0
"medium"    — ordinal 1 (DEFAULT)
"high"      — ordinal 2
"urgent"    — ordinal 3
```

### 3.4 Link Kinds

```
"depends_on"      — source requires target to be completed first
"blocks"          — source prevents target from progressing
"relates_to"      — general association
"supports"        — source contributes to or enables target
"duplicates"      — source is a duplicate of target
"derived_from"    — source was created based on target
"conflicts_with"  — source is in tension with target
```

---

## 4. Object Construction

All objects accept both dict payloads and keyword arguments. Dict payloads are preferred in serialization contexts and agent workflows for consistency. Both forms are valid throughout the library.

### 4.1 Atlas

```python
atlas = ta.Atlas({
    "name": "Project Name",         # str, optional, default ""
    "meta": {"key": "value"},       # dict, optional, default {}
    "task_stages": [...],           # list[str], optional, uses defaults above
    "goal_statuses": [...],         # list[str], optional, uses defaults above
})
```

You SHOULD always provide a `name`. You SHOULD NOT override `task_stages` or `goal_statuses` unless you have a specific reason.

### 4.2 Goal

```python
goal = ta.Goal({
    "title": "...",        # str, REQUIRED for clarity (technically defaults to "")
    "summary": "...",      # str, optional, default ""
    "status": "active",    # str, optional, default "proposed"
    "priority": "high",    # str, optional, default "medium"
    "tags": ["a", "b"],   # list[str], optional, default []
    "meta": {},            # dict, optional, default {}
})
```

### 4.3 Task

```python
task = ta.Task({
    "title": "...",        # str, REQUIRED for clarity (technically defaults to "")
    "summary": "...",      # str, optional, default ""
    "stage": "active",     # str, optional, default "inbox"
    "priority": "high",    # str, optional, default "medium"
    "tags": ["a", "b"],   # list[str], optional, default []
    "meta": {},            # dict, optional, default {}
})
```

### 4.4 Construction Rules

- You MUST always provide `title`. A Goal or Task without a title is technically valid but operationally useless.
- You SHOULD provide `summary` when the title alone is ambiguous.
- You SHOULD provide meaningful `tags` to enable filtering.
- IDs are auto-generated. You MUST NOT provide `id` unless restoring from serialized data.
- Timestamps (`created_at`, `updated_at`) are auto-generated. You MUST NOT provide them unless restoring from serialized data.

---

## 5. Registration: Adding Objects to the Atlas

Every Goal and Task MUST be registered in an Atlas before most operations will work correctly. Links, history propagation, retrieval by ID, context, and views all require atlas registration.

### 5.1 Adding Goals

```python
# Method 1: Create then add (PREFERRED for complex setup)
goal = ta.Goal({"title": "Ship v1", "status": "active", "priority": "high"})
atlas.add_goal(goal)

# Method 2: Add from dict (convenient for simple cases)
goal = atlas.add_goal({"title": "Ship v1", "status": "active", "priority": "high"})
```

Both return the Goal instance. Both register the goal and emit a `goal_created` event.

### 5.2 Adding Tasks

```python
# Method 1: Create then add
task = ta.Task({"title": "Build API", "stage": "ready", "priority": "high"})
atlas.add_task(task)

# Method 2: Add from dict
task = atlas.add_task({"title": "Build API", "stage": "ready", "priority": "high"})
```

### 5.3 Registration Rules

- Registration is **idempotent** for the same instance. Adding the same object twice is safe.
- Adding a **different** object with an **existing** ID raises `ValueError`. You MUST NOT create ID collisions.
- When you add a Goal or Task through a parent (e.g., `goal.add_task(...)` or `task.add_task(...)`), the child is automatically registered in the atlas if the parent is already registered. You do NOT need to call `atlas.add_task()` separately in that case.

---

## 6. Mandatory Workflows

This section defines the exact correct procedure for every common operation. Follow these precisely.

---

### 6.1 Workflow: Create a project from scratch

```python
import taskatlas as ta

# Step 1: Create the atlas
atlas = ta.Atlas({"name": "Project Name"})

# Step 2: Create and register top-level goals
goal = atlas.add_goal({
    "title": "Desired Outcome",
    "summary": "What success looks like.",
    "status": "active",
    "priority": "high",
    "tags": ["relevant-tag"],
})

# Step 3: Create tasks and attach them to goals
task = goal.add_task({
    "title": "Concrete work item",
    "stage": "ready",
    "priority": "high",
    "tags": ["relevant-tag"],
})

# Step 4: Decompose tasks into subtasks when appropriate
subtask = task.add_task({
    "title": "Smaller unit of work",
    "stage": "inbox",
    "priority": "medium",
})
```

**Best practice:** Create goals first, then attach tasks to goals. Do NOT create orphan tasks unless they genuinely don't belong to any goal.

---

### 6.2 Workflow: Move a task through its lifecycle

```python
# ALWAYS provide a reason when moving tasks. This is the most valuable metadata.
task.move("active", reason="Starting implementation")
task.move("blocked", reason="Waiting on API key provisioning")
task.move("active", reason="API key received, resuming")
task.move("review", reason="PR submitted for review")
task.move("done", reason="Merged and deployed")
```

**Mandates:**
- You MUST always provide a `reason` string when calling `.move()`. The reason is what makes history useful. A stage change without a reason is a lost opportunity to record context.
- You MUST NOT skip stages arbitrarily. While the library does not enforce stage ordering, moving a task from `inbox` directly to `done` indicates a modeling problem.
- You MUST NOT use `.move("archived")` as a substitute for `.move("done")`. Archived means no longer relevant. Done means completed.

---

### 6.3 Workflow: Change a goal's status

```python
goal.set_status("active", reason="Scope approved by stakeholders")
goal.set_status("paused", reason="Reprioritized to next quarter")
goal.set_status("active", reason="Back on the roadmap")
goal.set_status("achieved", reason="All success criteria met")
```

**Mandates:**
- You MUST always provide a `reason` string when calling `.set_status()`.
- `"achieved"` means the outcome was accomplished. `"archived"` means it was abandoned or became irrelevant. These are different. Use the correct one.

---

### 6.4 Workflow: Attach an existing task to a goal

When a task already exists in the atlas and needs to be associated with a goal:

```python
# By instance (PREFERRED when you have the object)
goal.attach_task(task)

# By ID string (when you only have the ID)
goal.attach_task("t-abc12345")
```

**Rules:**
- A task can be attached to **multiple** goals. This is normal and expected.
- `goal.attach_task()` does NOT create a new task. It links an existing one. To create and attach, use `goal.add_task({"title": "..."})`.
- Attaching by ID string requires the goal to be registered in an atlas. Otherwise it raises `ValueError`.

---

### 6.5 Workflow: Detach a task from a goal

```python
goal.detach_task(task)          # by instance
goal.detach_task("t-abc12345")  # by ID
```

Detaching removes the association. It does NOT delete the task from the atlas.

---

### 6.6 Workflow: Create subtask hierarchies

```python
parent = atlas.add_task({"title": "Build authentication", "stage": "active"})
child1 = parent.add_task({"title": "JWT implementation", "stage": "active"})
child2 = parent.add_task({"title": "Token refresh flow", "stage": "ready"})
grandchild = child1.add_task({"title": "Key rotation", "stage": "inbox"})
```

**Rules:**
- A task can have at most **one** parent task. Attempting to add a task to a second parent raises `ValueError`.
- A task MUST NOT be its own subtask. This raises `ValueError`.
- All tasks at any depth are registered in the atlas and queryable via `atlas.get_tasks()`.
- The queue view automatically de-emphasizes parent tasks (those with children) and surfaces leaf tasks instead.

---

### 6.7 Workflow: Create subgoal hierarchies

```python
platform = atlas.add_goal({"title": "Build platform", "status": "active"})
backend = platform.add_goal({"title": "Backend service", "status": "active"})
frontend = platform.add_goal({"title": "Frontend app", "status": "proposed"})
```

**Rules:**
- A goal can have at most **one** parent goal. Same constraint as tasks.
- A goal MUST NOT be its own subgoal.
- Subgoals are registered in the atlas automatically.

---

### 6.8 Workflow: Create typed links (dependencies, blockers, etc.)

```python
# task_a depends on task_b completing first
task_a.link(task_b, kind="depends_on")

# task_c is blocking task_d from progressing
task_c.link(task_d, kind="blocks")

# Two goals support each other
monitoring.link(platform, kind="supports")

# Cross-type: goal relates to a task
goal.link(task, kind="relates_to")
```

**Mandates:**
- You MUST use links (not containment) for dependencies, blockers, and semantic relationships.
- You MUST use containment (not links) for parent-child nesting.
- You MUST NOT link an entity to itself. This raises `ValueError`.
- Both entities involved in a link SHOULD be registered in the same atlas for the link to appear in views and context.

**When to use which link kind:**

| Situation | Use |
|---|---|
| A cannot start until B is done | `A.link(B, kind="depends_on")` |
| A is preventing B from progressing | `A.link(B, kind="blocks")` |
| A and B are related but neither depends on the other | `A.link(B, kind="relates_to")` |
| A contributes to or enables B | `A.link(B, kind="supports")` |
| A is the same work as B | `A.link(B, kind="duplicates")` |
| A was created based on or inspired by B | `A.link(B, kind="derived_from")` |
| A and B are in tension or contradiction | `A.link(B, kind="conflicts_with")` |

---

### 6.9 Workflow: Remove links

```python
# Remove a specific link to a target
task_a.unlink(target=task_b)

# Remove all links of a specific kind from this entity
task_a.unlink(kind="depends_on")

# Remove a specific link to a target of a specific kind
task_a.unlink(target=task_b, kind="depends_on")
```

`.unlink()` returns the integer count of links removed.

---

### 6.10 Workflow: Add notes

```python
# Simple text note
task.note("Switched from REST to GraphQL after benchmarking.")

# Note with structured metadata
task.note("Performance test complete.", meta={
    "p99_latency_ms": 42,
    "throughput_rps": 12000,
    "passed": True,
})
```

**Mandates:**
- You MUST add a note whenever you make a decision, encounter a blocker, change direction, or complete a significant step. Notes are the narrative thread of the work.
- Note text MUST be non-empty. Empty strings raise `ValueError`.
- Notes are **append-only**. They cannot be edited or deleted. This is by design.
- Use the `meta` dict for machine-readable data. Use `text` for human-readable narrative.

---

### 6.11 Workflow: Change priority

```python
task.set_priority("urgent", reason="Customer escalation")
goal.set_priority("high", reason="Executive sponsor added")
```

**Mandates:**
- You MUST always provide a `reason`.
- You MUST use `.set_priority()` rather than setting `.priority` directly. Direct attribute assignment does not generate history.

---

### 6.12 Workflow: Save and restore an atlas

```python
# Save (convenience method)
atlas.save("atlas.json")

# Restore (convenience method)
atlas = ta.Atlas.load("atlas.json")

# Or using raw dict round-trip:
import json
with open("atlas.json", "w") as f:
    json.dump(atlas.to_dict(), f, indent=2)
with open("atlas.json") as f:
    atlas = ta.Atlas.from_dict(json.load(f))
```

**Mandates:**
- You SHOULD use `atlas.save(path)` and `ta.Atlas.load(path)` for file persistence. You may also use `atlas.to_dict()` and `ta.Atlas.from_dict()` for dict-level serialization.
- You MUST save after completing a batch of meaningful changes. Do not rely on in-memory state persisting.
- After loading, all objects are fully functional. You can immediately call `.get_goal()`, `.get_task()`, `.move()`, `.note()`, etc.
- IDs, relationships, notes, links, events, and timestamps are all preserved through the round-trip.

---

## 7. Retrieval Reference

### 7.1 Direct retrieval by ID

```python
goal = atlas.get_goal("g-abc12345")   # returns Goal, raises KeyError if not found
task = atlas.get_task("t-def67890")   # returns Task, raises KeyError if not found
```

These return the **same in-memory instance** that was registered. This means mutations on the returned object are immediately reflected everywhere.

### 7.2 Filtered retrieval

All filters are conjunctive (AND). Archived items are excluded by default.

```python
# Tasks
atlas.get_tasks()                              # all non-archived tasks
atlas.get_tasks(stage="active")                # by stage
atlas.get_tasks(stage=["active", "blocked"])   # multi-value (OR within field)
atlas.get_tasks(priority="high")               # by priority
atlas.get_tasks(tags=["backend"])              # any tag matches (OR within tags)
atlas.get_tasks(title_contains="auth")         # case-insensitive substring
atlas.get_tasks(goal_id=goal.id)               # attached to specific goal
atlas.get_tasks(parent_id=task.id)             # children of specific task
atlas.get_tasks(linked_to=task.id)             # has any link to given entity
atlas.get_tasks(blocked=True)                  # stage == "blocked"
atlas.get_tasks(archived=True)                 # only archived tasks
atlas.get_tasks(order_by="priority")           # sorted (urgent first)
atlas.get_tasks(order_by="created_at")         # sorted (newest first)
atlas.get_tasks(order_by="updated_at")         # sorted (most recently changed first)
atlas.get_tasks(limit=5)                       # return at most 5 results

# Goals
atlas.get_goals()                              # all non-archived goals
atlas.get_goals(status="active")               # by status
atlas.get_goals(status=["active", "proposed"]) # multi-value (OR within field)
atlas.get_goals(priority="high")               # by priority
atlas.get_goals(tags=["core"])                 # by tags
atlas.get_goals(title_contains="platform")     # by title substring
atlas.get_goals(has_tasks=True)                # only goals with attached tasks
atlas.get_goals(parent_id=goal.id)             # children of specific goal

# Combining filters (all must match)
atlas.get_tasks(stage="active", priority="high", tags=["backend"])
```

**Best practices for agents:**
- When checking for blocked work, use `atlas.get_tasks(blocked=True)`.
- When looking for the next task to work on, use `atlas.queue()` instead of manual filtering. The queue is purpose-built for this.
- When you need to understand the state of a specific goal, use `goal.progress()`.

---

## 8. Context Retrieval

The `.context()` method is the **single most important method for agents**. It returns a structured dict with everything situationally relevant about an entity.

### 8.1 Task context

```python
# Compact mode (DEFAULT) — essentials only
task.context()
# Returns:
# {
#     "id": "t-...",
#     "title": "...",
#     "stage": "active",
#     "priority": "high",
#     "tags": [...],
#     "parent_task_id": "t-..." or absent,    # only if has parent
#     "subtask_count": 3 or absent,            # only if has children
#     "goal_ids": ["g-..."] or absent,         # only if attached to goals
#     "latest_note": "..." or absent,          # only if has notes
# }

# Full mode — everything
task.context(mode="full")
# Returns all of the above plus:
# {
#     "summary": "...",
#     "parent_task_id": "t-..." or None,
#     "child_task_ids": [...],
#     "goal_ids": [...],
#     "links": [<link dicts>],
#     "notes": [<last 5 notes>],
#     "recent_events": [<last 10 events>],
# }
```

### 8.2 Goal context

```python
# Compact
goal.context()
# Returns:
# {
#     "id": "g-...",
#     "title": "...",
#     "status": "active",
#     "priority": "high",
#     "tags": [...],
#     "task_count": 5 or absent,
#     "subgoal_count": 2 or absent,
#     "latest_note": "..." or absent,
# }

# Full
goal.context(mode="full")
# Returns all of the above plus:
# {
#     "summary": "...",
#     "parent_goal_id": "g-..." or None,
#     "child_goal_ids": [...],
#     "task_ids": [...],
#     "links": [<link dicts>],
#     "progress": {
#         "goal_id": "g-...",
#         "task_count": 5,
#         "by_stage": {"active": 2, "done": 3},
#         "done_count": 3,
#         "blocked_count": 0,
#         "active_count": 2,
#         "done_ratio": 0.6,
#     },
#     "notes": [<last 5 notes>],
#     "recent_events": [<last 10 events>],
# }
```

**Mandates for agents:**
- Before performing any operation on a task or goal, you SHOULD call `.context()` to understand its current state.
- Use `mode="compact"` for quick orientation. Use `mode="full"` when you need to understand relationships, blockers, or recent history.
- When building prompts or context windows, pass the dict from `.context(mode="full")` as structured data.

---

## 9. Views Reference

Views return structured data about the entire atlas. They are read-only snapshots.

### 9.1 Board — tasks grouped by stage

```python
atlas.board()                     # all non-archived tasks, grouped by stage
atlas.board(goal_id=goal.id)      # scoped to a specific goal
atlas.board(priority="high")      # with additional filters
```

Returns:
```python
{
    "stages": {
        "inbox": [{"id": "t-...", "title": "...", "priority": "...", "tags": [...]}],
        "ready": [...],
        "active": [...],
        "blocked": [...],
        "review": [...],
        "done": [...],
    }
}
```

**When to use:** When you need a workflow-oriented snapshot of where all tasks currently sit.

### 9.2 Tree — hierarchical structure

```python
atlas.tree()
```

Returns a nested dict showing: top-level goals → subgoals → attached tasks → subtasks. Orphan tasks (not attached to any goal and without parents) appear under `unattached_tasks`. Archived items are excluded.

**When to use:** When you need to understand the structural shape of the project.

### 9.3 Queue — what to work on next

```python
atlas.queue()                     # all actionable work, priority-sorted
atlas.queue(goal_id=goal.id)      # scoped to a specific goal
```

Returns a list of dicts, each containing: `id`, `title`, `stage`, `priority`, `tags`, `goal_ids`.

**Key behaviors:**
- Excludes done and archived tasks.
- Excludes parent tasks that have children (surfaces leaf tasks instead).
- Sorted by priority descending (urgent first).

**When to use:** When you need to decide what to work on next. This is the recommended method for agents selecting their next task.

### 9.4 Summary — aggregate overview

```python
atlas.summary()
```

Returns:
```python
{
    "goal_count": 5,
    "task_count": 23,
    "by_stage": {"inbox": 3, "active": 8, "done": 10, ...},
    "by_status": {"active": 3, "achieved": 2},
    "recent_events": [<last 10 events as dicts>],
}
```

**When to use:** For quick health checks and status reports.

---

## 10. History and Events Reference

### 10.1 How events are generated

Every mutation method automatically creates an Event. You NEVER create events manually. The following methods generate events:

| Method | Event type | Data fields |
|---|---|---|
| `atlas.add_goal(...)` / `goal.add_goal(...)` | `goal_created` | `title` |
| `atlas.add_task(...)` / `goal.add_task(...)` / `task.add_task(...)` | `task_created` | `title` |
| `task.move(stage, reason)` | `task_stage_changed` | `old_stage`, `new_stage` |
| `goal.set_status(status, reason)` | `goal_status_changed` | `old_status`, `new_status` |
| `entity.set_priority(priority, reason)` | `priority_changed` | `old`, `new` |
| `entity.set_title(title, reason)` | `title_changed` | `old`, `new` |
| `entity.set_summary(summary, reason)` | `summary_changed` | `old`, `new` |
| `entity.add_tag(tag)` | `tag_added` | `tag` |
| `entity.remove_tag(tag)` | `tag_removed` | `tag` |
| `entity.note(text)` | `note_added` | `note_id` |
| `goal.add_task(...)` / `goal.attach_task(...)` | `task_attached_to_goal` | `task_id` |
| `goal.detach_task(...)` | `task_detached_from_goal` | `task_id` |
| `goal.add_goal(...)` | `subgoal_added` | `child_id` |
| `goal.detach_goal(...)` | `subgoal_detached` | `child_id` |
| `task.add_task(...)` | `subtask_added` | `child_id` |
| `task.detach_task(...)` | `subtask_detached` | `child_id` |
| `entity.link(target, kind)` | `link_added` | `link_id`, `target_id`, `kind` |
| `entity.unlink(...)` | `link_removed` | `link_id`, `kind` |

### 10.2 Querying history

```python
# Per-entity (newest first)
task.history()                                    # all events for this task
task.history(limit=5)                             # last 5
task.history(event_type="task_stage_changed")     # only stage changes

# Atlas-wide (newest first)
atlas.get_events()                                # all events
atlas.get_events(entity_id=task.id)               # for a specific entity
atlas.get_events(event_type="note_added")         # by type
atlas.get_events(limit=10)                        # with limit
atlas.recent(limit=20)                            # shortcut, default limit 20
```

### 10.3 Event object fields

Every Event has: `id` (str), `event_type` (str), `entity_id` (str), `entity_type` (str, `"goal"` or `"task"`), `timestamp` (ISO 8601 str), `data` (dict), `reason` (str or None).

---

## 11. Progress Tracking

```python
progress = goal.progress()
```

Returns:
```python
{
    "goal_id": "g-...",
    "task_count": 8,          # total tasks attached to this goal
    "by_stage": {
        "active": 3,
        "done": 4,
        "blocked": 1,
    },
    "done_count": 4,
    "blocked_count": 1,
    "active_count": 3,
    "done_ratio": 0.5,        # 4/8
}
```

**Mandates:**
- Check `goal.progress()` before reporting on goal status.
- If `blocked_count > 0`, investigate blocked tasks before proceeding with other work under that goal.
- If `done_ratio == 1.0` and the goal status is still `"active"`, consider calling `goal.set_status("achieved", reason="All tasks complete")`.

---

## 12. Rules and Invariants

These will raise exceptions if violated. Know them to avoid errors.

### 12.1 ValueError

- Task stage not in the allowed set
- Goal status not in the allowed set
- Priority not in `("low", "medium", "high", "urgent")`
- Link kind not in the allowed set
- Task added as its own subtask
- Goal added as its own subgoal
- Task already has a different parent
- Goal already has a different parent
- Empty note text
- Duplicate ID (different object, same ID added to atlas)
- Linking an entity to itself

### 12.2 KeyError

- `atlas.get_goal(id)` with nonexistent ID
- `atlas.get_task(id)` with nonexistent ID
- `atlas.board(goal_id=id)` with nonexistent goal ID
- `atlas.queue(goal_id=id)` with nonexistent goal ID

### 12.3 TypeError

- Passing non-dict, non-Goal to `atlas.add_goal()`
- Passing non-dict, non-Task to `atlas.add_task()`
- Passing non-Goal, non-Task to `.link()` as target

---

## 13. Best Practices for Agent Workflows

### 13.1 Starting a session

When beginning work on a project:

```python
import taskatlas as ta

# Load existing atlas
atlas = ta.Atlas.load("atlas.json")

# Orient yourself
summary = atlas.summary()
blocked = atlas.get_tasks(blocked=True)
queue = atlas.queue()
```

You MUST orient before acting. Check the summary, check for blocked tasks, and review the queue.

### 13.2 Selecting the next task

```python
queue = atlas.queue()
if not queue:
    # No actionable work. Check if goals should be updated.
    pass
else:
    next_item = queue[0]  # highest priority actionable leaf task
    task = atlas.get_task(next_item["id"])
    
    # Read its context before starting
    ctx = task.context(mode="full")
    
    # Check for blockers in its links
    blockers = [lk for lk in ctx.get("links", []) if lk["kind"] in ("depends_on", "blocks")]
    
    # Move to active
    task.move("active", reason="Picked up from queue")
```

You MUST check context and links before starting a task. A task may have dependencies that need to be resolved first.

### 13.3 Recording work as you go

```python
# Starting work
task.move("active", reason="Beginning implementation")

# Capturing decisions
task.note("Chose PostgreSQL over MySQL for JSON column support.")

# Encountering a blocker
task.move("blocked", reason="Requires admin API key not yet provisioned")
task.note("Requested API key from infra team, ETA 2 hours.")

# Resuming
task.move("active", reason="API key received")

# Completing
task.note("Implementation complete. All tests passing.", meta={"tests_passed": 47})
task.move("review", reason="PR #234 submitted")

# After review
task.move("done", reason="PR merged, deployed to production")
```

You MUST leave a narrative trail. Every stage change gets a reason. Significant decisions and findings get notes.

### 13.4 Completing a goal

When all tasks under a goal are done:

```python
progress = goal.progress()
if progress["done_ratio"] == 1.0:
    goal.set_status("achieved", reason="All tasks complete. Outcome delivered.")
elif progress["done_ratio"] > 0.8:
    goal.note(f"Near completion: {progress['done_ratio']:.0%} done. "
              f"{progress['blocked_count']} still blocked.")
```

### 13.5 Saving after changes

```python
# After each meaningful batch of operations
atlas.save("atlas.json")
```

You MUST save after completing a logical unit of work. Do not accumulate large numbers of unsaved changes.

### 13.6 Building context for another agent or LLM

```python
def build_agent_context(atlas, task_id):
    task = atlas.get_task(task_id)
    goal_contexts = []
    for gid in task.goal_ids:
        goal = atlas.get_goal(gid)
        goal_contexts.append(goal.context(mode="compact"))
    
    return {
        "task": task.context(mode="full"),
        "parent_goals": goal_contexts,
        "project_summary": atlas.summary(),
        "work_queue": atlas.queue()[:5],
        "recent_activity": [e.to_dict() for e in atlas.recent(limit=10)],
    }
```

You SHOULD use `.context(mode="full")` for the primary task and `.context(mode="compact")` for surrounding entities to manage context window size.

---

## 14. Anti-Patterns: What NOT to Do

### 14.1 Do NOT create tasks without attaching them to goals

```python
# BAD: orphan task
atlas.add_task({"title": "Do something"})

# GOOD: task attached to a goal
goal.add_task({"title": "Do something", "stage": "inbox"})
```

Every task should contribute toward an outcome. If a task doesn't belong to any goal, that's a signal the goal structure is incomplete.

### 14.2 Do NOT use containment where you need links

```python
# BAD: modeling a dependency as a subtask
task_b.add_task(task_a)  # implies A is a sub-unit of B

# GOOD: modeling a dependency as a link
task_a.link(task_b, kind="depends_on")  # A depends on B, they are peers
```

Subtasks are parts of a larger task. Dependencies are between separate tasks.

### 14.3 Prefer mutation methods for tracked fields

```python
# These work but generate events WITHOUT a reason:
task.stage = "active"
task.priority = "high"

# PREFERRED: history includes a reason
task.move("active", reason="Starting work")
task.set_priority("high", reason="Escalated")
```

Direct assignment to `stage`, `status`, and `priority` is now validated and generates events, but the `reason` field will be `None`. Always prefer the mutation methods to include context.

### 14.4 Do NOT omit reasons

```python
# BAD: reason is None
task.move("blocked")

# GOOD: reason explains why
task.move("blocked", reason="Waiting on database migration to complete")
```

Reasons are what make the history useful. A history of state changes without reasons is nearly worthless.

### 14.5 Do NOT use `"archived"` when you mean `"done"` or `"achieved"`

```python
# BAD: archiving completed work
task.move("archived")  # means "no longer relevant"

# GOOD: marking work as complete
task.move("done", reason="Completed and verified")
```

Archive is for abandonment. Done is for completion. These have different semantics in filtering and views.

### 14.6 Do NOT create deeply nested goals as a substitute for task decomposition

```python
# BAD: goal → subgoal → subgoal → subgoal (deep goal nesting for work items)

# GOOD: goal → tasks → subtasks (goals for outcomes, tasks for work)
```

Goals should represent outcomes at 1-2 levels of nesting. Work decomposition belongs in the task hierarchy.

---

## 15. Complete Method Reference

### Atlas

| Method | Returns | Description |
|---|---|---|
| `add_goal(goal_or_dict)` | `Goal` | Register a goal |
| `add_task(task_or_dict)` | `Task` | Register a task |
| `get_goal(id)` | `Goal` | Retrieve by ID (raises KeyError) |
| `get_task(id)` | `Task` | Retrieve by ID (raises KeyError) |
| `get_goals(**filters)` | `list[Goal]` | Filtered retrieval |
| `get_tasks(**filters)` | `list[Task]` | Filtered retrieval |
| `get_events(entity_id, event_type, limit)` | `list[Event]` | Query event log |
| `recent(limit=20)` | `list[Event]` | Shortcut for recent events |
| `board(goal_id, **filters)` | `dict` | Kanban view |
| `tree()` | `dict` | Hierarchy view |
| `queue(goal_id, limit)` | `list[dict]` | Priority queue |
| `summary()` | `dict` | Aggregate overview |
| `to_dict()` | `dict` | Serialize entire atlas |
| `Atlas.from_dict(payload)` | `Atlas` | Restore from serialized data |
| `save(path)` | `None` | Serialize to JSON file |
| `Atlas.load(path)` | `Atlas` | Restore from JSON file |

### Goal

| Method | Returns | Description |
|---|---|---|
| `set_status(status, reason)` | `None` | Change lifecycle status |
| `set_priority(priority, reason)` | `None` | Change priority |
| `set_title(title, reason)` | `None` | Change title (tracked) |
| `set_summary(summary, reason)` | `None` | Change summary (tracked) |
| `add_tag(tag)` | `None` | Add a tag (tracked) |
| `remove_tag(tag)` | `None` | Remove a tag (tracked) |
| `note(text, meta)` | `dict` | Append a note |
| `add_task(task_or_dict)` | `Task` | Create/attach a task |
| `attach_task(task_or_id)` | `None` | Attach existing task |
| `detach_task(task_or_id)` | `None` | Detach a task |
| `get_tasks()` | `list[Task]` | Get attached tasks |
| `add_goal(goal_or_dict)` | `Goal` | Add a subgoal |
| `detach_goal(goal_or_id)` | `None` | Detach a subgoal |
| `get_goals()` | `list[Goal]` | Get child goals |
| `link(target, kind, meta)` | `Link` | Create typed link (idempotent) |
| `unlink(target, kind)` | `int` | Remove links |
| `get_links(kind, direction)` | `list[Link]` | Get links (optionally filtered) |
| `get_blockers()` | `list[Link]` | Get blocking links |
| `get_dependents()` | `list[Link]` | Get entities waiting on this |
| `history(limit, event_type)` | `list[Event]` | Query local history |
| `context(mode)` | `dict` | Situational summary |
| `progress()` | `dict` | Task completion stats |
| `to_dict()` | `dict` | Serialize |

### Task

| Method | Returns | Description |
|---|---|---|
| `move(stage, reason)` | `None` | Change stage |
| `set_priority(priority, reason)` | `None` | Change priority |
| `set_title(title, reason)` | `None` | Change title (tracked) |
| `set_summary(summary, reason)` | `None` | Change summary (tracked) |
| `add_tag(tag)` | `None` | Add a tag (tracked) |
| `remove_tag(tag)` | `None` | Remove a tag (tracked) |
| `note(text, meta)` | `dict` | Append a note |
| `add_task(task_or_dict)` | `Task` | Add a subtask |
| `detach_task(task_or_id)` | `None` | Detach a subtask |
| `get_tasks()` | `list[Task]` | Get child tasks |
| `link(target, kind, meta)` | `Link` | Create typed link (idempotent) |
| `unlink(target, kind)` | `int` | Remove links |
| `get_links(kind, direction)` | `list[Link]` | Get links (optionally filtered) |
| `get_blockers()` | `list[Link]` | Get blocking links |
| `get_dependents()` | `list[Link]` | Get entities waiting on this |
| `history(limit, event_type)` | `list[Event]` | Query local history |
| `context(mode)` | `dict` | Situational summary |
| `to_dict()` | `dict` | Serialize |

---

## 16. Quick Decision Framework

When you are unsure what to do, follow this framework:

1. **Orient:** Call `atlas.summary()` and `atlas.queue()`. Understand the current state.
2. **Inspect:** For any entity you plan to act on, call `.context(mode="full")` first.
3. **Check blockers:** Before moving a task to `active`, check its links for unresolved `depends_on` relationships.
4. **Act with reasons:** Every `.move()`, `.set_status()`, `.set_priority()` call MUST include a reason.
5. **Document:** Add `.note()` for every decision, finding, or significant event during execution.
6. **Update progress:** After completing tasks, check `goal.progress()` and update goal status if appropriate.
7. **Save:** Persist the atlas to disk after each logical unit of work.
