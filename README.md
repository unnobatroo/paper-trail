# Paper Trail

**From policy text to implementation evidence.**

[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-43%20passing-brightgreen)](tests/)

Paper Trail reads a real municipal climate strategy — the Józsefváros
(Budapest District VIII) strategy PDF — extracts the commitments it
contains, searches official municipal sources for evidence that each one
was actually implemented, and lets a **human reviewer** decide what enters
the permanent record:

> What did the district say it would do, what measurable targets exist,
> what implementation evidence was found, and what is still missing?

Nothing reaches the tracker without a person clicking **Confirm**. The
software proposes; the human disposes. It never estimates budgets, never
infers completion, and never judges whether a policy is good.

## Why this exists

Councils publish ambitious strategies; years later, nobody can tell which
promises became real. Implementation evidence does exist — procurement
notices, annual reports, budget resolutions — but it is scattered across
official websites in PDFs and news posts. Paper Trail automates the
tedious part (finding and ranking candidate evidence) while keeping the
accountable part (deciding what counts) human.

## The workflow

```text
strategy PDF
  → extract candidate commitments (page + verbatim excerpt required)
  → human reviews them (Confirm / Edit / Reject)
  → search official sources: jozsefvaros.hu, rev8.hu, budapest.hu
  → chunk documents → embed → top-20 semantic match → rerank → top-5
  → human reviews proposed links
  → confirmed records appear in the Paper Trail, with explicit gaps
```

Every record carries its provenance: the page number, the verbatim
excerpt, the source URL, the matched passage — so a claim can always be
traced back to the document that made it.

## Quickstart

```bash
git clone https://github.com/unnobatroo/paper-trail
cd paper-trail
uv sync                          # or: pip install -e .
uv run uvicorn paper_trail.api.app:app --app-dir src   # API → :8000
cd web && npm install && npm run dev                  # UI → :3000
```

The product UI is the Next.js app in [`web/`](web/) (React + shadcn/ui +
Tailwind, all open source). In the sidebar click **Read the strategy**,
then walk the three steps:
**Check commitments → Find evidence → Paper trail**.

Everything works offline except fetching pages from the official sites:
the test suite and the `fixture`/`hashing` providers need no keys and no
network. First real run downloads ~2 GB of local models (or set
`JINA_API_KEY` for hosted inference and download nothing).

The API is also usable directly — OpenAPI docs at
`http://localhost:8000/docs`.

## Documentation

Full docs with UML diagrams live in the
[project wiki](https://github.com/unnobatroo/paper-trail/wiki):

| Page | What it covers |
|---|---|
| [Architecture](https://github.com/unnobatroo/paper-trail/wiki/Architecture) | How the pieces fit — layers, interfaces, wiring |
| [Ranking Pipeline](https://github.com/unnobatroo/paper-trail/wiki/Ranking-Pipeline) | Search → fetch → chunk → embed → rerank → review, stage by stage |
| [Machine Learning](https://github.com/unnobatroo/paper-trail/wiki/Machine-Learning) | Models (embeddings, reranker, extraction, translation) and how to swap them |
| [Data Layer](https://github.com/unnobatroo/paper-trail/wiki/Data-Layer) | Schema, pgvector caches, storage buckets |
| [API Reference](https://github.com/unnobatroo/paper-trail/wiki/API-Reference) | Every REST endpoint |
| [Development](https://github.com/unnobatroo/paper-trail/wiki/Development) | Setup, tests, conventions |
| [Deployment](https://github.com/unnobatroo/paper-trail/wiki/Deployment) | Supabase, containers, Streamlit Cloud |

## Configuration

Everything has an offline-friendly default; a gitignored `.env` at the
repo root holds real values (see [.env.example](.env.example)):

| env var | default | meaning |
|---|---|---|
| `SUPABASE_URL` / `SUPABASE_KEY` | unset | set both → Postgres + pgvector + Storage instead of SQLite/files (run `supabase/migrations/` 001–003 once; use the service_role key) |
| `PAPER_TRAIL_STORAGE_BUCKET` | `source-documents` | Supabase Storage bucket holding source PDFs |
| `PAPER_TRAIL_API_ORIGINS` | `http://localhost:3000` | comma-separated CORS origins for the REST API |
| `JINA_API_KEY` | unset | hosted inference — with `PAPER_TRAIL_EMBED_MODEL=jina` + `PAPER_TRAIL_RERANKER=jina` no models are downloaded |
| `HF_TOKEN` | unset | enables HU→EN machine translation |
| `PAPER_TRAIL_DB` | `data/processed/paper_trail.db` | SQLite path (local backend) |
| `PAPER_TRAIL_EMBED_MODEL` | `intfloat/multilingual-e5-large` | embedder (`jina`, `hashing` = offline stub, or a fastembed model) |
| `PAPER_TRAIL_RERANKER` | `BAAI/bge-reranker-v2-m3` | cross-encoder (`jina`, `none`, or a local model) |
| `PAPER_TRAIL_RERANK_K` | `20` | chunks sent to the reranker |
| `PAPER_TRAIL_SEARCH` | `ddgs` | `ddgs` (DuckDuckGo) or `fixture` (offline replay) |
| `PAPER_TRAIL_MODEL_CACHE` | `data/models` | local model files |
| `PAPER_TRAIL_MAX_DOC_CHARS` | `4000000` | emergency document bound — truncates and warns, never silently |
| `PAPER_TRAIL_LLM_BASE_URL` / `_API_KEY` / `_MODEL` | unset | optional OpenAI-compatible extraction endpoint |

## The honesty rules

These are the product, not an afterthought:

- no claim without a page number and a verbatim excerpt (re-verified
  against the page text)
- money stays typed — estimated cost / approved allocation / reported
  expenditure — never merged, never estimated; only figures near the
  matched excerpt are kept
- source status comes from cue phrases quoted from the matched excerpt
  (announced → completed / budget / background / unclear), never from dates
- missing evidence shows as a gap, not a score
- English text is machine translation, always labelled as such

## Contributing

Bug reports and pull requests welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md). Security issues: see
[SECURITY.md](SECURITY.md). Everyone participating is covered by the
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

Copyright © 2026 Paper Trail contributors.

[GPL-3.0](LICENSE) — free to use, study, share and improve; derivatives
stay open.
