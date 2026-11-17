# Modeling a Real Project

This walkthrough models a realistic multi-horizon system using the full `Dream -> Goal -> Subgoal -> Task -> Subtask` hierarchy, causal dependencies, external holds, and open-world stall detection.

---

## 1. Anchor With an Optional Dream

Suppose you are building an autonomous data platform over multiple quarters. A `Dream` captures the enduring north star above individual quarterly milestones:

```python
import taskatlas as ta

atlas = ta.Atlas("Data Platform", meta={"org": "data-eng"})

dream = atlas.add_dream(
    "Self-Healing Data Platform",
    vision="Pipelines ingest, transform, and recover from upstream schema drift automatically.",
    status="active",
    priority="high",
)
```

---

## 2. Define Wave-1 Goals With Falsifiable Criteria

```python
ingestion = dream.add_goal(
    "Reliable ingestion service",
    summary="Accept events from 10+ sources with at-least-once delivery.",
    status="active",
    priority="urgent",
    criteria=[
        "Broker restart test passes with zero dropped records",
        "Schema registry validates payloads in < 2ms",
    ],
    tags=["ingestion", "core"],
)

transform = dream.add_goal(
    "SQL transformation engine",
    summary="DAG-ordered SQL models over ingested streams.",
    status="active",
    priority="high",
    criteria=["Cycle-free model graph execution"],
    tags=["transform", "core"],
)

# Standalone operational goal outside any Dream
ops = atlas.add_goal(
    "Quarterly credential hygiene",
    status="active",
    priority="medium",
    tags=["security"],
)
```

---

## 3. Decompose Goals Into Tasks and Subtasks

```python
schema_registry = ingestion.add_task(
    "Build schema registry",
    stage="active",
    priority="high",
)
# Subtasks inherit ingestion's Goal and Dream lineage transitively
v_model = schema_registry.add_task("Design versioning model", stage="ready", priority="high")
storage = schema_registry.add_task("Implement SQLite WAL backend", stage="ready", priority="high")
storage.link(v_model, kind="depends_on")

kafka = ingestion.add_task("Implement Kafka connector", stage="ready", priority="high")

sql_parser = transform.add_task("Build SQL parser", stage="ready", priority="urgent")
# Cross-goal causal dependency: SQL parser requires schema_registry to complete
sql_parser.link(schema_registry, kind="depends_on")

rotate_keys = ops.add_task("Rotate staging IAM keys", stage="ready", priority="medium")
```

---

## 4. Simulate Execution, Holds, and Cancellation

```python
with atlas.as_actor("agent:data-worker"):
    # Complete the first leaf subtask with an artifact receipt
    v_model.complete(
        "Defined backward-compatible version rules.",
        artifacts=["docs/schema_versioning.md"],
    )

    # External impediment on Kafka without losing its 'ready' workflow stage
    kafka.hold("Waiting on VPC peering from cloud-infra")

    # Drop speculative work cleanly without locking goal progress below 100%
    legacy_csv = ingestion.add_task("Legacy FTP importer", stage="inbox")
    legacy_csv.cancel(reason="FTP feed retired by upstream team")
```

---

## 5. Inspect Horizon Momentum, Queue, and Briefing

```python
# Dream progress tracks milestone counts, active wave execution, and stall health
dp = dream.progress()
print(dp["stalled"], dp["active_wave"])
# False {'task_count': 4, 'done_count': 1, 'open_count': 3, 'blocked_count': 2, ...}

# Goal progress traverses subtasks automatically and excludes canceled tasks
gp = ingestion.progress()
print(gp["done_count"], gp["task_count"], gp["canceled_count"])
# 1 3 1

# Ready queue boosts 'storage' to URGENT because 'schema_registry' unblocks urgent 'sql_parser'
for item in atlas.queue():
    print(item["effective_priority"], item["title"])

# Single compact Markdown briefing covering Dreams, Goals, Ready Queue, and Impediments
print(atlas.brief())
```
