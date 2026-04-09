# Project Guidelines

## Architecture
- Backend Python code lives under `source/app` and follows a layered architecture: `app.blueprints` handles REST, GraphQL, templates, and Socket.IO entrypoints; `app.business` owns domain logic; `app.datamgmt` owns persistence. Keep changes inside the correct layer and do not bypass the blueprints -> business -> datamgmt flow.
- Import boundaries are enforced from `pyproject.toml`. In particular, blueprints should not import `app.datamgmt` or `sqlalchemy`, and business code should not import `app.db` or blueprints.
- Frontend assets in this repository live under `ui`. Reusable Svelte components belong in `ui/src/lib/components`, while page entrypoints belong in `ui/src/pages`. Built assets are written to `ui/dist` and mounted into the app container.
- Use the Python API tests in `tests`, Playwright end-to-end tests in `e2e`, and deployment files under `deploy/` and the root Docker Compose files.

## Build and Test
- Prefer the Docker development stack for app-level work: from the repository root run `docker compose --file docker-compose.dev.yml up --detach --wait`, and stop it with `docker compose down`.
- Backend API tests use `unittest`, not `pytest`. Follow `tests/README.md`: from `tests`, create and activate a virtual environment, install `requirements.txt`, ensure the dev stack is running, then run `python -m unittest --verbose` or a fully qualified single test.
- Frontend work happens in `ui`: use `npm install`, `npm run watch` for rebuild-on-change development, `npm run build` for production assets, and `npm run lint` before finishing UI changes.
- End-to-end tests live in `e2e`: use `npm run test` for the full Playwright flow, or `npm run start`, `npm run e2e`, and `npm run stop` when debugging.

## Conventions
- Follow the project docs instead of restating them: see [README.md](../README.md), [architecture.md](../architecture.md), [CODESTYLE.md](../CODESTYLE.md), [CONFIGURATION.md](../CONFIGURATION.md), and [CONTRIBUTING.md](../CONTRIBUTING.md).
- Python conventions that differ from common defaults: use f-strings, keep one import per line, prefix private names with `_`, keep `__init__.py` files minimal where practical, and name functions with a module-specific prefix such as `assets_create`.
- If a change affects database schema or persisted models, add an Alembic migration under `source/app/alembic`.
- Mirror existing patterns when editing backend code: routes and request handling in `source/app/blueprints`, domain logic in `source/app/business`, and database access in `source/app/datamgmt`.
- Check `CONFIGURATION.md` before adding or changing settings. Configuration precedence is Azure Key Vault, then environment variables, then config files.
- The optional `frontend` service in `docker-compose.dev.yml` points at an external `../iris-frontend` checkout. Do not assume it is part of this workspace; frontend work in this repository is usually the `ui` application unless the task says otherwise.
- Branch and PR workflow is documented in `CONTRIBUTING.md` and `CODESTYLE.md`; repository changes normally target `develop`, even though `master` remains the default release branch.
