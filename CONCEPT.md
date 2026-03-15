

# PRD: `taskatlas`

## A lean Python library for representing goals, tasks, relationships, priority, evolution, and history

---

## 1. Overview

`taskatlas` is a Python library for modeling a living body of work in a way that is lightweight, coherent, and easy to transact with programmatically.

It is **not** meant to be a clone of Jira, Linear, or Trello.

Instead, it should provide a clean object model for:

* representing **goals** as higher-order intended outcomes
* representing **tasks** as actionable work units
* organizing tasks through simple **stages**
* linking tasks and goals through typed **relationships**
* preserving **history** as work evolves over time
* retrieving compact, relevant **context** quickly
* rendering the current state into useful, lightweight views

The core design intent is:

> simple enough to feel elemental, but rich enough to support real task evolution, hierarchy, and graph-like relationships.

The library should feel Pythonic, inspectable, and pleasant to use in scripts, notebooks, agents, services, and small applications.

---

## 2. Product vision

The goal of `taskatlas` is to become a foundational task-representation layer for intelligent systems and serious Python applications.

It should give developers a way to represent work as a navigable atlas:

* a place where goals define direction
* tasks define executable work
* relationships define structure
* history defines narrative continuity
* retrieval methods expose the right context quickly

The library should support use cases such as:

* simple project/task planning
* structured work tracking in scripts or apps
* agent-readable task context
* hierarchical decomposition of work
* dependency and blocker tracking
* historical inspection of changes over time
* export/import of task state for persistence

The library should remain deliberately narrower than a workflow engine and deliberately more expressive than a plain list of tasks.

---

## 3. Problem statement

Most task systems fall into one of two bad extremes:

### Too shallow

Simple task lists or Kanban tools are easy to use, but they often fail to represent:

* meaningful relationships between tasks
* higher-order outcomes
* historical evolution
* local context and neighborhood
* hierarchical decomposition beyond crude subtasks

### Too heavy

Enterprise issue trackers are powerful, but they impose:

* too many concepts
* too much field complexity
* too much process ceremony
* too much UI- and org-shaped thinking
* too much friction for programmatic use

`taskatlas` should occupy the missing middle:

> a lean but semantically rich Python-native work model.

---

## 4. Design goals

### Primary goals

#### 4.1 Provide a clean object model

The public API should revolve around a small set of objects that are intuitive and composable.

#### 4.2 Distinguish goals from tasks

A goal is not merely a large task. It represents intended outcome. A task represents actionable work.

#### 4.3 Support hierarchy and relationships

The library must support both:

* containment/hierarchy
* typed cross-links

These are different concepts and must remain different in the model.

#### 4.4 Preserve change history

All meaningful mutations should create durable historical events.

#### 4.5 Make retrieval easy

Users should be able to quickly ask for:

* a goal
* a task
* all tasks matching some conditions
* recent changes
* local context around an object
* board/tree/queue views

#### 4.6 Keep the API small

The API must remain compact and memorable.

#### 4.7 Make rendering easy

The library should expose structured view outputs that can be easily turned into text, JSON, markdown, UI cards, or agent context.

---

## 5. Non-goals

The first version of `taskatlas` should **not** attempt to become:

* a workflow orchestration engine
* a ticketing platform clone
* a database ORM
* a collaboration server
* a permissions/identity system
* a notification system
* a sprint/planning tool
* a story point / velocity tool
* a calendar or Gantt system
* a chat or document system

Those things may be integrated later, but they are not the center of this library.

---

## 6. Design principles

### 6.1 Truthful naming

Names must reflect actual semantics.

* `Goal` means desired outcome
* `Task` means actionable work
* `Atlas` means the containing world of goals and tasks

### 6.2 Small number of public nouns

The public object model should remain compact.

Recommended public nouns:

* `Atlas`
* `Goal`
* `Task`

Secondary objects such as `Link` and `Event` may exist, but the user should not be forced to think about them constantly.

### 6.3 Distinguish containment from relation

These must never be blurred.

Containment means:

* subgoal of a goal
* subtask of a task
* task attached to a goal

Relation means:

* blocks
* depends_on
* supports
* relates_to

### 6.4 History should be automatic

A user should not have to manually create history records. Mutations should create them.

### 6.5 Retrieval should return context, not just rows

This library should not feel like querying a table. It should feel like retrieving situationally relevant objects.

### 6.6 The board is a view, not the ontology

Tasks may move through stages, but the underlying reality is richer than a set of columns.

### 6.7 Pythonic ergonomics

The API should use simple signatures, readable method names, and low ceremony.

---

## 7. Core domain model

---

### 7.1 `Atlas`

The root container.

The atlas is the authoritative in-memory representation of a body of work.

It owns:

* goals
* tasks
* indexes
* links
* events
* stage definitions
* query helpers
* render helpers
* serialization/export behavior

Conceptually:

> `Atlas` is the navigable world in which goals and tasks live.

---

### 7.2 `Goal`

A goal is a higher-order intended outcome.

A goal may have:

* title
* summary
* status
* priority
* tags
* notes
* tasks attached to it
* subgoals
* links to other goals/tasks
* historical events
* derived progress indicators

A goal answers:

* what are we trying to achieve?
* what work belongs to this outcome?
* what changed around this goal?
* how much progress exists under it?

---

### 7.3 `Task`

A task is an actionable work unit.

A task may have:

* title
* summary
* stage
* priority
* tags
* notes
* goal attachments
* parent task
* child tasks
* links to other tasks/goals
* historical events
* derived context

A task answers:

* what should be done?
* where is this work in its current flow?
* what blocks it?
* what depends on it?
* what subwork exists beneath it?
* what changed recently?

---

### 7.4 `Link` (recommended internal or semi-public object)

A typed relationship between two entities.

Source and target may be:

* goal -> goal
* goal -> task
* task -> task
* task -> goal

Recommended link types for v0:

* `depends_on`
* `blocks`
* `relates_to`
* `supports`
* `duplicates`
* `derived_from`
* `conflicts_with`

Important: `part_of` should generally **not** be used for parent/child containment. Containment should be represented structurally, not merely as a link.

---

### 7.5 `Event` (recommended internal or read-only public object)

A historical record of change.

Examples:

* goal created
* task created
* task moved stage
* goal status changed
* priority changed
* note added
* task attached to goal
* subtask added
* link added
* link removed
* object archived

The event model should make historical inspection natural and cheap.

---

## 8. Recommended public API philosophy

The main interaction pattern should be object-based.

The user should be able to instantiate objects directly and add them to the atlas, as in your example:

```python
import taskatlas as ta

atlas = ta.Atlas()

goal1 = ta.Goal({
    "title": "Design task ontology",
    "summary": "Define the core object model for goals and tasks.",
    "priority": "high",
})

atlas.add_goal(goal1)
```

This pattern is good because it is explicit and legible.

At the same time, convenience forms may also be supported:

```python
goal2 = atlas.add_goal({
    "title": "Define relation model",
    "priority": "high",
})
```

But the canonical PRD direction should prioritize the explicit object pattern first.

---

## 9. Canonical public classes

The required public classes for v0 should be:

```python
Atlas
Goal
Task
```

Optional but recommended secondary classes:

```python
Link
Event
```

The engineer may implement `Link` and `Event` internally first, then decide whether to expose them publicly.

---

## 10. Object construction pattern

The preferred constructor pattern should support a dict-like payload style:

```python
goal = ta.Goal({
    "title": "Ship v0 API",
    "summary": "Define and stabilize the public surface.",
    "priority": "high",
    "tags": ["core", "api"],
})
```

And:

```python
task = ta.Task({
    "title": "Draft PRD",
    "stage": "active",
    "priority": "high",
})
```

Reasons to support this style:

* easy to serialize
* easy to construct from other systems
* easy to create from JSON-like payloads
* easy for agents and programmatic systems to use

The engineer may also support kwargs later, but dict-style payloads should be first-class.

---

## 11. Identity model

Every `Goal` and `Task` must have a stable unique ID.

### Requirements

* IDs must be assigned on creation if not explicitly provided
* IDs must remain stable across serialization and reload
* `atlas.get_goal(goal_id)` must retrieve the goal by ID
* `atlas.get_task(task_id)` must retrieve the task by ID
* equality should be id-based and type-aware

That means this should be true:

```python
goal1 = ta.Goal({"title": "Do some task"})
atlas.add_goal(goal1)

goal2 = atlas.get_goal(goal1.id)

goal1 == goal2
```

Recommended semantic rule:

* `Goal` equality compares `id`
* `Task` equality compares `id`
* a `Goal` is never equal to a `Task`, even if IDs somehow collide

In a single atlas session, `get_*()` should preferably return the same in-memory object instance when possible.

---

## 12. Atlas responsibilities

The `Atlas` class is the primary operating surface.

It must support:

### 12.1 Object registration

* add goals
* add tasks
* remove/archive goals/tasks
* retrieve by ID

### 12.2 Querying

* retrieve all goals/tasks
* filter by common fields
* sort
* retrieve recent changes

### 12.3 Relationship management

* maintain indexes for attachments, hierarchy, and links

### 12.4 Rendering

* board-style view
* tree-style view
* queue view
* compact summaries
* recent activity

### 12.5 Serialization

* export to dict
* load from dict
* preserve IDs and history

---

## 13. Goal responsibilities

A `Goal` must support:

* metadata
* status changes
* priority changes
* note accumulation
* attachment of tasks
* containment of subgoals
* links to other objects
* history retrieval
* progress summary
* contextual summary

Goals should not move through task stages. They should have their own goal-oriented lifecycle.

Recommended default goal statuses:

```python
["proposed", "active", "paused", "achieved", "archived"]
```

---

## 14. Task responsibilities

A `Task` must support:

* metadata
* movement through stages
* priority changes
* note accumulation
* parent-child subtask structure
* links to goals/tasks
* history retrieval
* contextual summary

Recommended default task stages:

```python
["inbox", "ready", "active", "blocked", "review", "done", "archived"]
```

---

## 15. Required public methods

---

### 15.1 Atlas methods

The engineer should implement the following public methods in v0.

#### Creation / registration

```python
atlas.add_goal(goal_or_payload)
atlas.add_task(task_or_payload)
```

#### Retrieval

```python
atlas.get_goal(goal_id)
atlas.get_task(task_id)
atlas.get_goals(...)
atlas.get_tasks(...)
```

#### Search / filtering

```python
atlas.find_goals(...)
atlas.find_tasks(...)
```

It is acceptable for `get_goals()` and `get_tasks()` to handle filtering directly and for `find_*()` to be omitted initially, but at least one clear filtered retrieval pattern must exist.

#### History / events

```python
atlas.get_events(...)
atlas.recent(...)
```

#### Rendering

```python
atlas.board(...)
atlas.tree(...)
atlas.queue(...)
atlas.summary(...)
```

#### Serialization

```python
atlas.to_dict()
ta.Atlas.from_dict(payload)
```

---

### 15.2 Goal methods

```python
goal.add_task(task_or_payload)
goal.add_goal(goal_or_payload)
goal.attach_task(task_or_id)
goal.detach_task(task_or_id)

goal.get_tasks(...)
goal.get_goals(...)

goal.set_status(status, reason=None)
goal.set_priority(priority, reason=None)

goal.note(text, meta=None)
goal.link(target, kind, meta=None)
goal.unlink(target=None, kind=None)

goal.context(...)
goal.history(...)
goal.progress(...)
goal.to_dict()
```

---

### 15.3 Task methods

```python
task.add_task(task_or_payload)
task.get_tasks(...)

task.move(stage, reason=None)
task.set_priority(priority, reason=None)

task.note(text, meta=None)
task.link(target, kind, meta=None)
task.unlink(target=None, kind=None)

task.context(...)
task.history(...)
task.to_dict()
```

---

## 16. Filtering requirements

The retrieval API should be easy to read and not require a query language.

### Example patterns

```python
atlas.get_goals()
atlas.get_goals(status="active")
atlas.get_goals(priority="high")
atlas.get_goals(tags=["core"])
atlas.get_goals(title_contains="design")
```

```python
atlas.get_tasks()
atlas.get_tasks(stage="blocked")
atlas.get_tasks(priority="urgent")
atlas.get_tasks(goal_id=goal1.id)
atlas.get_tasks(parent_id=task1.id)
atlas.get_tasks(tags=["api", "core"])
atlas.get_tasks(title_contains="schema")
```

### Recommended common filters

For goals:

* `id`
* `status`
* `priority`
* `tags`
* `title_contains`
* `has_tasks`
* `linked_to`
* `archived`

For tasks:

* `id`
* `stage`
* `priority`
* `tags`
* `goal_id`
* `parent_id`
* `title_contains`
* `blocked`
* `linked_to`
* `archived`

### Sorting

Support optional sorting such as:

```python
atlas.get_tasks(order_by="priority")
atlas.get_tasks(order_by="updated_at")
atlas.get_goals(order_by="created_at")
```

---

## 17. Relationship semantics

This section matters a lot and should be implemented with discipline.

### 17.1 Goal -> Task attachment

A task may be attached to one or more goals.

This is not the same as parent-child containment.

Example:

```python
goal1.attach_task(task1)
```

or:

```python
goal1.add_task(task1)
```

The recommended rule is:

* `goal.add_task(payload_or_task)` may create or attach
* `goal.attach_task(task_or_id)` explicitly attaches an existing task

### 17.2 Goal -> Goal containment

Subgoals are allowed.

Example:

```python
subgoal = ta.Goal({"title": "Define API naming"})
goal1.add_goal(subgoal)
```

### 17.3 Task -> Task containment

Subtasks are allowed and recursive.

Example:

```python
task1.add_task(task2)
```

### 17.4 Typed links

Cross-cutting relationships are modeled by links.

Examples:

```python
task1.link(task2, kind="depends_on")
task2.link(task3, kind="blocks")
goal1.link(goal2, kind="supports")
goal1.link(task4, kind="relates_to")
```

### 17.5 Containment must not be faked with links

Do not represent subtask structure only as links.

Containment should have dedicated structural fields/indexes.

---

## 18. Notes model

Goals and tasks should both allow note accumulation.

### Requirements

* notes are append-only by default
* each note should record timestamp
* each note may optionally include metadata
* notes should appear in context summaries and history

Example:

```python
task1.note("Need clearer naming for the root container.")
goal1.note("Goals should represent intended outcomes, not merely larger tasks.")
```

Recommended note representation internally:

```python
{
    "id": "...",
    "text": "...",
    "created_at": "...",
    "meta": {...}
}
```

---

## 19. History model

History is one of the most important parts of the design.

Every meaningful mutation should generate an event.

### Example event types

* `goal_created`
* `task_created`
* `goal_status_changed`
* `task_stage_changed`
* `priority_changed`
* `note_added`
* `task_attached_to_goal`
* `subgoal_added`
* `subtask_added`
* `link_added`
* `link_removed`
* `archived`

### Required behaviors

```python
task1.move("blocked", reason="Waiting on schema decision")
```

should automatically create a history event.

```python
goal1.set_status("active", reason="Scope is now approved")
```

should automatically create a history event.

### Retrieval

```python
task1.history()
goal1.history()
atlas.get_events()
atlas.recent(limit=20)
```

History retrieval should support filters such as:

* object ID
* event type
* date range
* limit

---

## 20. Context model

`context()` is a critical method and should be treated as a core differentiator.

The purpose of `context()` is to return a compact but meaningful situational summary.

### 20.1 Task context should include

* id
* title
* summary
* stage
* priority
* tags
* goal attachments
* parent task
* child tasks
* incoming/outgoing links
* blockers/dependencies
* recent notes
* recent events

Example:

```python
task1.context()
task1.context(mode="compact")
task1.context(mode="full")
```

### 20.2 Goal context should include

* id
* title
* summary
* status
* priority
* tags
* attached tasks
* subgoals
* progress snapshot
* blocked tasks under the goal
* recent notes
* recent events

Example:

```python
goal1.context()
goal1.context(mode="compact")
goal1.context(mode="full")
```

### Return format

For v0, `context()` should return structured Python data, not only formatted strings.

Recommended default: dict-like payload.

Formatted text versions can be added later.

---

## 21. Progress model

Goals should expose a lightweight progress summary.

Example:

```python
goal1.progress()
```

Recommended output should include:

* total attached tasks
* tasks by stage
* done count
* blocked count
* active count
* derived completion ratio

Important: this is a convenience summary, not a full reporting engine.

Tasks may also expose a lightweight progress view if they have subtasks.

---

## 22. Rendering requirements

The library should support fast, structured render views.

These are not UI widgets. They are programmatic representations optimized for inspection and downstream rendering.

### 22.1 Board view

Tasks grouped by stage.

```python
atlas.board()
atlas.board(goal_id=goal1.id)
```

Recommended output:

* stages as buckets
* tasks listed under each stage
* optionally filtered by goal/tags/priority

### 22.2 Tree view

Hierarchy of goals and/or tasks.

```python
atlas.tree()
goal1.context()
task1.context()
```

A full `atlas.tree()` may show:

* top-level goals
* their subgoals
* attached tasks
* task subtasks

### 22.3 Queue view

Priority-oriented task list.

```python
atlas.queue()
atlas.queue(goal_id=goal1.id)
```

Should prioritize:

* non-archived
* non-done
* high priority
* actionable tasks
* optionally de-emphasize parent/container tasks

### 22.4 Summary view

```python
atlas.summary()
```

Should include:

* total goals
* total tasks
* tasks by stage
* goals by status
* recent changes

---

## 23. Serialization requirements

Serialization is required in v0.

### Required methods

```python
atlas.to_dict()
ta.Atlas.from_dict(payload)

goal.to_dict()
task.to_dict()
```

### Requirements

* preserve IDs
* preserve notes
* preserve links
* preserve history/events
* preserve goal-task attachments
* preserve task hierarchy
* preserve goal hierarchy
* preserve timestamps

JSON-friendly payloads are strongly preferred.

---

## 24. Archive behavior

Both goals and tasks should support archival.

Archival means:

* object remains in atlas/history
* object is excluded from most default active queries
* object is still retrievable directly by ID
* object can be included when `archived=True`

Examples:

```python
task1.move("archived")
goal1.set_status("archived")
```

or explicit helpers later:

```python
task1.archive()
goal1.archive()
```

For v0, one approach is enough as long as semantics are clear.

---

## 25. Error handling requirements

The library should fail clearly and predictably.

### Examples of invalid operations

* adding two different objects with same ID
* moving a task to an invalid stage
* setting a goal to an invalid status
* linking unsupported object types
* attaching a non-existent task ID
* making a task its own child
* making a goal its own subgoal
* creating cyclic parent-child containment if cycles are disallowed

### Recommended behavior

Raise clear Python exceptions with readable messages.

Example exception categories:

* `ValueError`
* `KeyError`
* `TypeError`

Custom exceptions can be added later, but are not required for v0.

---

## 26. Equality and mutability requirements

### Equality

`goal1 == goal2` should be true when they represent the same goal ID.

`task1 == task2` should be true when they represent the same task ID.

### Mutability

Objects should be mutable, but mutations should pass through methods when event history matters.

Good:

```python
task1.move("active")
task1.set_priority("high")
task1.note("This is blocked on naming.")
```

Less desirable for public use:

```python
task1.stage = "active"
task1.priority = "high"
```

The engineer should design the API so that meaningful state mutations go through methods that generate history.

Direct attribute mutation should either be discouraged or internally guarded.

---

## 27. Example interaction patterns

This section is especially important. The engineer should use these examples as guidance for how the library should feel in practice.

---

### 27.1 Create an atlas and add a goal

```python
import taskatlas as ta

atlas1 = ta.Atlas({
    "name": "API Design Atlas"
})

goal1 = ta.Goal({
    "title": "Design taskatlas v0 API",
    "summary": "Create a lean and expressive public interface.",
    "priority": "high",
    "status": "active",
    "tags": ["core", "api"]
})

atlas1.add_goal(goal1)
```

---

### 27.2 Retrieve the goal by ID

```python
goal2 = atlas1.get_goal(goal1.id)

goal1 == goal2
```

Expected outcome:

* returns the stored goal object
* equality is true
* preferably the same in-memory object instance in the current process

---

### 27.3 Add tasks to a goal

```python
task1 = ta.Task({
    "title": "Define Atlas class responsibilities",
    "summary": "Clarify what belongs on the root object.",
    "stage": "active",
    "priority": "high",
    "tags": ["atlas", "core"]
})

task2 = ta.Task({
    "title": "Define Goal class semantics",
    "stage": "ready",
    "priority": "high",
    "tags": ["goal", "core"]
})

goal1.add_task(task1)
goal1.add_task(task2)
```

Expected behavior:

* both tasks become registered in the atlas
* both tasks become attached to the goal
* creation/attachment events are recorded

---

### 27.4 Create subtasks under a task

```python
subtask1 = ta.Task({
    "title": "Clarify goal status lifecycle",
    "stage": "ready",
    "priority": "medium"
})

subtask2 = ta.Task({
    "title": "Clarify goal progress semantics",
    "stage": "ready",
    "priority": "medium"
})

task2.add_task(subtask1)
task2.add_task(subtask2)
```

Expected behavior:

* `task2` becomes parent of both subtasks
* both subtasks are registered in the atlas
* history records are added

---

### 27.5 Filter tasks

```python
atlas1.get_tasks()
atlas1.get_tasks(stage="ready")
atlas1.get_tasks(priority="high")
atlas1.get_tasks(goal_id=goal1.id)
atlas1.get_tasks(tags=["core"])
```

Expected behavior:

* each method returns a list of task objects
* filtering is conjunctive by default unless documented otherwise

---

### 27.6 Move a task

```python
task1.move("blocked", reason="Waiting on naming decision")
```

Expected behavior:

* stage becomes `blocked`
* `updated_at` changes
* history event is created
* reason is preserved in event metadata

---

### 27.7 Add notes

```python
task1.note("Need stronger distinction between goals and tasks.")
goal1.note("The API should stay much lighter than Jira or Linear.")
```

Expected behavior:

* notes are appended
* history events are created
* `context()` should later surface these notes

---

### 27.8 Link objects

```python
task1.link(task2, kind="relates_to")
task2.link(subtask1, kind="supports")
goal1.link(task1, kind="supports")
```

Expected behavior:

* typed links are created
* link metadata is stored
* history events are created
* links appear in context

---

### 27.9 Retrieve history

```python
task1.history()
goal1.history()
atlas1.recent(limit=10)
```

Expected behavior:

* returns ordered event lists
* newest first or oldest first must be documented consistently

---

### 27.10 Render a board

```python
atlas1.board()
atlas1.board(goal_id=goal1.id)
```

Expected output shape:

* structured Python object
* stage buckets containing task summaries

Not required to be pretty-printed text in v0.

---

### 27.11 Progress summary

```python
goal1.progress()
```

Expected output should resemble:

```python
{
    "goal_id": goal1.id,
    "task_count": 4,
    "by_stage": {
        "ready": 2,
        "active": 1,
        "blocked": 1,
        "done": 0
    },
    "done_ratio": 0.0
}
```

---

### 27.12 Serialize and reload

```python
payload = atlas1.to_dict()

atlas2 = ta.Atlas.from_dict(payload)

goal3 = atlas2.get_goal(goal1.id)
task3 = atlas2.get_task(task1.id)
```

Expected behavior:

* IDs preserved
* relationships preserved
* history preserved
* equality by ID still behaves correctly

---

## 28. Recommended minimal data fields

---

### 28.1 Goal fields

Required fields:

* `id`
* `title`
* `summary`
* `status`
* `priority`
* `tags`
* `notes`
* `created_at`
* `updated_at`
* `meta`

Structural fields:

* `parent_goal_id`
* `child_goal_ids`
* `task_ids`
* `link_ids`

---

### 28.2 Task fields

Required fields:

* `id`
* `title`
* `summary`
* `stage`
* `priority`
* `tags`
* `notes`
* `created_at`
* `updated_at`
* `meta`

Structural fields:

* `parent_task_id`
* `child_task_ids`
* `goal_ids`
* `link_ids`

---

### 28.3 Atlas fields

Required fields:

* `name`
* `goal_registry`
* `task_registry`
* `event_registry`
* `link_registry`
* `task_stages`
* `goal_statuses`
* `created_at`
* `updated_at`
* `meta`

---

## 29. v0 priorities

The engineer should prioritize the following in order.

### Highest priority

1. `Atlas`, `Goal`, and `Task` object model
2. ID generation and retrieval
3. goal/task registration
4. task stages and goal statuses
5. goal-task attachments
6. task-task hierarchy
7. note support
8. event/history generation
9. filtering and retrieval
10. serialization

### Second priority

11. typed links
12. board/tree/queue outputs
13. progress summaries
14. richer context outputs

### Later

15. markdown/text renderers
16. import/export helpers
17. advanced querying
18. custom stage/status schemas
19. stronger validation rules
20. custom event types

---

## 30. Success criteria

The library should be considered successful for v0 if a talented engineer can build it such that all of the following feel natural and coherent:

### A user can:

* create an atlas
* create goals and tasks
* add them into the atlas
* retrieve them by ID
* attach tasks to goals
* nest tasks under tasks
* nest goals under goals
* move tasks through stages
* change goal statuses
* add notes
* create typed links
* inspect history
* filter objects
* serialize and reload the atlas

### And the library:

* preserves identity correctly
* preserves history automatically
* keeps containment and links distinct
* remains lightweight and readable
* avoids enterprise-style complexity

---

## 31. Final product philosophy

The library should feel like this:

> a clean, living Python atlas of work.

Not just a board.
Not just a graph.
Not just a task list.

An atlas:

* of goals
* of tasks
* of relations
* of movement
* of evolving context
* of historical continuity

That is the core product idea the engineer should hold in mind while building the classes.

---

## 32. Concise implementation north star for the engineer

Build a Python library where:

* `Atlas` is the root container and registry
* `Goal` represents intended outcome
* `Task` represents actionable work
* tasks move through stages
* goals move through statuses
* goals can contain goals and attach tasks
* tasks can contain subtasks
* goals and tasks can link to one another
* meaningful mutations generate events
* retrieval is easy
* context is compact and useful
* serialization is first-class
* the API remains lean, coherent, and pleasant

That is the PRD target.










