# Contributing to Paper Trail

Thanks for wanting to help. Before you write any code, there's one thing
to understand about this project: it exists to be honest about what a
city *didn't* do. Everything else is negotiable — that isn't.

## The rules that aren't negotiable

Paper Trail's whole value is that it never pretends. If a change weakens
any of these, it won't get merged:

- **A human always has the last word.** The pipeline can suggest all it
  wants, but nothing becomes part of the record until someone reviews
  and accepts it. No auto-acceptance, ever.
- **Every claim can be traced.** Page number, verbatim excerpt, source
  URL. If the source can't be quoted, it doesn't count.
- **Money stays as written.** An estimated cost is not an approved
  budget is not actual spending. We never merge them and we never make
  numbers up.
- **Status comes from what the text says.** "Completed" means the source
  literally says so — not that the deadline passed.
- **Tests run offline.** No keys, no network, no excuses. The suite is
  how we keep all of the above true.

If your idea sits awkwardly with one of these, open an issue first so we
can talk about it — there might be a way to do both.

## Getting set up

```bash
uv sync
uv run pytest        # ~33 tests, all offline, should pass in seconds
```

The [Development](https://github.com/unnobatroo/paper-trail/wiki/Development)
wiki page covers the layout and the conventions in more depth.

## How changes land

1. For anything beyond a typo, open an issue describing the problem
   first — it's much easier to agree on direction before there's code.
2. Branch from `main`, keep the diff focused. Unrelated cleanups get
   asked to be their own PR.
3. Bug fixes come with a failing test that then passes; features extend
   existing test files before adding new ones.
4. New backends go behind the existing interfaces (`EmbeddingProvider`,
   `SearchProvider`, and friends) rather than being wired into the
   services directly.
5. `uv run pytest` has to be green. If you added a dependency, run
   `uv lock` and regenerate `requirements.txt`:
   `uv export --format requirements-txt --no-hashes --no-dev --no-group ml`.

## Good places to start

- Label more passages in `data/benchmark/` — better labels make every
  tuning decision more honest.
- Improve organisation, place, or money extraction in `ml/entities.py`
  (with tests, please).
- Bring in strategy documents from other Hungarian districts as
  fixtures — Józsefváros shouldn't be the only one under a microscope.
- Fix or clarify anything in the
  [wiki](https://github.com/unnobatroo/paper-trail/wiki) — you can edit
  it directly.

## Style

Match the file you're in. The codebase is compact and comments explain
*why* something is done, not what the line does — keep that balance.
Code and comments are in English; Hungarian stays in fixtures and domain
strings. And please don't pull in a new dependency for something a few
lines of code can do.

By contributing, you agree your work is licensed under the project's
[GPL-3.0 license](LICENSE).
