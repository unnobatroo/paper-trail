# Claude Code notes

Project rules live in `AGENTS.md`; under `web/` also read `web/AGENTS.md`. They are not repeated here.

## IDE tools first (PyCharm MCP `pycharm`, always pass `projectPath`)

- `search_symbol`: find classes/functions before grepping
- `apply_patch`: edit files
- `rename_refactoring`: rename symbols across the project
- `get_file_problems`: IDE inspections on a file after editing
- `execute_run_configuration`: run tests from an IDE run config. Unverified: whether a pytest run configuration exists here; check with `get_run_configurations`, else use the commands below

Fall back to `rg` or the shell if the server is disconnected.

## Commands

- tests: `make test` (`uv run pytest -q` + `cd web && npm test`)
- full check, same as CI: `make check` (tests, `uvx pre-commit run --all-files`, `npm run lint`, `npm run build`)
- format: `make fmt`

## Rules

- smallest change that works, no unrelated refactors
- don't touch `.env` or secrets
- don't commit or push unless asked
- run the narrowest useful check first; `make test` / `make check` before calling work done
- final report: what changed, what you found, how you verified, open issues
