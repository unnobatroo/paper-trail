# Paper Trail

**From policy text to implementation evidence.**

Paper Trail reads one official Józsefváros climate strategy PDF, extracts
candidate commitments, searches official municipal sources for
implementation evidence, and lets a human decide what becomes part of the
record. It answers one question:

> What did the district say it would do, what measurable targets exist,
> what implementation evidence was found, and what is still missing?

It is not a planner, not an AI researcher, not a GIS platform. It does not
estimate budgets, infer completion, or judge whether a policy is good.
Nothing reaches the tracker without a human clicking **Confirm**.

## Workflow

```text
strategy PDF
→ extract candidate commitments (page + verbatim excerpt required)
→ human reviews them (Confirm / Edit / Reject)
→ search official sources: jozsefvaros.hu, rev8.hu, budapest.hu
→ chunk full documents (~2400 chars), embed once, cache
→ top ~20 chunks by cosine → cross-encoder rerank
→ best chunk per source → top ~5 proposed links
→ human reviews links (Confirm / Reject / Change type)
→ confirmed records appear in the Paper Trail, with explicit gaps
```

## Run

```bash
uv sync
uv run streamlit run app.py
```

Click **Read the strategy** in the sidebar, then walk the three steps:
**Check commitments → Find evidence → Paper trail**.

## Demo

The intended demo is the app itself, start to finish in a few minutes:

```text
Strategy        — "Read the strategy" reads the real Józsefváros climate PDF
→ Check commits — review the extracted commitments, confirm the ones that matter
→ Find evidence — Paper Trail searches official municipal sources and proposes links
→ Confirm match — inspect what each source actually proves, accept or reject
→ Paper trail   — every confirmed claim traced back to its official source,
                  with the gaps shown honestly
```

The demo works on a warm cache (models + fetched pages under `data/`).
On a cold machine the first search downloads ~2 GB of models — plan for
that or run `scripts/reset_demo_state.py` beforehand to show the full
flow from an empty state.

The first evidence search downloads ~2 GB of language models into
`data/models/` (the app says so) and embedding a full report takes a few
minutes on CPU. Fetched pages and chunk embeddings are cached under
`data/processed/fetched/` — later searches are fast.

Reset everything but the caches:

```bash
uv run python scripts/reset_demo_state.py   # archives the DB, keeps models/pages
```

## Configuration

| env var | default | meaning |
|---|---|---|
| `PAPER_TRAIL_DB` | `data/processed/paper_trail.db` | SQLite path |
| `PAPER_TRAIL_EMBED_MODEL` | `intfloat/multilingual-e5-large` | embedder (`hashing` = offline stub) |
| `PAPER_TRAIL_RERANKER` | `BAAI/bge-reranker-v2-m3` | cross-encoder (`none` disables; jina ONNX fallback when sentence-transformers absent) |
| `PAPER_TRAIL_RERANK_K` | `20` | chunks sent to the reranker |
| `PAPER_TRAIL_MAX_DOC_CHARS` | `4000000` | emergency document bound — truncates AND warns, never silently |
| `PAPER_TRAIL_SEARCH` | `ddgs` | `ddgs` (DuckDuckGo) or `fixture` (offline JSONL replay) |
| `PAPER_TRAIL_MODEL_CACHE` | `data/models` | downloaded model files |
| `PAPER_TRAIL_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | unset | optional OpenAI-compatible extraction endpoint |

`HF_HUB_DISABLE_XET=1` is set inside the providers: hf-xet's shared blob
cache puts a model's external ONNX data outside the model directory, which
onnxruntime refuses to load.

## Honesty rules

- no claim without a page number and a verbatim excerpt (re-verified
  against the page text)
- money stays typed — estimated cost / approved allocation / reported
  expenditure — never merged, never estimated; only figures near the
  matched excerpt are kept
- source status comes from cue phrases quoted from the matched excerpt
  (announced → completed / budget / background / unclear), never inferred
  from dates
- missing evidence shows as a gap, not a score

## Extraction

`RuleBasedExtractor` (default, offline) parses this document's own
structure — goal headers, numbered measure cards, target sentences inside
the action-plan region. It is tuned to this one strategy and deliberately
not a general parser; target candidates still over-fire occasionally on
background statistics, which is why the review screen exists. An optional
`LLMExtractor` posts page windows to any OpenAI-compatible endpoint with
structured output and verbatim excerpt verification.

## Retrieval (frozen for the MVP)

Benchmark on 8 commitments × 38 chunks of fetched official text (small —
do not read it as real-world accuracy): full-document chunking at ~2400
chars + e5-large embeddings + top-20 cosine + cross-encoder rerank beat
the old windowed baseline ~2.7× on recall@5. BGE-reranker-v2-m3 was chosen
over jina-v2-multilingual on source-level metrics (src r@5 0.749 vs 0.702)
and 2.4× speed. Learned relationship classification was evaluated and
rejected — the heuristic rules stay; the dataset can't support a learned
classifier. Raw numbers live in `experiments/results/`.

## Experiments

`experiments/` holds the reproducible benchmark harness — optional; the
app does not depend on it. `data/benchmark/` has 8 commitments × 91 real
passages × 89 curated labels, split by source document. Reviewed decisions
in the app export as labelled rows for future training data:

```bash
uv run python experiments/export_review_data.py
```

Heavy runs go on a rented GPU (Vast.ai, ~$0.17/hr RTX 3090): sync the
repo, `pip install sentence-transformers trafilatura pypdf pydantic
requests` on a stock pytorch image, run, pull the DB back, destroy the
instance. See `experiments/gpu_warm_e2e.py` for the pattern.

## Layout

```text
app.py                     entry point / wiring
src/paper_trail/
  domain/                  enums + Pydantic models
  ml/                      embeddings, entity/money/status parsing,
                           extraction, matching, rerank
  sources/                 PDF reader, allowlisted search, fetch,
                           official document registry
  services/                ingestion, evidence discovery, review, metrics
  repositories/            SQLite data access
  presentation/            three Streamlit screens
tests/                     offline: fixture search, hashing embeddings
data/source_documents/     the strategy PDF + benchmark input PDF
scripts/reset_demo_state.py
```

## Tests

```bash
uv run pytest          # all offline
```
