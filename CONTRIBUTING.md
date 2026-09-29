# Contributing to Paper Trail

Thanks for considering it. This file explains how to set up, what the
project's ground rules are, and how to get a change merged.

## Ground rules — read these first

Paper Trail exists to be trustworthy about what it *doesn't* know.
Changes are only accepted if they keep these invariants:

1. **Nothing is auto-accepted.** Every pipeline output stays
   `unreviewed` until a human acts.
2. **Every claim has provenance.** Page number + verbatim excerpt,
   re-verified against the source.
3. **Money stays typed and quoted.** No merging, no estimation.
4. **Status comes from quoted cues**, not from dates or intuition.
5. **Tests stay fully offline.** Stub providers, fixture search, tmp
   SQLite — see `tests/` for the pattern.
6. **Machine translation is labelled.** Always.

If your idea conflicts with one of these, open an issue to discuss it
before writing code.

## Setup

```bash
uv sync
uv run pytest          # must pass, fully offline
```

See the [wiki Development page](https://github.com/unnobatroo/paper-trail/wiki/Development)
for provider config, layout, and conventions.

## Making a change

1. **Open an issue first** for anything non-trivial — describe the
   problem, not just the fix you have in mind.
2. Fork, branch from `main`, keep diffs focused. Unrelated refactors get
   asked to be split.
3. Write a failing test for bug fixes; extend an existing test file for
   features before adding new files.
4. New providers go behind the existing ABCs — don't wire vendor-specific
   code into the services layer.
5. `uv run pytest` green; if you added a dependency, `uv lock` and
   regenerate `requirements.txt`
   (`uv export --format requirements-txt --no-hashes --no-dev --no-group ml`).
6. PRs: fill in the template, describe *why*, and link the issue.

## Good first contributions

- Widen the benchmark (`data/benchmark/`): label real passages.
- Improve entity/money recall in `ml/entities.py` — with tests.
- Hungarian strategy documents beyond Józsefváros as fixtures.
- Docs corrections — edit the
  [wiki](https://github.com/unnobatroo/paper-trail/wiki) directly.

## Style

- Follow the file you're editing — compact, commented only where the
  *why* isn't obvious (the codebase comments rationales, not mechanics).
- English code and comments; Hungarian only in domain fixtures/strings.
- No new dependencies for trivial functionality.

## License

By contributing you agree your work is licensed under the project's
[GPL-3.0 license](LICENSE).
