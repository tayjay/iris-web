---
description: "Use when adding or updating automated tests, including Python API tests under tests, database migration tests under tests_database_migration, or Playwright end-to-end tests under e2e. Covers unittest conventions, Docker prerequisites, and test separation."
name: "Test Workflow Guidelines"
applyTo: "tests/*.py, tests/**/*.py, tests_database_migration/*.py, tests_database_migration/**/*.py, e2e/*.js, e2e/tests/**/*.js, e2e/*.json, e2e/*.md"
---

# Test Workflow Guidelines

- Keep test types separated: Python API and integration tests live under `tests` and use `unittest`; browser flows live under `e2e` with Playwright; schema migration checks live under `tests_database_migration`.
- Follow [tests/README.md](../../tests/README.md) for backend API tests: create a virtual environment in `tests`, install `requirements.txt`, start the Docker dev stack, then run `python -m unittest --verbose` or a fully qualified single test.
- Reuse the existing backend test helpers and patterns in `tests/iris.py`, `tests/rest_api.py`, `tests/graphql_api.py`, and the existing `tests_rest_*.py` modules instead of creating a new harness.
- Use the scripts in `e2e/package.json` for browser tests: `npm run test` for the full flow, or `npm run start`, `npm run e2e`, and `npm run stop` while debugging.
- Do not default to `pytest` for backend tests in this repository.
- If a test needs Docker services or persistent state, say so explicitly. Avoid destructive cleanup such as removing Docker volumes unless the task requires it.