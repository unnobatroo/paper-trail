# Claude Code notes

Project rules live in `AGENTS.md`. They are not repeated here.

## Commands

- tests: `make test` (`uv run pytest -q`)
- full check, same as CI: `make check` (tests + `uvx pre-commit run --all-files`)
- format: `make fmt`

## Rules

- smallest change that works, no unrelated refactors
- don't touch `.env` or secrets
- don't commit or push unless asked
- run the narrowest useful check first; `make test` / `make check` before calling work done
- final report: what changed, what you found, how you verified, open issues
