# Filtering and Retrieval

`taskatlas` is designed so that finding the right tasks and goals is fast, readable, and doesn't require a query language. This tutorial covers every filtering option, sorting, and common retrieval patterns.

---

## The Design

Filtering in `taskatlas` uses keyword arguments. Each argument adds a condition, and all conditions must match (conjunctive / AND logic).

```python
atlas.get_tasks(stage="active", priority="high")
```

This means: give me tasks where the stage is `active` **and** the priority is `high`.

There is no query language, no builder pattern, no DSL. Just keyword arguments that read like English.

---

## Setup

```python
import taskatlas as ta

atlas = ta.Atlas({"name": "Retrieval Demo"})

# Two goals
platform = atlas.add_goal({"title": "Build platform", "status": "active", "priority": "high", "tags": ["platform"]})
docs = atlas.add_goal({"title": "Write documentation", "status": "proposed", "priority": "medium", "tags": ["docs"]})

# Several tasks across stages and priorities
tasks_data = [
    {"title": "Set up CI/CD",         "stage": "done",    "priority": "high",   "tags": ["infra", "devops"]},
    {"title": "Build auth service",   "stage": "active",  "priority": "urgent", "tags": ["backend", "auth"]},
    {"title": "Design database schema","stage": "active",  "priority": "high",   "tags": ["backend", "database"]},
    {"title": "Write API tests",      "stage": "ready",   "priority": "high",   "tags": ["testing", "backend"]},
    {"title": "Build dashboard UI",   "stage": "inbox",   "priority": "medium", "tags": ["frontend"]},
    {"title": "Set up monitoring",    "stage": "blocked",  "priority": "medium", "tags": ["infra", "monitoring"]},
    {"title": "Write user guide",     "stage": "inbox",   "priority": "low",    "tags": ["docs"]},
    {"title": "Archive old endpoints","stage": "archived", "priority": "low",    "tags": ["cleanup"]},
]

for td in tasks_data:
    t = atlas.add_task(td)
    if "docs" in td["tags"]:
        docs.attach_task(t)
    else:
        platform.attach_task(t)
```

---

## Filtering Tasks

### By stage

```python
active = atlas.get_tasks(stage="active")
# Returns: Build auth service, Design database schema

blocked = atlas.get_tasks(stage="blocked")
# Returns: Set up monitoring
```

### By priority

```python
urgent = atlas.get_tasks(priority="urgent")
# Returns: Build auth service

high = atlas.get_tasks(priority="high")
# Returns: Set up CI/CD, Design database schema, Write API tests
```

### By tags

Tags use **any-match** logic — a task matches if it has *any* of the specified tags:

```python
backend = atlas.get_tasks(tags=["backend"])
# Returns: Build auth service, Design database schema, Write API tests

infra_or_docs = atlas.get_tasks(tags=["infra", "docs"])
# Returns: Set up CI/CD, Set up monitoring, Write user guide
```

### By title (substring search)

Case-insensitive substring matching:

```python
auth_tasks = atlas.get_tasks(title_contains="auth")
# Returns: Build auth service

setup_tasks = atlas.get_tasks(title_contains="set up")
# Returns: Set up CI/CD, Set up monitoring
```

### By goal attachment

```python
platform_tasks = atlas.get_tasks(goal_id=platform.id)
# Returns: all tasks attached to the platform goal

docs_tasks = atlas.get_tasks(goal_id=docs.id)
# Returns: Write user guide
```

### By blocked status

```python
blocked = atlas.get_tasks(blocked=True)
# Returns: Set up monitoring

not_blocked = atlas.get_tasks(blocked=False)
# Returns: everything except "Set up monitoring" (and archived)
```

### By specific ID

```python
task = atlas.get_tasks(id=some_task.id)
# Returns: [that specific task]
```

---

## Combining Filters

All filters are conjunctive — they AND together:

```python
# Active AND high priority
atlas.get_tasks(stage="active", priority="high")
# Returns: Design database schema

# Backend-tagged AND ready stage
atlas.get_tasks(tags=["backend"], stage="ready")
# Returns: Write API tests

# Attached to platform goal AND blocked
atlas.get_tasks(goal_id=platform.id, blocked=True)
# Returns: Set up monitoring
```

If no tasks match all conditions, you get an empty list:

```python
atlas.get_tasks(stage="active", priority="low")
# Returns: []
```

---

## Archived Tasks

By default, archived tasks are **excluded** from all queries:

```python
all_tasks = atlas.get_tasks()
# Does NOT include "Archive old endpoints"

assert all(t.stage != "archived" for t in all_tasks)
```

To explicitly query archived tasks:

```python
archived = atlas.get_tasks(archived=True)
# Returns: Archive old endpoints
```

This applies to goals as well — archived goals are excluded by default.

---

## Sorting

Add `order_by` to sort the results:

```python
# By priority (urgent first, then high, medium, low)
by_priority = atlas.get_tasks(order_by="priority")
print([t.priority for t in by_priority])
# ['urgent', 'high', 'high', 'high', 'medium', 'medium', 'low']

# By title (alphabetical)
by_title = atlas.get_tasks(order_by="title")
print([t.title for t in by_title])
# ['Build auth service', 'Build dashboard UI', ...]

# By creation time (newest first)
by_created = atlas.get_tasks(order_by="created_at")

# By last update (most recently changed first)
by_updated = atlas.get_tasks(order_by="updated_at")
```

Sorting combines with filters:

```python
# High-priority tasks for the platform goal, sorted by creation time
atlas.get_tasks(goal_id=platform.id, priority="high", order_by="created_at")
```

---

## Filtering Goals

Goals support the same keyword argument pattern:

```python
# All non-archived goals
atlas.get_goals()

# By status
atlas.get_goals(status="active")
# Returns: Build platform

atlas.get_goals(status="proposed")
# Returns: Write documentation

# By priority
atlas.get_goals(priority="high")

# By tags
atlas.get_goals(tags=["platform"])

# By title
atlas.get_goals(title_contains="document")

# Has tasks attached
atlas.get_goals(has_tasks=True)

# Sorted
atlas.get_goals(order_by="priority")
```

---

## Direct Retrieval by ID

When you know the exact ID, use the direct getter:

```python
task = atlas.get_task("t-abc12345")
goal = atlas.get_goal("g-def67890")
```

These return the exact in-memory object (same instance, not a copy). They raise `KeyError` if the ID doesn't exist.

```python
try:
    atlas.get_task("t-nonexist")
except KeyError as e:
    print(e)  # "No task with id 't-nonexist'"
```

---

## Practical Patterns

### Daily standup summary

```python
print("BLOCKED:")
for t in atlas.get_tasks(blocked=True):
    note = t.notes[-1]["text"] if t.notes else "no details"
    print(f"  - {t.title}: {note}")

print("\nACTIVE:")
for t in atlas.get_tasks(stage="active", order_by="priority"):
    print(f"  - [{t.priority}] {t.title}")

print("\nREADY (up next):")
for t in atlas.get_tasks(stage="ready", order_by="priority"):
    print(f"  - [{t.priority}] {t.title}")
```

### Finding untagged work

```python
for task in atlas.get_tasks():
    if not task.tags:
        print(f"Untagged: {task.title}")
```

### Progress by goal

```python
for goal in atlas.get_goals(order_by="priority"):
    p = goal.progress()
    print(f"{goal.title}: {p['done_ratio']:.0%} "
          f"({p['active_count']} active, {p['blocked_count']} blocked)")
```

### Finding all tasks in a dependency chain

```python
def find_dependents(atlas, task):
    """Find all tasks that this task blocks (directly or indirectly)."""
    dependents = []
    for link in task.get_links():
        if link.kind == "blocks" and link.source_id == task.id:
            dependent = atlas.get_task(link.target_id)
            dependents.append(dependent)
            dependents.extend(find_dependents(atlas, dependent))
    return dependents
```

---

## Summary

| Filter | Applies to | Behavior |
|---|---|---|
| `stage="..."` | Tasks | Exact match |
| `status="..."` | Goals | Exact match |
| `priority="..."` | Both | Exact match |
| `tags=[...]` | Both | Any-match (OR within tags) |
| `title_contains="..."` | Both | Case-insensitive substring |
| `goal_id="..."` | Tasks | Task is attached to this goal |
| `parent_id="..."` | Both | Has this parent ID |
| `blocked=True/False` | Tasks | Stage is/isn't "blocked" |
| `has_tasks=True/False` | Goals | Has/doesn't have attached tasks |
| `archived=True/False` | Both | Default: `False` (excluded) |
| `id="..."` | Both | Exact ID match |
| `order_by="..."` | Both | Sort by field (`priority`, `title`, `created_at`, `updated_at`) |

All filters combine with AND logic. Sorting is applied after filtering.
