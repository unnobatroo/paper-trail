## What & why

<!-- one short paragraph: the problem, the change, the link to the issue -->

## Checklist

- [ ] `uv run pytest` passes (all tests are offline — if yours needed
      network or keys, it probably doesn't belong in the suite)
- [ ] Honesty rules preserved: nothing auto-accepted, provenance intact,
      money typed, status quoted, MT labelled
- [ ] New providers implement the existing ABCs (no vendor logic in services)
- [ ] If dependencies changed: `uv lock` + `requirements.txt` regenerated
      (`uv export --format requirements-txt --no-hashes --no-dev --no-group ml`)
- [ ] Wiki docs updated if behaviour changed

## Test plan

<!-- how you verified it -->
