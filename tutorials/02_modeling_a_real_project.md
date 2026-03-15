# Modeling a Real Project

This tutorial walks through a realistic scenario: using `taskatlas` to model a software project with multiple goals, hierarchical task decomposition, cross-cutting dependencies, and evolving state. The goal is to show how the library feels when used on something real.

---

## Scenario

You're building a data pipeline platform. There are three major outcomes to deliver this quarter:

1. A reliable ingestion service
2. A transformation engine
3. A monitoring dashboard

Each has its own tasks, subtasks, and interdependencies.

---

## Set Up the Atlas

```python
import taskatlas as ta

atlas = ta.Atlas({
    "name": "Data Pipeline Platform",
    "meta": {"team": "data-eng", "quarter": "Q3-2025"},
})
```

The `meta` field is a free-form dict — use it for any metadata that doesn't fit into the structured fields.

---

## Define the Goals

```python
ingestion = atlas.add_goal({
    "title": "Reliable ingestion service",
    "summary": "Accept data from 10+ sources with at-least-once delivery guarantees.",
    "status": "active",
    "priority": "urgent",
    "tags": ["ingestion", "core"],
})

transform = atlas.add_goal({
    "title": "Transformation engine",
    "summary": "SQL-based transformation layer with dependency resolution.",
    "status": "active",
    "priority": "high",
    "tags": ["transform", "core"],
})

monitoring = atlas.add_goal({
    "title": "Monitoring dashboard",
    "summary": "Real-time visibility into pipeline health and data freshness.",
    "status": "proposed",
    "priority": "medium",
    "tags": ["monitoring", "observability"],
})
```

Notice that monitoring is still `proposed` — the team hasn't committed to it yet. Goals have their own lifecycle independent of tasks.

---

## Decompose into Tasks

### Ingestion tasks

```python
schema_registry = ingestion.add_task({
    "title": "Build schema registry",
    "summary": "Central registry for source schemas with versioning.",
    "stage": "active",
    "priority": "urgent",
    "tags": ["schema", "ingestion"],
})

kafka_connector = ingestion.add_task({
    "title": "Implement Kafka connector",
    "stage": "ready",
    "priority": "high",
    "tags": ["kafka", "ingestion"],
})

s3_connector = ingestion.add_task({
    "title": "Implement S3 connector",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["s3", "ingestion"],
})

backfill = ingestion.add_task({
    "title": "Design backfill mechanism",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["backfill", "ingestion"],
})
```

### Transformation tasks

```python
sql_parser = transform.add_task({
    "title": "Build SQL parser",
    "stage": "active",
    "priority": "high",
    "tags": ["sql", "transform"],
})

dag_resolver = transform.add_task({
    "title": "Implement DAG dependency resolver",
    "stage": "ready",
    "priority": "high",
    "tags": ["dag", "transform"],
})

scheduling = transform.add_task({
    "title": "Build scheduling layer",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["scheduling", "transform"],
})
```

### Monitoring tasks

```python
health_api = monitoring.add_task({
    "title": "Expose pipeline health API",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["api", "monitoring"],
})

freshness = monitoring.add_task({
    "title": "Implement data freshness tracking",
    "stage": "inbox",
    "priority": "medium",
    "tags": ["freshness", "monitoring"],
})
```

---

## Break Down Complex Tasks with Subtasks

The schema registry is complex enough to warrant subtasks:

```python
schema_registry.add_task({
    "title": "Design schema versioning model",
    "stage": "done",
    "priority": "high",
})

schema_registry.add_task({
    "title": "Implement schema storage backend",
    "stage": "active",
    "priority": "high",
})

schema_registry.add_task({
    "title": "Build schema validation endpoint",
    "stage": "ready",
    "priority": "medium",
})

schema_registry.add_task({
    "title": "Write schema migration tooling",
    "stage": "inbox",
    "priority": "low",
})
```

Now `schema_registry` is both a task (attached to the ingestion goal) and a parent (with four subtasks beneath it).

---

## Model Dependencies with Links

The transformation engine depends on the schema registry — it needs to know the shapes of the data it's transforming:

```python
sql_parser.link(schema_registry, kind="depends_on")
```

The DAG resolver depends on the SQL parser:

```python
dag_resolver.link(sql_parser, kind="depends_on")
```

The scheduling layer depends on the DAG resolver:

```python
scheduling.link(dag_resolver, kind="depends_on")
```

The monitoring dashboard's freshness tracking depends on the ingestion service being operational:

```python
freshness.link(kafka_connector, kind="depends_on")
freshness.link(s3_connector, kind="depends_on")
```

Cross-goal support relationships:

```python
monitoring.link(ingestion, kind="supports")
monitoring.link(transform, kind="supports")
```

These typed links capture real project structure — dependency chains, support relationships, and cross-cutting concerns — without conflating them with containment.

---

## Simulate Work in Progress

A week passes. Work moves forward:

```python
kafka_connector.move("active", reason="Dev assigned, starting implementation")
kafka_connector.note("Using confluent-kafka client library, version 2.3")

schema_registry.move("review", reason="Core implementation complete, PR open")
schema_registry.note("Reviewer: @maria — focused on migration edge cases")

sql_parser.move("blocked", reason="Waiting on schema registry finalization")
sql_parser.note("Need final schema format before we can parse incoming payloads")

monitoring.set_status("active", reason="Team committed to Q3 delivery after all")

ingestion.note("On track. Schema registry nearly done, Kafka connector in progress.")
```

---

## Inspect the State of Things

### Board view — where is everything?

```python
board = atlas.board()
for stage, tasks in board["stages"].items():
    if tasks:
        print(f"\n{stage.upper()}:")
        for t in tasks:
            print(f"  - [{t['priority']}] {t['title']}")
```

### Board scoped to a single goal

```python
ingestion_board = atlas.board(goal_id=ingestion.id)
```

### Tree view — the full hierarchy

```python
import json
tree = atlas.tree()
print(json.dumps(tree, indent=2))
```

This produces a nested structure showing goals → subgoals → tasks → subtasks, making the project's shape visible at a glance.

### Queue view — what should I work on next?

```python
queue = atlas.queue()
for item in queue[:5]:
    print(f"[{item['priority']}] {item['title']} ({item['stage']})")
```

The queue surfaces leaf-level actionable tasks sorted by priority, filtering out completed/archived work and parent tasks that exist primarily as containers.

### Progress check

```python
for goal in atlas.get_goals(status="active"):
    p = goal.progress()
    print(f"{goal.title}: {p['done_count']}/{p['task_count']} done ({p['done_ratio']:.0%})")
```

### Summary

```python
summary = atlas.summary()
print(f"Goals: {summary['goal_count']}")
print(f"Tasks: {summary['task_count']}")
print(f"By stage: {summary['by_stage']}")
```

---

## Context for a Specific Task

When you need the full picture of a single work item — its relationships, notes, recent history:

```python
ctx = sql_parser.context(mode="full")
print(json.dumps(ctx, indent=2, default=str))
```

This returns everything relevant: the task's metadata, its links (showing the dependency on schema_registry), its notes, its recent events, and its parent/child structure.

The compact mode gives you just the essentials:

```python
ctx = sql_parser.context()  # compact by default
```

---

## What We Modeled

In about 60 lines of setup code, this atlas now represents:

- **3 goals** at different lifecycle stages
- **9 top-level tasks** decomposed across those goals
- **4 subtasks** under the schema registry
- **5 typed dependency links** capturing real execution order
- **2 cross-goal support links**
- **Ongoing notes** capturing decisions and context
- **Automatic history** of every mutation

This is the sweet spot `taskatlas` is designed for: rich enough to model real project structure, lean enough that the code reads clearly and the data stays lightweight.
