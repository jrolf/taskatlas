# Changelog

All notable changes to taskatlas will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.0.2] - 2026-03-15

### Added
- `CONTRIBUTING.md` — branch model, dev setup, PR guidelines, release process
- `SECURITY.md` — vulnerability reporting and scope statement
- `.github/workflows/ci.yml` — automated pytest runs across Python 3.10, 3.11, 3.12, and 3.13 on every push and pull request
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
- `Atlas` — root container owning all goals, tasks, links, and events
- `Goal` — higher-order intended outcomes with statuses: `proposed`, `active`, `paused`, `achieved`, `archived`
- `Task` — actionable work units with stages: `inbox`, `ready`, `active`, `blocked`, `review`, `done`, `archived`
- `Link` — typed cross-references between entities (`depends_on`, `blocks`, `relates_to`, `supports`, `duplicates`, `derived_from`, `conflicts_with`)
- `Event` — automatic immutable history records for every meaningful mutation
- Containment model — structural nesting of subtasks under tasks, subgoals under goals, tasks under goals
- Filtering and retrieval via `get_tasks()` and `get_goals()` with keyword arguments
- Four built-in views: `board()`, `tree()`, `queue()`, `summary()`
- `context()` method on goals and tasks for compact or full situational summaries
- Full round-trip JSON serialization via `save()`, `load()`, `to_dict()`, `from_dict()`
- Priority model: `critical`, `high`, `medium`, `low`
- Notes — append-only, timestamped annotations on any goal or task
- 213-test suite covering all modules, relationships, history, views, and serialization
- 7 tutorial walkthroughs in `tutorials/`
- Zero external dependencies — Python 3.10+ standard library only

---

<!-- Release links -->
[Unreleased]: https://github.com/jrolf/taskatlas/compare/v0.0.2...HEAD
[0.0.2]: https://github.com/jrolf/taskatlas/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/jrolf/taskatlas/releases/tag/v0.0.1
