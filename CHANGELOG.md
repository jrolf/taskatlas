# Changelog

All notable changes to taskatlas will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Optional `Dream` horizon (`ta.Dream`, `d-` prefix):** Top-level open-world vision layer above `Goal` with `vision`, statuses (`seed`, `active`, `dormant`, `realized`, `abandoned`), milestone momentum tracking (`dream.progress()`), and automatic stall detection (`no_active_goals`, `no_open_tasks`, `all_tasks_blocked`). Views use progressive disclosure so zero-dream Atlases have zero dream clutter.
- **Goal acceptance criteria & outcomes:** `Goal` now supports falsifiable `criteria` (`add_criterion()`, `remove_criterion()`), `outcome` summaries, and explicit `achieve()` / `abandon()` lifecycle helpers.
- **Task completion & cancellation receipts:** `task.complete(summary, artifacts=..., data=...)` and `task.cancel(reason, superseded_by=...)` record structured receipts on `task.result` and automatically propagate upstream receipts into downstream `context()` and `brief()`.
- **External holds & live topological blockage:** Added `hold(reason)` / `unhold(reason)` (`is_held`, `hold_reason`) alongside live `is_topologically_blocked` and `is_blocked` properties, plus `.blocks(target)`, `.blockers()`, `.dependencies()`, and `.dependents()`.
- **Actor provenance & worker claims:** Added `atlas.as_actor(...)` context manager, `actor` attribution on `Event` and notes, and conflict-checked `task.claim()` / `task.release()` ownership for multi-agent coordination.
- **Temporal continuity primitives:** Added `atlas.cursor`, `atlas.events_since(cursor)`, `atlas.copy()`, `atlas.diff(other)` (with `newly_unblocked_tasks` and `newly_blocked_tasks`), and `atlas.compact(...)`.
- **Token-tight briefings & zero-dependency agent tool seam:** Added `.brief()` Markdown renderers on `Atlas`, `Dream`, `Goal`, and `Task`, plus `atlas.tool_schemas()`, `atlas.dispatch()`, and `atlas.as_tools()` in `taskatlas/_tools.py`.

### Changed
- **Bound-from-birth factory model:** `Atlas` (and bound parents `Dream`, `Goal`, `Task`) is now the sole entity factory; direct unbound instantiation raises `TypeError` with guidance, and `add_*()` is cleanly separated from `attach_*()`.
- **Orthogonal lifecycle, blockage, and archival model:** Separated workflow `stage` (`inbox`, `ready`, `active`, `review`, `done`, `canceled`) and `Goal.status` (`proposed`, `active`, `paused`, `achieved`, `abandoned`) from `is_blocked` and `archived: bool` (`archive()` / `unarchive()`), preventing archived or obsolete tasks from corrupting `goal.progress()`.
- **Canonical acyclic links:** Simplified `LINK_KINDS` to `depends_on`, `relates_to`, and `derived_from`, enforcing DAG acyclicity on `depends_on` and normalizing `b.blocks(a)` to canonical `a -> depends_on -> b` edges.
- **Transitive containment & critical-path `queue()`:** `goal.progress()`, `board()`, `queue()`, `tree()`, and `get_tasks()` / `get_goals()` now traverse `Dream -> Goal -> Subgoal -> Task -> Subtask` transitively; `atlas.queue()` filters blocked/held/review/paused/claimed items and computes critical-path `effective_priority` inheritance.
- **Single-store immutable events & hardened persistence:** Events are stored and serialized once on `Atlas` (`schema 0.3.0`, with automatic migration from `0.2.0` payloads), `Event` and `Link` instances are immutable, tracked entity fields are read-only properties, `atlas.save()` is POSIX-atomic (`mkstemp` + `fsync` + `os.replace`), and `Atlas.from_dict()` validates bidirectional referential integrity.

### Removed
- Removed broken custom `task_stages` and `goal_statuses` overrides on `Atlas` in favor of a single coherent lifecycle model with defined readiness and progress semantics.
- Removed redundant/ornamental link kinds (`blocks` as a separate stored edge kind, `supports`, `duplicates`, `conflicts_with`).

---

## [0.0.2] - 2026-03-15

### Added
- `CONTRIBUTING.md` - branch model, dev setup, PR guidelines, release process
- `SECURITY.md` - vulnerability reporting and scope statement
- `.github/workflows/ci.yml` - automated pytest runs across Python 3.10, 3.11, 3.12, and 3.13 on every push and pull request
- PyPI, Python version, license, and CI status badges in `README.md`
- `Contributing` section in `README.md`
- `Changelog` URL in `pyproject.toml` project URLs
- Ruff linting configuration in `pyproject.toml`
- `ruff` added to `dev` optional dependencies

### Changed
- Tutorial `01_quickstart.md` install step updated from `pip install -e .` to `pip install taskatlas`
- `CONCEPT.md` and `CRITICAL_REVIEW.md` removed from git tracking (files kept locally)

---

## [0.0.1] - 2026-03-15

### Added
- `Atlas` - root container owning all goals, tasks, links, and events
- `Goal` - higher-order intended outcomes with statuses: `proposed`, `active`, `paused`, `achieved`, `archived`
- `Task` - actionable work units with stages: `inbox`, `ready`, `active`, `blocked`, `review`, `done`, `archived`
- `Link` - typed cross-references between entities (`depends_on`, `blocks`, `relates_to`, `supports`, `duplicates`, `derived_from`, `conflicts_with`)
- `Event` - automatic immutable history records for every meaningful mutation
- Containment model - structural nesting of subtasks under tasks, subgoals under goals, tasks under goals
- Filtering and retrieval via `get_tasks()` and `get_goals()` with keyword arguments
- Four built-in views: `board()`, `tree()`, `queue()`, `summary()`
- `context()` method on goals and tasks for compact or full situational summaries
- Full round-trip JSON serialization via `save()`, `load()`, `to_dict()`, `from_dict()`
- Priority model: `urgent`, `high`, `medium`, `low`
- Notes - append-only, timestamped annotations on any goal or task
- Test suite covering modules, relationships, history, views, and serialization
- 7 tutorial walkthroughs in `tutorials/`
- Zero external dependencies - Python 3.10+ standard library only

---

<!-- Release links -->
[Unreleased]: https://github.com/jrolf/taskatlas/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/jrolf/taskatlas/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/jrolf/taskatlas/releases/tag/v0.0.1
