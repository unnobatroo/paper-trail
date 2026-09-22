# Paper Trail

**From policy text to implementation evidence.**

Paper Trail reads the real Józsefváros climate strategy PDF, extracts
candidate commitments, searches official municipal sources for
implementation evidence, and lets a human decide what enters the record:

> What did the district say it would do, what measurable targets exist,
> what implementation evidence was found, and what is still missing?

Nothing reaches the tracker without a human clicking **Confirm**. It does
not estimate budgets, infer completion, or judge whether a policy is good.

**Live demo: https://paper-trail.streamlit.app**

## Workflow

```text
strategy PDF
→ extract candidate commitments (page + verbatim excerpt required)
→ human reviews them (Confirm / Edit / Reject)
→ search official sources: jozsefvaros.hu, rev8.hu, budapest.hu
→ chunk documents (~2400 chars) → embed → top-20 cosine → rerank → top-5
→ human reviews proposed links
→ confirmed records appear in the Paper Trail, with explicit gaps
```

## Run

```bash
uv sync
uv run streamlit run app.py
```

Click **Read the strategy** in the sidebar, then walk the three steps:
**Check commitments → Find evidence → Paper trail**.

Hungarian source text can be shown with an automatic English translation
(sidebar toggle) — labelled machine translation, never an official
document.

### First run

- With `JINA_API_KEY` set (see config) the app uses hosted inference —
  no model downloads, first search just calls the API.
- Without it, the first search downloads ~2 GB of local models into
  `data/models/` (the app says so) and embedding takes minutes on CPU.
  Fetched pages and embeddings are cached under `data/processed/fetched/`.

Reset state without touching caches:

```bash
uv run python scripts/reset_demo_state.py
```

Works for both backends: archives the SQLite file, or clears the Supabase
rows when `SUPABASE_URL`/`SUPABASE_KEY` are set.

## Deploy

The app deploys on Streamlit Community Cloud straight from this repo:
pick `unnobatroo/paper-trail`, branch `main`, file `app.py`, then paste
`.streamlit/secrets.toml` (template: `secrets.example.toml`) into the
app's Secrets. `requirements.txt` covers the build; a `Dockerfile` is
included for container hosts. Cloud secrets become env vars automatically.

## Configuration

| env var | default | meaning |
|---|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` | unset | set both → Supabase/Postgres backend instead of SQLite (run `supabase/migrations/001_schema.sql` once; use the service_role key) |
| `JINA_API_KEY` | unset | hosted inference — with `PAPER_TRAIL_EMBED_MODEL=jina` + `PAPER_TRAIL_RERANKER=jina` no models are downloaded |
| `HF_TOKEN` | unset | enables HU→EN machine translation in the UI |
| `PAPER_TRAIL_DB` | `data/processed/paper_trail.db` | SQLite path (local backend) |
| `PAPER_TRAIL_EMBED_MODEL` | `intfloat/multilingual-e5-large` | embedder (`jina`, `hashing` = offline stub, or a fastembed model) |
| `PAPER_TRAIL_RERANKER` | `BAAI/bge-reranker-v2-m3` | cross-encoder (`jina`, `none`, or a local model) |
| `PAPER_TRAIL_RERANK_K` | `20` | chunks sent to the reranker |
| `PAPER_TRAIL_SEARCH` | `ddgs` | `ddgs` (DuckDuckGo) or `fixture` (offline replay) |
| `PAPER_TRAIL_MODEL_CACHE` | `data/models` | local model files |
| `PAPER_TRAIL_MAX_DOC_CHARS` | `4000000` | emergency document bound — truncates and warns, never silently |
| `PAPER_TRAIL_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | unset | optional OpenAI-compatible extraction endpoint |

Keys can live in a gitignored `.env` at the repo root (see `.env.example`).

## Honesty rules

- no claim without a page number and a verbatim excerpt (re-verified
  against the page text)
- money stays typed — estimated cost / approved allocation / reported
  expenditure — never merged, never estimated; only figures near the
  matched excerpt are kept
- source status comes from cue phrases quoted from the matched excerpt
  (announced → completed / budget / background / unclear), never from dates
- missing evidence shows as a gap, not a score
- English text is machine translation, always labelled as such

## Extraction

`RuleBasedExtractor` (default, offline) parses this document's own
structure — goal headers, numbered measure cards, target sentences inside
the action-plan region. It is tuned to this one strategy, not a general
parser; the review screen exists because it occasionally over-fires on
background statistics. An optional `LLMExtractor` posts page windows to
any OpenAI-compatible endpoint with structured output and verbatim
excerpt verification.

## Retrieval (frozen for the MVP)

Full-document chunking + e5-large + top-20 cosine + BGE cross-encoder
rerank beat the old windowed baseline ~2.7× on recall@5 in our small
benchmark; a learned relationship classifier was evaluated and rejected —
the heuristic rules stay. Raw numbers live in `experiments/results/`.

The benchmark (`data/benchmark/`) is 8 commitments × 91 real passages ×
89 hand-labelled pairs (`relevance` 0–2, `relationship` uses the app's
own enum, every label has a note). Splits are by source document — a test
passage never has near-copies in train. Regenerate with
`experiments/build_benchmark.py`; the app does not depend on it.
Reviewed decisions in the app export as labelled rows for future data:
`experiments/export_review_data.py` (SQLite backend).

Heavy runs go on a rented GPU (Vast.ai): sync repo, run on a stock
pytorch image, pull the DB back, destroy the instance —
`experiments/gpu_warm_e2e.py` shows the pattern.

## Layout

```text
app.py                     entry point / wiring
src/paper_trail/
  domain/                  enums + Pydantic models
  ml/                      embeddings, entity/money/status parsing,
                           extraction, matching, rerank
  sources/                 PDF reader, allowlisted search, fetch,
                           official document registry
  services/                ingestion, evidence discovery, review,
                           metrics, translation
  repositories/            SQLite + Supabase data access
  presentation/            three Streamlit screens
tests/                     offline: fixture search, hashing embeddings
data/source_documents/     the strategy PDF
scripts/reset_demo_state.py
supabase/migrations/       Postgres schema for the cloud backend
```

## Tests

```bash
uv run pytest          # all offline
```
