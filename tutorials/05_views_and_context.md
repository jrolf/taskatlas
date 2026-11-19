# Views, Readiness Queue, Context, and Briefings

`taskatlas` exposes structured Python views (`board`, `tree`, `queue`, `summary`), hydrated entity `context()`, and token-tight Markdown `brief()` renderers.

---

## Setup

```python
import taskatlas as ta

atlas = ta.Atlas("Views Demo")
dream = atlas.add_dream("Unified Developer Portal", status="active", priority="high")

backend = dream.add_goal("Backend API", status="active", priority="urgent")
frontend = dream.add_goal("Web UI", status="active", priority="high")

db = backend.add_task("Database layer", stage="active", priority="high")
migrations = db.add_task("Schema migrations", stage="ready", priority="medium")
pooling = db.add_task("Connection pooling", stage="ready", priority="medium")

routes = backend.add_task("API routes", stage="ready", priority="urgent")
routes.link(db, kind="depends_on")

ui_shell = frontend.add_task("App shell", stage="ready", priority="high")
ui_shell.hold("Waiting on brand typography tokens")
```

---

## 1. Critical-Path Ready Queue (`atlas.queue()`)

`atlas.queue()` answers **"What executable leaf task should be worked on next?"**:

- Excludes `done`, `canceled`, `review`, and `archived` tasks.
- Excludes container parent tasks while they still have open subtasks (surfacing `migrations` and `pooling` rather than `db`, even when scoped to `goal_id=backend.id` or `dream_id=dream.id`).
- Excludes topologically blocked (`routes`) and externally held (`ui_shell`) tasks.
- Excludes tasks under `paused` Goals or `dormant` Dreams, and tasks claimed by other workers.
- Computes **critical-path priority inheritance**: if a low/medium prerequisite blocks an `urgent` task, its `effective_priority` is boosted automatically.

```python
for item in atlas.queue():
    print(item["effective_priority"], item["title"], item["stage"])
```

---

## 2. Progressive Tree (`atlas.tree()`)

- When the Atlas has **no Dreams**, `atlas.tree()` renders `{"goals": [...], "unattached_tasks": [...]}` with zero Dream keys.
- When **Dreams exist**, `atlas.tree()` renders `{"dreams": [...], "unattached_goals": [...], "unattached_tasks": [...]}`.
- Archived items are filtered consistently at *every* depth unless `include_archived=True` is passed.

---

## 3. Workflow Board & Aggregate Summary

```python
# All non-archived tasks bucketed across inbox, ready, active, review, done, canceled
full_board = atlas.board()

# Transitively scoped to a Goal or Dream (includes nested subtasks!)
backend_board = atlas.board(goal_id=backend.id)
dream_board = atlas.board(dream_id=dream.id)

# Health overview (includes stalled_dreams whenever Dreams are present)
summary = atlas.summary()
```

---

## 4. Hydrated Neighborhood Context (`context()`)

Unlike raw foreign-key dumps, `context()` resolves 1-hop neighbors inline with titles and states, attaches a ~15-token `dream` breadcrumb on Tasks and Goals, and propagates upstream completion receipts:

```python
migrations.complete("Applied initial DDL", artifacts=["sql/001_init.sql"])
pooling.complete("Configured PgBouncer pool", artifacts=["infra/pgbouncer.ini"])
db.complete("Database layer verified end-to-end", artifacts=["src/db.py"])

# 'routes' is now unblocked and immediately sees 'src/db.py' in satisfied_dependencies!
ctx = routes.context(mode="full")
print(ctx["is_blocked"])  # False
print(ctx["dream"])       # {'id': 'd-...', 'title': 'Unified Developer Portal', 'status': 'active'}
print(ctx["satisfied_dependencies"][0]["result"]["artifacts"])
# ['src/db.py']
```

---

## 5. Token-Tight Markdown Briefings (`brief()`)

When feeding state into an LLM prompt (such as `ThoughtFlow`'s `THOUGHT`), `.brief()` renders the exact situational picture in compact Markdown at a fraction of the token cost of raw JSON:

```python
print(atlas.brief())
print(dream.brief())
print(backend.brief())
print(routes.brief())
```
