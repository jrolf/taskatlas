# Contributing to taskatlas

Thank you for your interest in contributing. This is a small, focused library - contributions that keep it lean and readable are most welcome.

---

## Getting started

Clone the repo and install development dependencies:

```bash
git clone https://github.com/jrolf/taskatlas.git
cd taskatlas
pip install -e ".[dev]"
```

## Running the tests

```bash
pytest
```

All tests in the `pytest` suite must pass before you open a pull request.

## Running the linter

```bash
ruff check .
```

Fix any lint issues with:

```bash
ruff check --fix .
```

---

## Branch model

- `main` - production, mirrors what is on PyPI
- `develop` - integration branch for ongoing work

Please target all pull requests at `develop`. The `main` branch is only updated when a new version is ready to release to PyPI.

Feature branches should be named descriptively, e.g. `fix/dependency-cycle-check` or `feat/dream-momentum`.

---

## Releasing (maintainers only)

1. Bump the version in `pyproject.toml` and `taskatlas/__init__.py` on `develop`
2. Promote `[Unreleased]` to a dated `[x.y.z]` entry in `CHANGELOG.md` on `develop`
3. Open and merge a pull request from `develop` -> `main`
4. GitHub Actions (`publish.yml`) verifies version alignment, lint, and tests, then builds and publishes to PyPI automatically (optionally tag `vX.Y.Z` on `main` for GitHub Releases)

---

## Pull request etiquette

- Keep changes focused - one concern per PR
- Add or update tests for any behavior changes
- Update `CHANGELOG.md` under `[Unreleased]` with a concise summary
- Keep the zero-dependency constraint - do not add external imports to the `taskatlas/` package

---

## Questions

Open a GitHub Issue or reach out at james@think.dev.
