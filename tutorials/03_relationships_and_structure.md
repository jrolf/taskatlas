# Relationships and Structure

This tutorial is a deep dive into how `taskatlas` models relationships between entities. Understanding the distinction between **containment** and **links** is essential to using the library well.

---

## The Two Kinds of Relationship

`taskatlas` maintains a clear separation between two fundamentally different kinds of relationship:

| Concept | What it means | How it's stored | Examples |
|---|---|---|---|
| **Containment** | One entity structurally belongs to another | Dedicated parent/child ID fields | Subtasks, subgoals, goal-task attachment |
| **Links** | A typed cross-reference between entities | `Link` objects in a separate registry | depends_on, blocks, supports, relates_to |

This distinction is not cosmetic. Containment defines the shape of your work. Links define the connections across it.

---

## Containment: Goal-Task Attachment

Tasks contribute toward goals. A single task can be attached to multiple goals — it might serve more than one outcome.

```python
import taskatlas as ta

atlas = ta.Atlas({"name": "Relationship Demo"})

goal_api = atlas.add_goal({"title": "Ship public API", "status": "active"})
goal_docs = atlas.add_goal({"title": "Complete documentation", "status": "active"})

# A task that serves both goals
openapi_spec = atlas.add_task({
    "title": "Write OpenAPI specification",
    "stage": "active",
    "priority": "high",
})

goal_api.attach_task(openapi_spec)
goal_docs.attach_task(openapi_spec)

# The attachment is bidirectional
print(openapi_spec.goal_ids)  # [goal_api.id, goal_docs.id]
print(goal_api.task_ids)       # [openapi_spec.id]
print(goal_docs.task_ids)      # [openapi_spec.id]
```

### Creating and attaching in one step

`goal.add_task()` can accept a dict payload. It creates the task, attaches it to the goal, and registers it in the atlas:

```python
endpoint_tests = goal_api.add_task({
    "title": "Write endpoint integration tests",
    "stage": "ready",
    "priority": "high",
})

# The task is already in the atlas
assert atlas.get_task(endpoint_tests.id) is endpoint_tests
```

### Detaching

```python
goal_docs.detach_task(openapi_spec)
print(openapi_spec.goal_ids)  # [goal_api.id] — only one attachment remains
```

Detaching removes the relationship, not the task itself. The task stays in the atlas.

---

## Containment: Subgoals

Goals can nest inside other goals for hierarchical decomposition of outcomes.

```python
platform_goal = atlas.add_goal({
    "title": "Build data platform",
    "status": "active",
    "priority": "high",
})

ingestion_goal = platform_goal.add_goal({
    "title": "Reliable ingestion service",
    "status": "active",
    "priority": "urgent",
})

transform_goal = platform_goal.add_goal({
    "title": "Transformation engine",
    "status": "proposed",
    "priority": "high",
})

# Structural parent-child
print(ingestion_goal.parent_goal_id)         # platform_goal.id
print(platform_goal.child_goal_ids)          # [ingestion_goal.id, transform_goal.id]

# Retrieve child goals
children = platform_goal.get_goals()
print([g.title for g in children])
# ['Reliable ingestion service', 'Transformation engine']
```

### Rules

- A goal can have at most one parent goal.
- A goal cannot be its own subgoal.
- Attempting to re-parent a goal that already has a parent raises an error.

---

## Containment: Subtasks

Tasks can nest inside other tasks. This is how you decompose complex work.

```python
build_api = atlas.add_task({
    "title": "Build REST API",
    "stage": "active",
    "priority": "high",
})

auth = build_api.add_task({
    "title": "Implement authentication",
    "stage": "active",
    "priority": "high",
})

pagination = build_api.add_task({
    "title": "Add pagination support",
    "stage": "ready",
    "priority": "medium",
})

rate_limiting = build_api.add_task({
    "title": "Add rate limiting",
    "stage": "inbox",
    "priority": "low",
})

# Parent-child structure
print(build_api.child_task_ids)  # [auth.id, pagination.id, rate_limiting.id]
print(auth.parent_task_id)       # build_api.id

# Retrieve children
subtasks = build_api.get_tasks()
print([t.title for t in subtasks])
# ['Implement authentication', 'Add pagination support', 'Add rate limiting']
```

### Multi-level nesting

Subtasks can themselves have subtasks:

```python
jwt_setup = auth.add_task({
    "title": "Set up JWT token generation",
    "stage": "active",
    "priority": "high",
})

token_refresh = auth.add_task({
    "title": "Implement token refresh flow",
    "stage": "ready",
    "priority": "medium",
})
```

Now the hierarchy is: `build_api` → `auth` → `jwt_setup`, `token_refresh`.

### Rules

- A task can have at most one parent task.
- A task cannot be its own subtask.
- All tasks (at any nesting depth) are registered in the atlas and queryable directly.

---

## Links: Typed Cross-References

Links are fundamentally different from containment. They express how entities relate to each other *across* the hierarchy — dependencies, blockers, support relationships, and more.

### Available link kinds

| Kind | Meaning |
|---|---|
| `depends_on` | This entity requires the target to be completed first |
| `blocks` | This entity is preventing the target from progressing |
| `relates_to` | General association |
| `supports` | This entity contributes to or enables the target |
| `duplicates` | This entity is a duplicate of the target |
| `derived_from` | This entity was created based on the target |
| `conflicts_with` | This entity is in tension with the target |

### Creating links

```python
# Task-to-task dependency
pagination.link(auth, kind="depends_on")

# Task-to-task blocker
rate_limiting.link(pagination, kind="depends_on")

# Goal-to-goal support
transform_goal.link(ingestion_goal, kind="depends_on")

# Cross-type link
ingestion_goal.link(build_api, kind="supports")
```

Links are directed (source → target) but both endpoints know about the link. You can query links from either side.

### Inspecting links

```python
links = pagination.get_links()
for lk in links:
    print(f"{lk.source_id} --{lk.kind}--> {lk.target_id}")
```

### Link metadata

Links can carry metadata for additional context:

```python
auth.link(build_api, kind="blocks", meta={
    "reason": "Auth must be complete before API can go live",
    "severity": "hard-blocker",
})
```

### Removing links

```python
# Remove a specific link by target
pagination.unlink(target=auth)

# Remove all links of a specific kind
auth.unlink(kind="blocks")
```

`.unlink()` returns the count of links removed.

---

## Why the Distinction Matters

Consider this scenario: Task A is a subtask of Task B, *and* Task A depends on Task C.

If you modeled both relationships as links, you'd lose the structural meaning. Is A contained within B, or merely related to it? Does A live under B in the hierarchy, or are they peers?

In `taskatlas`:

```python
# Containment — structural nesting
task_b.add_task(task_a)  # A is structurally *inside* B

# Dependency — cross-cutting link
task_a.link(task_c, kind="depends_on")  # A depends on C, but C is elsewhere
```

This keeps the hierarchy clean and the dependency graph orthogonal. The tree view shows you the shape of your work. The links show you the connections across it.

---

## Seeing It All Together

### Tree view respects containment

```python
import json
tree = atlas.tree()
print(json.dumps(tree, indent=2))
```

The tree shows goals containing subgoals containing tasks containing subtasks — the structural hierarchy.

### Context view surfaces links

```python
ctx = pagination.context(mode="full")
print(ctx["links"])  # Shows the depends_on link to auth
```

The context method brings together *both* containment and links into a single situational summary.

### Board view flattens for workflow

```python
board = atlas.board()
```

The board groups tasks by stage regardless of hierarchy — it's a workflow view, not a structural one. Both top-level tasks and deeply nested subtasks appear side by side in their respective stage columns.

---

## Summary

| Operation | What it does | Creates history? |
|---|---|---|
| `goal.add_task(t)` | Attach task to goal | Yes (`task_attached_to_goal`) |
| `goal.attach_task(t)` | Attach existing task to goal | Yes |
| `goal.detach_task(t)` | Remove task from goal | Yes (`task_detached_from_goal`) |
| `goal.add_goal(g)` | Nest subgoal under goal | Yes (`subgoal_added`) |
| `task.add_task(t)` | Nest subtask under task | Yes (`subtask_added`) |
| `entity.link(target, kind)` | Create typed cross-reference | Yes (`link_added`) |
| `entity.unlink(target, kind)` | Remove cross-references | Yes (`link_removed`) |

Every structural change is recorded in history. The atlas always knows how it got to its current shape.
