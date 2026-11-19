# taskatlas

[![PyPI version](https://img.shields.io/pypi/v/taskatlas.svg)](https://pypi.org/project/taskatlas/)
[![Python versions](https://img.shields.io/pypi/pyversions/taskatlas.svg)](https://pypi.org/project/taskatlas/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/jrolf/taskatlas/actions/workflows/ci.yml/badge.svg)](https://github.com/jrolf/taskatlas/actions/workflows/ci.yml)

A lean, zero-dependency Python engine for long-horizon intentionality: **Dreams**, **Goals**, **Tasks**, causal readiness, and operational continuity.

---

## What is this?

`taskatlas` gives intelligent systems, scripts, and Python applications a durable object model for tracking work across time. It sits between a simple task list and an enterprise tracker - expressive enough to model multi-horizon structure, critical-path readiness, and deliverable receipts, yet lightweight enough to run anywhere with **zero external dependencies** (Python 3.10+ standard library only).

An **Atlas** is the navigable world and factory for three horizons of intentionality:

- **Dreams** *(optional)* - enduring open-world visions and north stars (`seed`, `active`, `dormant`, `realized`, `abandoned`), evaluated by milestone momentum and stall detection rather than a fake completion percentage.
- **Goals** - convergent, falsifiable outcomes (`proposed`, `active`, `paused`, `achieved`, `abandoned`) with verifiable acceptance `criteria` and `outcome` summaries.
- **Tasks** - executable work units (`inbox`, `ready`, `active`, `review`, `done`, `canceled`) with non-destructive external holds (`hold()`), multi-agent ownership (`claim()`), and structured completion receipts (`complete()`).
- **Causal & Contextual Links** - acyclic `depends_on` prerequisites (plus `.blocks()`), `relates_to`, and `derived_from`.
- **Single-Store History & Deltas** - immutable `Event` audit trails with `actor` provenance, cursor tailing (`events_since()`), snapshot `diff()`, and safe archival `compact()`.
- **Agent-Native Orientation & Tools** - critical-path `queue()`, hydrated neighborhood `context()`, token-tight Markdown `brief()`, and portable JSON-Schema tools (`tool_schemas()`, `dispatch()`, `as_tools()`).

---

## Install

```bash
pip install taskatlas
```

For development:

```bash
git clone https://github.com/jrolf/taskatlas.git
cd taskatlas
pip install -e ".[dev]"
```

---

## Quick Example

```python
import taskatlas as ta

atlas = ta.Atlas("Data Platform")

# Optional top-level Dream: an enduring open-horizon vision
dream = atlas.add_dream(
    "Self-Driving Analytics Stack",
    vision="Pipelines ingest, validate, and self-heal without manual intervention.",
    status="active",
    priority="high",
)

# Convergent Goal with falsifiable criteria (works with or without a Dream)
goal = dream.add_goal(
    "Ship reliable ingestion v1",
    status="active",
    priority="urgent",
    criteria=[
        "At-least-once delivery verified under broker restart",
        "p99 ingest latency < 50ms",
    ],
)

# Executable Tasks and causal dependencies
schema = goal.add_task("Publish wire schema", stage="ready", priority="medium")
parser = goal.add_task("Implement stream parser", stage="ready", priority="urgent")
parser.link(schema, kind="depends_on")  # equivalent to: schema.blocks(parser)

# Critical-path queue: 'schema' inherits URGENT priority because it unblocks 'parser'
print(atlas.queue()[0]["title"])               # "Publish wire schema"
print(atlas.queue()[0]["effective_priority"])  # "urgent"

# Complete prerequisite with a structured deliverable receipt
schema.complete(
    "Published Avro/JSON wire schema v1.",
    artifacts=["schemas/ingest_v1.json"],
    data={"fields": 18},
)

# Downstream task unblocks automatically and sees upstream artifacts in its context
ctx = parser.context(mode="full")
print(ctx["is_blocked"])  # False
print(ctx["satisfied_dependencies"][0]["result"]["artifacts"])
# ['schemas/ingest_v1.json']

# Render a token-tight Markdown briefing for a human or LLM prompt
print(atlas.brief())

# Atomic JSON persistence (temp-file + fsync + os.replace)
atlas.save("project.json")
restored = ta.Atlas.load("project.json")
```

---

## Core Architecture

### 1. Progressive Hierarchy (`Dream -> Goal -> Subgoal -> Task -> Subtask`)

`Atlas` is the sole factory; every entity is bound to its `Atlas` from birth:

```python
atlas = ta.Atlas("Roadmap")

# Simple Goal -> Task usage (Dreams are completely optional)
api = atlas.add_goal("Public API", status="active", priority="high")
auth = api.add_task("Build authentication", stage="active")
jwt = auth.add_task("Implement JWT verifier", stage="ready")
```

When you do use `Dream`, `atlas.tree()`, `atlas.summary()`, and `atlas.brief()` surface dream momentum and **stalled-dream warnings** (`no_active_goals`, `no_open_tasks`, or `all_tasks_blocked`) automatically. When an `Atlas` has no dreams, views stay completely free of dream noise.

Containment is **transitive** everywhere: `goal.progress()`, `atlas.board(goal_id=...)`, `atlas.queue(goal_id=...)`, and `atlas.get_tasks(dream_id=...)` walk subgoals and subtasks without double counting.

### 2. Orthogonal State Physics: Stage, Blockage, Resolution, and Archival

Workflow position, impediments, completion vs. abandonment, and visibility shelving are never conflated into a single flat string:

- **Lifecycle:** Tasks end as `done` (`task.complete(...)`) or `canceled` (`task.cancel(...)`). Canceled tasks are excluded from active `goal.progress()` denominators so dropping obsolete scope never locks completion below `100%`.
- **Live Blockage + External Holds:** `task.is_blocked` is `True` when a prerequisite `depends_on` target is unfinished *or* when an external hold is set via `task.hold("Waiting on IAM role")`. Calling `task.unhold()` restores readiness without losing whether the task was in `ready`, `active`, or `review`.
- **Archival Shelving:** `entity.archive()` shelves items out of default active views while preserving their terminal `done`/`achieved` or `canceled`/`abandoned` status.

### 3. Provenance, Claims, Cursors, and Diffs

```python
checkpoint = atlas.cursor

with atlas.as_actor("agent:worker-1"):
    jwt.claim(move_active=True)
    jwt.note("Selected EdDSA keys.")
    jwt.complete("Verifier passing 28 unit tests.", artifacts=["src/jwt.py"])

# Tail events chronologically since a cursor or timestamp
for ev in atlas.events_since(checkpoint):
    print(ev.actor, ev.event_type, ev.reason)

# Or diff two Atlas snapshots across sub-agent runs or CHRON ticks
copy_atlas = atlas.copy()
copy_atlas.add_task("Follow-up audit", stage="ready")
delta = atlas.diff(copy_atlas)
```

### 4. Zero-Dependency Agent Tool Seam

Plug an `Atlas` straight into `ThoughtFlow` or any function-calling LLM loop:

```python
schemas = atlas.tool_schemas()  # 9 portable JSON-Schema tool definitions
receipt = atlas.dispatch("atlas_orient", {"format": "brief"}, actor="agent:planner")

# Or bind directly as ThoughtFlow TOOLs:
# tools = [TOOL(**spec) for spec in atlas.as_tools(actor="agent:worker")]
```

---

## Project Structure

```
taskatlas/
├── __init__.py     # Public API: Atlas, Dream, Goal, Task, Link, Event
├── _atlas.py       # Atlas root factory, single event store, diffs, compaction, atomic I/O
├── _dream.py       # Optional Dream horizon, milestone momentum, stall detection
├── _goal.py        # Convergent Goal model, criteria, outcomes, transitive progress
├── _task.py        # Executable Task model, receipts, holds, worker claims
├── _base.py        # Bound _WorkItem and _CausalWorkItem physics
├── _link.py        # Immutable Link model (depends_on, relates_to, derived_from)
├── _event.py       # Immutable Event model with actor provenance
├── _filtering.py   # Transitive keyword filtering and sorting
├── _views.py       # Board, progressive tree, critical-path queue, summary, brief()
├── _tools.py       # Zero-dependency LLM tool schemas and receipt-returning dispatch
├── _identity.py    # Collision-guarded prefixed IDs (d-, g-, t-, lk-, ev-, n-)
└── _types.py       # Lifecycle vocabularies and priority ranks
```

---

## Tutorials

1. **[Quickstart](tutorials/01_quickstart.md)** - Your first Atlas, Goals, Tasks, receipts, and briefings
2. **[Modeling a Real Project](tutorials/02_modeling_a_real_project.md)** - End-to-end architecture from Dream to Subtasks
3. **[Relationships and Structure](tutorials/03_relationships_and_structure.md)** - Transitive containment vs. acyclic causal links
4. **[History and Evolution](tutorials/04_history_and_evolution.md)** - Single-store immutable events, actors, cursors, and diffs
5. **[Views and Context](tutorials/05_views_and_context.md)** - Critical-path queue, hydrated context, progressive tree, and `brief()`
6. **[Persistence and Programmatic Use](tutorials/06_persistence_and_programmatic_use.md)** - Atomic saves, compaction, worker claims, and agent tool dispatch
7. **[Filtering and Retrieval](tutorials/07_filtering_and_retrieval.md)** - Transitive filters, blockage queries, predicates, and sorting

---

## Running Tests & Linting

```bash
pytest
ruff check .
```

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) for the branch model, testing workflow, and PR guidelines.

---

## License

MIT
