# Agent rules

- **Reuse before inventing.** Before adding a component, helper, or
  abstraction, look for the existing one in `src/paper_trail/`
  (services/repositories/ml, the nicegui ui in `ui/`). Extend what's there rather
  than building a parallel version.
- **Prefer established OSS over bespoke code.** If a problem is already
  solved by a dependency in `pyproject.toml` (or a small,
  well-maintained addition), use it — don't hand-roll equivalents.
  Deliberate exceptions exist (e.g. `ml/entities.py` parses money with regexes
  on purpose, exact and checkable); match them, don't repeat them.
- Keep diffs focused; match the conventions of the file you're in.
- Checks: `make check` runs what CI gates on (pytest, the pre-commit
  hooks: ruff, uv-lock). `uvx
  pre-commit install` runs the hooks on every commit. Database changes go
  in a new numbered file under `db/sql/` plus an Alembic revision, never an edit.
- **Docs live in the GitHub wiki only** (`unnobatroo/paper-trail.wiki`): update it
  with behaviour changes, don't add markdown docs to the repo. Deployment data
  (sources, domains, places) belongs in the database or untracked env files.
- **The ui is python** (`src/paper_trail/ui/`, NiceGUI on the api's FastAPI app). It calls
  the api's router functions directly, so a rule lives in one place.
