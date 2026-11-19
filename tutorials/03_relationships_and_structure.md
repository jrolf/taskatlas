# Relationships and Structure

`taskatlas` separates **containment** (the structural shape of work) from **links** (causal prerequisites and cross-cutting lineage).

---

## 1. Containment: `Dream -> Goal -> Subgoal -> Task -> Subtask`

| Relationship | Create New | Wire Existing | Cardinality |
|---|---|---|---|
| `Dream -> Goal` | `dream.add_goal(...)` | `dream.attach_goal(g)` / `detach_goal(g)` | Many root goals per Dream; at most 1 Dream per Goal |
| `Goal -> Subgoal` | `goal.add_goal(...)` | `goal.attach_goal(sub)` / `detach_goal(sub)` | Strict tree (at most 1 parent Goal; cycle-checked) |
| `Goal -> Task` | `goal.add_task(...)` | `goal.attach_task(t)` / `detach_task(t)` | Many-to-many (a shared Task may advance multiple Goals) |
| `Task -> Subtask` | `task.add_task(...)` | `task.attach_task(sub)` / `detach_task(sub)` | Strict tree (at most 1 parent Task; cycle-checked) |

Key structural invariants:
- **No `Dream -> Task` shortcut:** Tasks always attach to Goals, never directly to a Dream without an intervening Goal.
- **Transitive lineage:** Subgoals automatically inherit `effective_dream_id` from their ancestor root Goal, and subtasks automatically inherit `effective_goal_ids` and `effective_dream_id` from their ancestor Tasks and Goals.

```python
import taskatlas as ta

atlas = ta.Atlas("Structure Demo")
dream = atlas.add_dream("Autonomous Cloud", status="active")
platform = dream.add_goal("Core Platform", status="active")
auth_goal = platform.add_goal("Identity Service", status="active")

parent_task = auth_goal.add_task("Build token service", stage="active")
leaf_task = parent_task.add_task("EdDSA key rotation", stage="ready")

print(leaf_task.effective_goal_ids)  # (auth_goal.id, platform.id)
print(leaf_task.effective_dream_id)  # dream.id
```

---

## 2. Typed Links: Three Canonical Kinds

`taskatlas` keeps the link vocabulary intentionally tight so every link kind has crisp meaning:

| Kind | Allowed Endpoints | Semantics |
|---|---|---|
| `depends_on` | `Goal` and `Task` only | Causal prerequisite (`source` is topologically blocked until `target` reaches `done` / `achieved`). Enforced acyclic (DAG). |
| `relates_to` | `Dream`, `Goal`, `Task` | Non-blocking contextual association surfaced in `context()`. |
| `derived_from` | `Dream`, `Goal`, `Task` | Lineage pointer to an earlier task, goal, or dream that spawned this item. |

*(Why can't a `Task` or `Goal` `depends_on` a `Dream`? Because Dreams are open-world visions without a closed checklist; depending causally on a Dream would create a permanent topological deadlock.)*

### Canonical Direction & `.blocks()` Convenience

Whether you think in terms of *"A depends on B"* or *"B blocks A"*, `taskatlas` stores a single canonical `depends_on` edge:

```python
db = platform.add_task("Provision database", stage="active")
api = platform.add_task("Deploy API", stage="ready")

# Both calls write and deduplicate the exact same canonical Link (api --depends_on--> db):
lk1 = api.link(db, kind="depends_on")
lk2 = db.blocks(api)
assert lk1 is lk2
```

---

## 3. Live Blockage vs. Historical Dependencies

Completing a prerequisite never forces you to delete your dependency graph:

```python
print(api.is_blocked)    # True
print(api.blockers())    # [Task(id='t-...', title='Provision database')]

db.complete("Database live in us-east-1")

print(api.is_blocked)    # False (automatically unblocked!)
print(api.blockers())    # [] (no remaining unsatisfied blockers)
print(api.dependencies())  # [Task(id='t-...', title='Provision database')] (history intact!)
```
