# Benchmark data

Small, hand-labelled benchmark built from the same official sources Paper
Trail searches. Regenerate with:

```bash
uv run python experiments/build_benchmark.py
```

## Files

| file | contents |
|---|---|
| `commitments.jsonl` | 8 real strategy measures (code, title, text, page) |
| `passages.jsonl` | 91 chunks (800 chars) from fetched official pages + PDF pages |
| `labels.jsonl` | 89 curated (commitment, passage) pairs |
| `raw/` | verbatim fetched page text — the source of `passages.jsonl` |

## Labels

`relevance`: 2 = real implementation evidence, 1 = related/partial/planned,
0 = not evidence. `relationship` uses the app's own `RelationshipType`
enum — no invented label set.

Every label has a `note` saying why. Hard negatives are labelled
explicitly where a page shares vocabulary with a commitment but is not
evidence for it (e.g. adopt-a-public-space vs courtyard greening).

## Known shape

- 8 commitments, ~11 positives each on average — heavily skewed toward
  C1 (street greening) because that is what the district actually did.
- C8 (district heating) has almost no positives: honest "no evidence" case.
- Unlabelled (commitment, passage) pairs count as relevance 0 in ranking
  metrics; the classifier's pair builder (`experiments/data.py`) adds
  in-source and sampled easy negatives explicitly.

## Splits

By source document, never by row — a test passage never has near-copies in
train. See `experiments/data.py` for the exact source lists. Some
commitments only have positives in one split; that is real, and reported.
