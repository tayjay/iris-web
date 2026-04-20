---
description: "Use when editing Docker Compose files, Dockerfiles, or container startup scripts. Covers local dev stack commands, service dependency/healthcheck expectations, frontend profile behavior, and safe Docker workflow practices."
name: "Docker Workflow Guidelines"
applyTo: "docker-compose*.yml, docker/**/Dockerfile, docker/**/*.sh, docker/**/*.conf"
---

# Docker Workflow Guidelines

- Use the repository root Docker workflow from [README.md](../../README.md) and [tests/README.md](../../tests/README.md). For app-level development, prefer `docker compose --file docker-compose.dev.yml up --detach --wait` and stop with `docker compose down`.
- Keep Compose layering consistent: services in `docker-compose.dev.yml` extend `docker-compose.base.yml`. Preserve `extends` structure unless the task explicitly requires reshaping service ownership.
- Preserve startup safety when changing service dependencies: keep health checks meaningful and keep `depends_on` conditions aligned with `service_healthy` expectations.
- Keep volume intent intact in dev compose: backend code is mounted from `./source/app` and frontend built assets are mounted from `./ui/dist`.
- Treat the `frontend` service in `docker-compose.dev.yml` as optional (`new-ui` profile) and external by default (`../iris-frontend`). Do not assume that external path exists in this workspace.
- When editing Dockerfiles or container entrypoint scripts under `docker/`, keep behavior aligned with existing compose service expectations (ports, mounted paths, startup commands, and health checks).
- After editing Compose files, validate merged configuration with `docker compose --file docker-compose.dev.yml config` before concluding.
- Avoid destructive Docker operations (for example removing volumes) unless the task explicitly requests cleanup or data reset.
- If workflow changes impact backend tests, keep instructions compatible with the documented `unittest` + Docker flow in [tests/README.md](../../tests/README.md).
