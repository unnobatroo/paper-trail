"""Run find_evidence for every confirmed commitment on a GPU box.

Uses the fixture search provider (replays locally-collected DDG hits) and
the pre-fetched page cache, so the only network it needs is the one-time
model download. Writes links into the same SQLite DB the app uses —
sync data/processed/ back afterwards.
"""

import os
import sys
import time

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pathlib import Path

from paper_trail.infrastructure.database import connect
from paper_trail.repositories.store import PolicyRepository, EvidenceRepository
from paper_trail.services.evidence_service import EvidenceService
from paper_trail.ml.embeddings import SentenceTransformerProvider
from paper_trail.ml.rerank import get_reranker
from paper_trail.sources.web_search import get_search_provider

ROOT = Path(__file__).resolve().parents[1]

conn = connect(ROOT / "data/processed/paper_trail.db")
policy, evidence = PolicyRepository(conn), EvidenceRepository(conn)
svc = EvidenceService(
    evidence, get_search_provider("fixture", ROOT / "data/fixtures"),
    SentenceTransformerProvider("intfloat/multilingual-e5-large"),
    cache_dir=ROOT / "data/processed/fetched",
    reranker=get_reranker("BAAI/bge-reranker-v2-m3"),
)
prog = lambda m: print("  …", m, flush=True)
for com in policy.commitments():
    t0 = time.time()
    print(f"=== {com.id} [{com.kind.value}] {com.title[:80]}", flush=True)
    links = svc.find_evidence(com, progress=prog)
    for w in svc.warnings:
        print("  WARN:", w, flush=True)
    for l in links:
        ev = evidence.evidence(l.evidence_id)
        print(f"  link {l.id}: {ev.title[:70]}")
        print(f"      {ev.url}")
        print(f"      rel={l.suggested_relationship.value} "
              f"status={ev.status_hint.value} "
              f"sim={l.features.semantic_similarity:.3f}")
        print(f"      reasons: {'; '.join(l.reasons)}")
        for b in evidence.budgets_for_evidence(ev.id):
            print(f"      money: {b.amount_huf} ({b.kind.value}) "
                  f"fy={b.fiscal_year}")
    print(f"  → {len(links)} links in {time.time()-t0:.0f}s", flush=True)
print("ALL DONE", flush=True)
