# Agent rules

- **Reuse before inventing.** Before adding a component, helper, or
  abstraction, look for the existing one: `web/src/components/` and
  `web/src/components/ui/` (Base UI/shadcn primitives), `web/src/lib/`,
  `src/paper_trail/` services/repositories/ml. Extend what's there rather
  than building a parallel version.
- **Prefer established OSS over bespoke code.** If a problem is already
  solved by a dependency in `package.json`/`pyproject.toml` (or a small,
  well-maintained addition), use it — don't hand-roll equivalents.
  Deliberate exceptions exist (e.g. `ml/entities.py` parses deterministically
  on purpose, `CONTRIBUTING.md` explains why); match them, don't repeat them.
- Keep diffs focused; match the conventions of the file you're in.
- `web/AGENTS.md` applies under `web/` — read the version-matched Next.js
  docs in `node_modules/next/dist/docs/` before Next.js-specific changes.
- Checks: `make check` runs what CI gates on (pytest, the pre-commit
  hooks: ruff, uv-lock, then web lint/test/build). `uvx
  pre-commit install` runs the hooks on every commit. Database changes go
  in a new numbered file under `db/sql/` plus an Alembic revision, never an edit.
- **Docs live in the GitHub wiki only** (`unnobatroo/paper-trail.wiki`): update it
  with behaviour changes, don't add markdown docs to the repo. Deployment data
  (sources, domains, places) belongs in the database or untracked env files.
- **Frontend API types are generated**: after a backend model/endpoint change run
  `uv run python scripts/ops/export_openapi.py && (cd web && npm run gen:api)`.
