# Contributing to taskatlas

Thank you for your interest in contributing. This is a small, focused library — contributions that keep it lean and readable are most welcome.

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

All 213 tests should pass before you open a pull request.

## Running the linter

```bash
ruff check .
ruff format --check .
```

Fix any issues with:

```bash
ruff check --fix .
ruff format .
```

---

## Branch model

- `main` — production, mirrors what is on PyPI
- `develop` — integration branch for ongoing work

Please target all pull requests at `develop`. The `main` branch is only updated when a new version is ready to release to PyPI.

Feature branches should be named descriptively, e.g. `fix/duplicate-links` or `feat/tag-mutation-api`.

---

## Releasing (maintainers only)

1. Merge `develop` → `main` via pull request
2. Bump the version in `pyproject.toml` and `taskatlas/__init__.py`
3. Add a `[x.y.z]` entry to `CHANGELOG.md`
4. Push a version tag from `main`:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. GitHub Actions will build and publish to PyPI automatically

---

## Pull request etiquette

- Keep changes focused — one concern per PR
- Add or update tests for any behavior changes
- Update `CHANGELOG.md` under `[Unreleased]` with a brief note
- Keep the zero-dependency constraint — do not add external imports to the `taskatlas/` package

---

## Questions

Open a GitHub Issue or reach out at james@think.dev.
