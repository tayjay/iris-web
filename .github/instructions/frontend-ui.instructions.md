---
description: "Use when editing the frontend under ui, including Svelte components, page entrypoints, public assets, Vite config, Tailwind config, or eslint config. Covers source locations, generated output boundaries, and the frontend build and lint workflow."
name: "Frontend UI Guidelines"
applyTo: "ui/src/**, ui/public/**, ui/*.js, ui/*.json, ui/*.md"
---

# Frontend UI Guidelines

- Frontend source in this repository lives in `ui/src` and static assets live in `ui/public`. Treat `ui/dist` as generated output from the build; regenerate it instead of hand-editing built files.
- Put reusable Svelte components in `ui/src/lib/components` and page entrypoints in `ui/src/pages`. Follow the existing page-based structure rather than introducing a new app layout.
- Use the commands documented in [ui/README.md](../../ui/README.md): `npm install` to set up, `npm run watch` during development, `npm run build` for production assets, and `npm run lint` before finishing.
- Preserve the existing stack and patterns in `ui/package.json`, `ui/vite.config.js`, and `ui/eslint.config.js`. Prefer extending current Svelte and Vite conventions over adding parallel tooling.
- The optional `frontend` profile in [docker-compose.dev.yml](../../docker-compose.dev.yml) points to an external `../iris-frontend` checkout. Unless the task explicitly targets that external repo, make frontend changes in this workspace's `ui` application.