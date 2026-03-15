# Critical Review: TaskAtlas Library

A detailed analysis of design weaknesses, API inconsistencies, missing capabilities, and ambiguities in the `taskatlas` library. This document is diagnostic, not prescriptive — it aims to surface problems clearly so that subsequent work can address them with full context.

---

## 1. Event System Integrity

### 1.1 Missing `task_created` events from `goal.add_task()`

The most architecturally significant bug in the library. When a task is created through `goal.add_task({...})` — the **recommended** and most common creation pattern — no `task_created` event is emitted. The atlas event log records only `task_attached_to_goal` on the goal. The task itself has zero events in its local history.

By contrast, `atlas.add_task({...})` correctly emits `task_created`. The same gap exists for `task.add_task({...})`, which emits `subtask_added` but no `task_created`.

This means that for any atlas built by following the documented best practices (create tasks through goals), the event log is structurally incomplete. There is no record that most tasks were ever created. This undermines the library's core promise of automatic, comprehensive history.

### 1.2 Missing `goal_created` events from `goal.add_goal()`

The same pattern applies to subgoals. `goal.add_goal({...})` emits `subgoal_added` but no `goal_created` event. Only `atlas.add_goal()` emits `goal_created`. A hierarchical project built through the natural containment API will have creation events only for top-level goals.

### 1.3 Dual event storage creates confusion

Events are stored in two places: the entity's `_events` list and the atlas's `_events` list. The `_emit()` method on `_WorkItem` appends to both — but only if `_atlas` is set at emission time. Events generated before atlas registration (which shouldn't normally happen given the documented workflows, but can happen) live only on the entity. Events generated via `Atlas.add_goal()` / `Atlas.add_task()` use `Atlas._record_event()` directly and never touch the entity's `_events` list.

The result: `task.history()` and `atlas.get_events(entity_id=task.id)` can return different results for the same entity. The `goal_created` event appears only in the atlas log; the entity's own history has no record of its own creation. This is counterintuitive.

---

## 2. Unguarded Direct Mutation

### 2.1 All tracked fields are freely writable

The library depends on mutation methods (`move()`, `set_status()`, `set_priority()`) to generate history and validate state. But every tracked attribute — `stage`, `status`, `priority`, `tags`, `title`, `summary` — is a plain Python attribute with no property guards.

```python
task.stage = "done"       # works silently — no validation, no event
task.priority = "garbage"  # works silently — invalid value accepted
goal.status = "achieved"  # works silently — no event
```

The AGENT_GUIDE explicitly warns against this ("Do NOT mutate tracked fields directly"), and the CONCEPT.md says it should be "discouraged or internally guarded." But neither the code nor the runtime enforces it. Any consumer who writes natural Python attribute assignment will corrupt the event log without any signal that something went wrong.

### 2.2 Tags have no mutation API at all

There is no `add_tag()`, `remove_tag()`, or `set_tags()` method. The only way to modify tags is direct list mutation (`task.tags.append("x")` or `task.tags.remove("x")`), which generates no events. Tags are used throughout filtering and views, yet changes to them are invisible to the history system.

### 2.3 Title and summary changes are untracked

There is no method for changing a task's title or summary. If a task's title changes — a meaningful mutation that agents and humans would want in the audit trail — the only option is `task.title = "new title"`, which is silent.

---

## 3. Link Model Weaknesses

### 3.1 Duplicate links are not prevented

Creating the same link twice produces two separate Link objects:

```python
task_a.link(task_b, kind="depends_on")
task_a.link(task_b, kind="depends_on")
# atlas now has 2 link objects, both source=A target=B kind=depends_on
```

There is no deduplication. The `_link_ids` lists grow unbounded with repeated link calls. This is easy to hit in agent workflows where retry logic or imprecise state checking leads to duplicate link creation.

### 3.2 Links are purely informational — no enforcement

A `depends_on` link from task A to task B does not prevent A from moving to "active" while B is still in "inbox." A `blocks` link from C to D does not prevent D from progressing. The library records the relationship but provides zero enforcement machinery.

The AGENT_GUIDE tells agents to check links manually before acting, but the library offers no helper for this. There is no `task.is_blocked()`, no `task.dependencies_met()`, no `task.get_blockers()` convenience method. Consumers must manually traverse `get_links()`, parse link directions, and look up target states themselves.

### 3.3 Bidirectional link query is awkward

Links are stored centrally in `atlas._links` and referenced by ID from both source and target entities. `entity.get_links()` returns all links involving the entity, but there is no way to filter by direction. To find "what blocks me" vs. "what I block," consumers must inspect `source_id` and `target_id` manually on each Link object. A richer query interface — `get_links(direction="incoming", kind="blocks")` — does not exist.

### 3.4 No cycle detection

The library does not detect circular dependencies. A → depends_on → B → depends_on → A is silently accepted. For agent workflows that traverse dependency chains, this can cause infinite loops unless the consumer implements their own cycle detection.

### 3.5 Link removal cleanup is fragile

The `unlink()` method manipulates `_link_ids` lists on both sides and deletes from `atlas._links`. If anything goes wrong mid-operation (or if the link state becomes inconsistent through other means), orphaned link IDs can persist in entity `_link_ids` lists, pointing to deleted Link objects. The `get_links()` method silently skips these, hiding the corruption.

---

## 4. Containment Model Gaps

### 4.1 No way to detach subtasks or subgoals from parents

You can `goal.detach_task(task)` to remove a task from a goal's attachment list. But there is no equivalent for subtask or subgoal containment. Once `parent.add_task(child)` is called, there is no `parent.detach_subtask(child)` or `parent.remove_task(child)`. The `parent_task_id` cannot be reset to `None` through any public API.

This means task hierarchy is strictly additive. If a subtask is placed under the wrong parent, the only recourse is to archive it and create a new one — losing its history, notes, and links.

### 4.2 Subtask + goal attachment overlap is unchecked

A subtask can simultaneously be a child of a parent task and be directly attached to a goal:

```python
parent = goal.add_task({"title": "Parent"})
child = parent.add_task({"title": "Child"})
goal.attach_task(child)  # child is now in both parent.child_task_ids AND goal.task_ids
```

This creates ambiguity in `goal.progress()` (which counts all `task_ids`, so the child is counted alongside the parent), in `tree()` (where the child would appear under the parent, but the parent's attachment to the goal also includes the child), and in `queue()` (which filters by `child_task_ids` to surface leaves, but the child is also a direct goal attachment).

The library neither prevents this overlap nor documents its consequences.

### 4.3 `goal.progress()` only counts direct attachments

`progress()` iterates `self.task_ids` — only tasks directly attached to the goal. It does not recurse into subtasks. If a goal has one task with ten subtasks, and all ten subtasks are done but the parent task is "active," `progress()` reports 0% done (or whatever the parent's stage is). This is technically correct per the implementation but likely misleading for any consumer who has decomposed work into subtasks.

### 4.4 No deletion API

There is no way to delete a task, goal, or link from an atlas. Archiving changes the status/stage but the objects remain in all registries. This is possibly intentional (append-only design), but it is never explicitly stated. For long-running atlases, this means unbounded memory growth with no eviction path.

---

## 5. Filtering and Query Limitations

### 5.1 No multi-value stage/status filtering

You cannot query for tasks in multiple stages at once:

```python
atlas.get_tasks(stage=["active", "blocked"])  # does not work
```

The filter treats the value as a direct equality check. To get tasks in two stages, you must make two separate calls and merge results. This is awkward for common queries like "show me everything that's in flight."

### 5.2 No negation filters

There is no way to express "not X":

```python
atlas.get_tasks(stage_not="done")  # does not exist
atlas.get_tasks(priority_not="low")  # does not exist
```

The `archived` filter's default-exclusion behavior is a special case, not a general pattern.

### 5.3 Sort direction is not configurable

`order_by="priority"` always sorts urgent-first (descending). `order_by="created_at"` always sorts newest-first (descending). `order_by="title"` always sorts A-Z (ascending). There is no way to reverse any of these. A consumer who wants oldest-first or lowest-priority-first must post-process the results.

### 5.4 No limit/offset on filtered queries

`get_tasks()` and `get_goals()` return all matching results. There is no `limit` or `offset` parameter. For large atlases, this means every query materializes the full result set.

### 5.5 `linked_to` filter exists but is undocumented

The `_filtering.py` module implements a `linked_to` filter that checks whether an item has any link (in any direction, of any kind) to a given entity ID. This filter works but is not documented in the README, AGENT_GUIDE, or any tutorial. It's a hidden capability.

### 5.6 Unknown filter keys are silently ignored

If you pass a misspelled or nonexistent filter key, the `_matches` function falls through to `getattr(item, key, UNSET)`, which returns `UNSET` for unknown attributes, causing the match to fail. The effect is that a typo in a filter key silently returns an empty list with no error:

```python
atlas.get_tasks(staeg="active")  # returns [] with no warning
```

---

## 6. Serialization and Persistence Concerns

### 6.1 No built-in file I/O

Every code example in the documentation repeats the same `json.dump(atlas.to_dict(), f, indent=2)` / `json.load(f)` boilerplate. There is no `atlas.save("path.json")` or `Atlas.load("path.json")` convenience method. For a library that emphasizes persistence as a core workflow, this is surprising friction.

### 6.2 No schema versioning

Serialized atlas dicts contain no version field. If the library evolves and field names change or new required fields are added, there is no mechanism for detecting stale data, migrating schemas, or providing helpful error messages during deserialization.

### 6.3 `from_dict()` with malformed data fails opaquely

There is no validation during deserialization. Missing required fields, wrong types, or corrupted data will produce confusing `KeyError` or `TypeError` exceptions from deep in the constructor chain rather than clear "invalid atlas data" messages.

### 6.4 Events are duplicated between entity and atlas serialization

When serializing, every event appears in two places: inside the entity's `events` array (via `_base_to_dict()`) and in the atlas-level `events` array (via `Atlas.to_dict()`). On deserialization, both are restored, meaning the same event object exists in two separate lists. This is correct for the dual-storage architecture, but it doubles the storage cost of events and the resulting JSON can be surprisingly large for active atlases.

### 6.5 Version mismatch between `__init__.py` and `pyproject.toml`

`__init__.py` declares `__version__ = "0.1.0"` while `pyproject.toml` declares `version = "0.0.1"`. A minor issue, but symptomatic of a gap in release hygiene.

---

## 7. View and Context Gaps

### 7.1 `context(mode=...)` has no validation

The `mode` parameter accepts any string. `task.context(mode="detailed")` or `task.context(mode="everything")` silently returns the compact view (since only `"full"` triggers the extended branch). There is no `ValueError` for invalid modes, and no documentation of what values are accepted.

### 7.2 `context()` compact mode inconsistently omits fields

In compact mode, Task context conditionally includes `parent_task_id`, `subtask_count`, `goal_ids`, and `latest_note` — but only if they are non-empty/truthy. Goal context similarly omits `task_count`, `subgoal_count`, and `latest_note` when empty. This means the return dict's keys vary from call to call, forcing consumers to use `.get()` for every field. This is awkward for typed consumers and makes the return type effectively unpredictable.

### 7.3 Board view does not include stage in task summaries

`_task_summary()` returns `{id, title, priority, tags}` — no `stage` field. Since the board groups by stage, this is technically redundant (the stage is the bucket key). But it makes it impossible to process board output items uniformly without their enclosing context.

### 7.4 Tree view does not include archived subgoals/subtasks

The tree view excludes archived top-level goals and unattached tasks but does not filter archived items at deeper levels. An archived subtask beneath an active task will still appear in the tree. This is inconsistent.

### 7.5 Queue has no limit parameter

`atlas.queue()` returns all actionable tasks. For large atlases, there is no way to ask for "the top 5 things to work on next" without materializing the full sorted list and slicing it.

### 7.6 No view for links or dependency graphs

There is no view that shows link topology. The board shows workflow state, the tree shows containment, the queue shows priority, and the summary shows aggregate counts — but nothing shows the dependency/blocker graph. For a library that emphasizes typed relationships as a core feature, the absence of a link-oriented view is a notable gap.

---

## 8. API Consistency and Ergonomic Issues

### 8.1 Asymmetric return types from mutation methods

`move()`, `set_status()`, `set_priority()` return `None`. `note()` returns the note dict. `link()` returns the Link object. `add_task()` returns the Task. `attach_task()` and `detach_task()` return `None`. `unlink()` returns an int (count removed). There is no consistent pattern for what mutation methods return.

### 8.2 Asymmetric add vs. attach semantics

`goal.add_task(dict)` creates a new task and attaches it. `goal.add_task(Task)` attaches an existing task (same as `attach_task`). `goal.attach_task(Task)` also attaches an existing task. The behavioral overlap between `add_task(instance)` and `attach_task(instance)` is confusing — they do the same thing but through different methods, and `add_task` has the additional capability of accepting dicts.

However, there is a subtle difference: `add_task()` emits a `task_attached_to_goal` event, and so does `attach_task()`. But `add_task()` returns the Task while `attach_task()` returns None. The naming suggests `add` creates and `attach` links existing, but `add` also links existing.

### 8.3 `goal.get_tasks()` takes no filter parameters

While `atlas.get_tasks(goal_id=goal.id)` supports the full filter vocabulary, `goal.get_tasks()` accepts no arguments and returns an unfiltered list. There is no `goal.get_tasks(stage="active")`. Consumers must either use the atlas-level filter or post-process the list.

### 8.4 No fluent/chainable API

Every mutation returns a different type (or None), precluding method chaining:

```python
# Not possible:
task.move("active", reason="Starting").note("Beginning work").set_priority("high", reason="Escalated")
```

Whether this matters is a design preference, but it constrains expressive patterns.

### 8.5 The dict-payload constructor pattern is unusual for Python

Python libraries conventionally use keyword arguments for construction: `Task(title="X", stage="active")`. The dict-payload-first pattern (`Task({"title": "X", "stage": "active"})`) is optimized for serialization round-trips and agent use, but it feels foreign to Python developers and is not enforced — both patterns work, and the documentation gives contradictory guidance about which to prefer.

---

## 9. Robustness and Safety Gaps

### 9.1 No cycle detection in containment hierarchies

While self-referential containment is caught (`task.add_task(task)` raises `ValueError`), longer cycles are not:

```python
a = atlas.add_task({"title": "A"})
b = a.add_task({"title": "B"})
# b.parent_task_id = a.id, a.child_task_ids = [b.id]
# Now if somehow a.parent_task_id gets set to b.id, we have a cycle.
```

The `add_task` method checks for self-reference and existing parent, but it does not walk the ancestor chain to detect longer cycles. In practice, the existing-parent check prevents most cycles (since a task can only have one parent), but the architecture does not rule them out if state is manipulated at the serialization layer.

### 9.2 ID collision risk with 8-hex-character IDs

IDs use 8 hex characters from `uuid4`, giving ~4 billion possible values per prefix. For typical use (hundreds of tasks) this is fine, but the library does not handle the collision case gracefully. If `make_id` generates a collision (astronomically unlikely but theoretically possible), the atlas's duplicate detection only catches it if you try to add both objects to the same atlas.

### 9.3 No validation that `reason` is meaningful

The AGENT_GUIDE mandates that `reason` must always be provided, but the parameter is typed as `str | None` with a default of `None`. The library silently accepts `task.move("active")` with no reason. A strict library would at minimum warn when `reason` is omitted for tracked mutations.

### 9.4 `detach_task` silently succeeds for non-attached tasks

Calling `goal.detach_task(task)` when the task is not actually attached to the goal still emits a `task_detached_from_goal` event. The method doesn't check whether the task was actually attached before emitting the event, producing misleading history.

---

## 10. Documentation and Conceptual Concerns

### 10.1 The AGENT_GUIDE and tutorials give different guidance on kwargs

The AGENT_GUIDE says "You MUST prefer dict payloads over keyword arguments." Tutorial 01 says "Both forms work throughout the library" and demonstrates both. This is a direct contradiction that will confuse consumers about the canonical pattern.

### 10.2 Tutorial code contains factual errors

Tutorial 05's board output shows a task appearing in two stages simultaneously (the "Authentication" task appears under both ACTIVE and REVIEW). Tutorial 04 claims "two events already exist" after a single `add_goal` call. These errors undermine trust in the documentation as a reference.

### 10.3 No guidance on atlas lifecycle management

The documentation covers creation and restoration of atlases but not lifecycle management: When should you create a new atlas vs. extend an existing one? How should long-running atlases handle growth? When is archiving insufficient and actual deletion needed? What are the memory implications of thousands of events?

### 10.4 The `meta` field's purpose is underspecified

Every entity (Atlas, Goal, Task, Note, Link) has a `meta` dict. The documentation describes it as "structured metadata" or "machine-readable data" but provides almost no guidance on what should go in `meta` vs. what should be a tag, a note, or a separate task field. There are no conventions for meta key naming, no typed helpers for common patterns, and no guidance on when meta is the right tool vs. when the schema should be extended.

### 10.5 No documentation on concurrency or thread safety

The library uses plain Python dicts and lists with no locking. In agent workflows where multiple agents might share an atlas (even sequentially through file serialization), there is no guidance on conflict resolution, merge strategies, or concurrent modification safety.

---

## 11. Structural and Architectural Observations

### 11.1 The `_atlas` back-reference creates tight coupling

Every `_WorkItem` holds a reference to its owning `Atlas`. This means entities cannot meaningfully exist outside an atlas context — `get_links()`, `get_tasks()`, `get_goals()`, `unlink()`, and `attach_task(by_id)` all return empty results or raise errors when `_atlas` is `None`. Yet the library allows creating entities without an atlas and provides no signal that they are in a degraded state.

### 11.2 Registration has inconsistent event semantics

`atlas.add_goal(goal)` both registers and emits `goal_created`. `atlas._register_goal(goal)` only registers (no event). `goal.add_task(task)` calls `_register_task` (no creation event) and then emits `task_attached_to_goal` on the goal. The distinction between "public add" and "internal register" is meaningful but the event gap it creates (section 1.1) is a real defect.

### 11.3 No abstract base class enforcement

`_WorkItem` sets `_entity_type = ""` and `_id_prefix = ""`, relying on subclasses to override. There is no `ABC`, no `abstractmethod`, and no runtime check. Instantiating `_WorkItem` directly would produce an entity with an empty type and a malformed ID.

### 11.4 Events are not truly immutable

`Event` uses `__slots__` but does not use `__setattr__` to prevent modification. Despite being documented as "immutable records," event attributes can be freely modified after creation:

```python
event.reason = "rewritten history"  # works silently
event.data["key"] = "injected"      # works silently
```

---

## 12. Summary of Priority Concerns

Ranked by impact on the library's reliability and usability:

1. **Missing creation events** from `goal.add_task()` and `task.add_task()` — undermines the core history promise
2. **Unguarded direct attribute mutation** — makes it easy to corrupt state without any signal
3. **Duplicate links accepted silently** — a data integrity hazard in real workflows
4. **No subtask/subgoal detachment API** — makes hierarchy corrections impossible without destructive workarounds
5. **No tag mutation API** — a tracked field with no tracked mutation path
6. **Context mode and filter parameters silently accept invalid values** — debugging becomes guesswork
7. **Inconsistent event storage** across entity and atlas — makes history queries unreliable
8. **No link enforcement or convenience queries** — typed relationships exist but have no teeth
9. **Serialization lacks versioning and validation** — fragile persistence layer
10. **Documentation contradictions and errors** — undermines adoption confidence

---

*This review reflects the state of the library at version 0.1.0 / 0.0.1. It is intended as a foundation for prioritized improvement work.*
