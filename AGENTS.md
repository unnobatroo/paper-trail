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
