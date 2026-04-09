---
description: "Use when editing Flask backend code under source/app or source/run.py, including REST routes, GraphQL handlers, business logic, persistence, models, schema code, or Alembic migrations. Covers layered boundaries, naming conventions, configuration, and backend test workflow."
name: "Backend Python Guidelines"
applyTo: "source/app/**/*.py, source/run.py"
---

# Backend Python Guidelines

- Keep the backend flow intact: blueprints handle request parsing, permissions, and HTTP responses; business handles domain logic; datamgmt handles persistence. Do not bypass the business layer.
- Respect the import boundaries documented in [architecture.md](../../architecture.md) and enforced from [pyproject.toml](../../pyproject.toml): blueprints must not import `app.datamgmt` or `sqlalchemy`; business must not import `app.db` or blueprints; datamgmt must not import business.
- Follow the repo-specific Python rules from [CODESTYLE.md](../../CODESTYLE.md): use f-strings, keep one import per line, prefix private names with `_`, keep `__init__.py` files minimal where practical, and use module-prefixed function names such as `assets_create`.
- Mirror existing locations and patterns: request handlers in `source/app/blueprints`, domain logic in `source/app/business`, persistence in `source/app/datamgmt`, shared objects in `source/app/models` and `source/app/schema`, and migrations in `source/app/alembic`.
- Check [CONFIGURATION.md](../../CONFIGURATION.md) before adding settings. Configuration precedence is Azure Key Vault, then environment variables, then config files.
- If a change affects schema or persisted models, add or update an Alembic migration under `source/app/alembic` in the same change.
- When validating backend work, prefer the Docker dev stack from the repository root and the `unittest` workflow documented in [tests/README.md](../../tests/README.md).