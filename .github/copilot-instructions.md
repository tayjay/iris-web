# Project Guidelines

## Architecture
- Backend Python code under `source/app` follows layered boundaries: `app.blueprints` (REST/GraphQL/templates/Socket.IO entrypoints) -> `app.business` (domain logic) -> `app.datamgmt` (persistence).
- Respect import boundaries enforced from `pyproject.toml`: blueprints must not import `app.datamgmt` or `sqlalchemy`; business must not import `app.db` or blueprints.
- Frontend code in this repository lives under `ui` (`ui/src` + `ui/public`); `ui/dist` is generated output.
- Keep changes aligned with [architecture.md](../architecture.md). 

## Build and Test
- Start the app-level dev stack from repo root with `docker compose --file docker-compose.dev.yml up --detach --wait`; stop with `docker compose down`.
- Backend API tests use `unittest` (not `pytest`). Follow [tests/README.md](../tests/README.md) and run `python -m unittest --verbose` from `tests`.
- Frontend workflow in `ui`: `npm install`, `npm run watch`, `npm run build`, `npm run lint`.
- End-to-end workflow in `e2e`: `npm run test` (full flow) or `npm run start` + `npm run e2e` + `npm run stop`.

## API Reference
- REST v2 endpoints are rooted at `/api/v2` via `source/app/blueprints/rest/api_v2_routes.py`, with per-domain handlers under `source/app/blueprints/rest/v2`.
- Canonical API reference publishing is external: use the docs links in [README.md](../README.md) (`docs.dfir-iris.org` and the `iris-doc-src` repository) rather than embedding endpoint reference docs in this repository.
- GraphQL reference in this repository is generated from `source/spectaql/config.yml` (CI uses `npx spectaql@^3.0.2 source/spectaql/config.yml`).

## Conventions
- Link to canonical docs instead of duplicating policy: [README.md](../README.md), [architecture.md](../architecture.md), [CODESTYLE.md](../CODESTYLE.md), [CONFIGURATION.md](../CONFIGURATION.md), [CONTRIBUTING.md](../CONTRIBUTING.md).
- Repo-specific Python conventions: prefer f-strings, one import per line, `_`-prefixed private names, minimal `__init__.py` files, and module-prefixed function names (for example `assets_create`).
- If schema or persisted model behavior changes, include an Alembic migration under `source/app/alembic`.
- Configuration precedence is Azure Key Vault -> environment variables -> config files.
- The optional `frontend` profile in `docker-compose.dev.yml` points to an external `../iris-frontend` checkout; default frontend edits in this repo should target `ui`.
- Prefer branch and PR workflow from [CONTRIBUTING.md](../CONTRIBUTING.md); typical target branch is `develop`.

## Scoped Instructions
- For backend Python edits, follow `.github/instructions/backend-python.instructions.md`.
- For frontend UI edits, follow `.github/instructions/frontend-ui.instructions.md`.
- For automated test edits, follow `.github/instructions/test-workflows.instructions.md`.
- For Docker and Compose edits, follow `.github/instructions/docker-workflows.instructions.md`.
