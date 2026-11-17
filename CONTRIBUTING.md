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

1. Merge `develop` -> `main` via pull request
2. Bump the version in `pyproject.toml` and `taskatlas/__init__.py`
3. Add a `[x.y.z]` entry to `CHANGELOG.md`
4. Push to `main` (and tag `vX.Y.Z` for GitHub Releases)
5. GitHub Actions will build and publish to PyPI automatically

---

## Pull request etiquette

- Keep changes focused - one concern per PR
- Add or update tests for any behavior changes
- Update `CHANGELOG.md` under `[Unreleased]` with a concise summary
- Keep the zero-dependency constraint - do not add external imports to the `taskatlas/` package

---

## Questions

Open a GitHub Issue or reach out at james@think.dev.
