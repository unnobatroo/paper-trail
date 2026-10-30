"""erase machine output and queue the pipeline again, postgres only

  reset                    dry run: counts what would go
  reset --yes              erase generated rows, keep human decisions
  reset --cache --yes      also drop fetched pages/chunks (needed after an embed model change)
  reset --everything --yes empty every table, decisions too
  rerun                    queue find_evidence for every commitment
  rerun --ingest strategy.pdf --title T --publisher P   extract a document again first
  source add URL --publisher P [--title T] [--jurisdiction J]   register an official source
  source list              the registry, with each source's asset owner
  profile import FILE      load a language profile (json) into the db
  profile export CODE      print one as json
  notes import FILE.jsonl  plain-english notes + ai suggestions, one json Note per line
  notes generate [--links] [--redo] [--limit N]   our llm writes them (goethe extraction phase)

run as python -m paper_trail.maintenance <command>

reset/rerun/source need the owner dsn in PAPER_TRAIL_DATABASE_URL (api/worker roles
can't delete). profile and notes also work on the local sqlite file when that's unset
"""

import argparse
import json
import os
import sys
from pathlib import Path

from .domain.enums import Jurisdiction
from .domain.models import OfficialSource
from .repositories.postgres.db import connect
from .repositories.postgres.jobs import PostgresJobRunner
from .repositories.store import EvidenceRepository, PolicyRepository


def _gone(evidence_id: str) -> str:
    # evidence nothing points at after links/budgets are cleared = generated, goes
    return (f"NOT EXISTS (SELECT 1 FROM links l WHERE l.evidence_id = {evidence_id})"
            f" AND NOT EXISTS (SELECT 1 FROM budgets b WHERE b.evidence_id = {evidence_id})")


# anything a person decided (or that hangs off it) isn't "generated"
# not exists, not "not in": one null in the subquery and not in matches nothing
# budgets without evidence come from the doc itself, they stay
GENERATED = [
    ("budgets", "DELETE FROM budgets b WHERE b.evidence_id IS NOT NULL AND NOT EXISTS"
                " (SELECT 1 FROM links l WHERE l.evidence_id = b.evidence_id"
                " AND l.review_status <> 'unreviewed')"),
    ("links", "DELETE FROM links WHERE review_status = 'unreviewed'"),
    # artifacts hang off evidence, unhook them from the passages about to go
    ("artifact_evidence", "DELETE FROM artifact_evidence ae WHERE " + _gone("ae.evidence_id")),
    ("implementation_artifacts", "UPDATE implementation_artifacts SET status = 'active',"
                                 " status_evidence_id = NULL, updated_at = now()"
                                 " WHERE status_evidence_id IS NOT NULL AND "
                                 + _gone("status_evidence_id")),
    # ...then re-escalate from what's left, same rule as link_artifact
    ("implementation_artifacts", "UPDATE implementation_artifacts a SET status = s.status,"
                                 " status_evidence_id = s.evidence_id FROM"
                                 " (SELECT DISTINCT ON (ae.artifact_id) ae.artifact_id, e.id"
                                 " evidence_id, CASE e.polarity WHEN 'termination' THEN"
                                 " 'terminated' ELSE 'amended' END status FROM artifact_evidence"
                                 " ae JOIN evidence e ON e.id = ae.evidence_id WHERE e.polarity"
                                 " IN ('amendment', 'termination') ORDER BY ae.artifact_id,"
                                 " e.polarity = 'termination' DESC, e.id) s"
                                 " WHERE a.id = s.artifact_id AND a.status_evidence_id IS NULL"),
    ("implementation_artifacts", "DELETE FROM implementation_artifacts a WHERE NOT EXISTS"
                                 " (SELECT 1 FROM artifact_evidence ae"
                                 " WHERE ae.artifact_id = a.id)"),
    ("evidence", "DELETE FROM evidence e WHERE " + _gone("e.id")),
    ("candidates", "DELETE FROM candidates c WHERE c.review_status = 'unreviewed'"
                   " AND NOT EXISTS (SELECT 1 FROM commitments m WHERE m.candidate_id = c.id)"),
    ("jobs", "DELETE FROM jobs WHERE status NOT IN ('queued', 'running')"),
    # notes have no fk (two subject tables), drop the ones whose item just went
    ("notes", "DELETE FROM notes n WHERE (n.subject_kind = 'candidate' AND NOT EXISTS"
              " (SELECT 1 FROM candidates c WHERE c.id = n.subject_id)) OR"
              " (n.subject_kind = 'link' AND NOT EXISTS"
              " (SELECT 1 FROM links l WHERE l.id = n.subject_id))"),
]
CACHE = [("chunks", "DELETE FROM chunks"), ("pages", "DELETE FROM pages")]
# children first, fks don't cascade
EVERYTHING = ["notes", "budgets", "links", "artifact_evidence", "implementation_artifacts",
              "evidence", "commitments", "candidates", "documents", "chunks", "pages",
              "official_sources", "jobs"]


def reset(url: str, *, cache: bool, everything: bool, yes: bool) -> dict[str, int]:
    steps = ([(t, f"DELETE FROM {t}") for t in EVERYTHING] if everything
             else GENERATED + (CACHE if cache else []))
    counts = {}
    with connect(url) as conn:
        # one transaction: dry run rolls back, real run is all or nothing
        for table, sql in steps:
            counts[table] = counts.get(table, 0) + conn.execute(sql).rowcount
        if yes:
            conn.commit()
        else:
            conn.rollback()
    return counts


def rerun(url: str, ingest: list[str], title: str, publisher: str, source_url: str) -> list:
    jobs = PostgresJobRunner(url)
    queued = [jobs.submit("ingest", {"name": name, "title": title,
                                     "publisher": publisher, "url": source_url})
              for name in ingest]
    with connect(url) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM commitments ORDER BY id")]
    queued += [jobs.submit("find_evidence", {"commitment_id": i}) for i in ids]
    return queued


def profile(args) -> int:
    from .infrastructure.settings import load
    from .ml.lang import LanguageProfile
    settings = load()
    repo = PolicyRepository(settings.database_url or settings.db_path)
    if args.profile_cmd == "import":
        # round-trip through the dataclass so a typo'd field or enum fails here, not at boot
        data = LanguageProfile.from_dict(json.loads(args.file.read_text())).to_dict()
        repo.put_language_profile(data["code"], data)
        print(f"imported {data['code']}")
        return 0
    data = repo.language_profile(args.code)
    if data is None:
        print(f"no profile {args.code}", file=sys.stderr)
        return 1
    print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


def notes(args) -> int:
    from .domain.models import Note
    from .infrastructure.settings import load
    settings = load()
    url = settings.database_url or settings.db_path
    repo = PolicyRepository(url)
    if args.notes_cmd == "import":
        # validate everything first, a bad line halfway shouldn't leave half an import
        rows = [Note.model_validate_json(line)
                for line in args.file.read_text().splitlines() if line.strip()]
    else:
        rows = _generate_notes(settings, repo, EvidenceRepository(url), args)
    for note in rows:
        repo.put_note(note)
    print(f"{args.notes_cmd}: {len(rows)} notes written")
    return 0


def _generate_notes(settings, repo, evidence, args) -> list:
    """our own llm writes them, needs goethe in the extraction phase"""
    from .bootstrap import load_profile
    from .domain.enums import ReviewStatus
    from .ml.client import model_client
    from .ml.notes import NoteWriter, candidate_item, link_item
    if not settings.llm_configured:
        raise SystemExit("PAPER_TRAIL_LLM_BASE_URL / _MODEL not set, nothing to write notes with")
    profile = load_profile(repo, settings.language)
    items = []
    cands = repo.candidates(ReviewStatus.UNREVIEWED)
    have = set() if args.redo else set(repo.notes("candidate", [c.id for c in cands]))
    items += [("candidate", c.id, candidate_item(c)) for c in cands if c.id not in have]
    if args.links:
        links = evidence.links(ReviewStatus.UNREVIEWED)
        have = set() if args.redo else set(repo.notes("link", [l.id for l in links]))
        todo = [l for l in links if l.id not in have]
        ev = evidence.evidence_many([l.evidence_id for l in todo])
        coms = {c.id: c for c in repo.commitments()}
        items += [("link", l.id, link_item(coms[l.commitment_id], ev[l.evidence_id]))
                  for l in todo if l.evidence_id in ev and l.commitment_id in coms]
    items = items[:args.limit] if args.limit else items
    print(f"writing {len(items)} notes with {settings.llm_model}", file=sys.stderr)
    writer = NoteWriter(model_client(settings.llm_base_url, settings.llm_api_key),
                        settings.llm_model, profile, settings.llm_concurrency)
    return writer.write(items)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset", help="erase generated rows (dry run without --yes)")
    r.add_argument("--cache", action="store_true", help="also drop fetched pages and chunks")
    r.add_argument("--everything", action="store_true",
                   help="empty every table, human decisions included")
    r.add_argument("--yes", action="store_true", help="actually delete")
    q = sub.add_parser("rerun", help="queue the pipeline for the worker")
    q.add_argument("--ingest", action="append", default=[], metavar="FILE",
                   help="document store filename to extract again, repeatable")
    q.add_argument("--title", default="")
    q.add_argument("--publisher", default="")
    q.add_argument("--url", default="")
    s = sub.add_parser("source", help="the official_sources registry, the only place "
                                      "source domains and asset-owner routing live")
    s_sub = s.add_subparsers(dest="source_cmd", required=True)
    add = s_sub.add_parser("add", help="add or update a source")
    add.add_argument("source_url")
    add.add_argument("--publisher", required=True)
    add.add_argument("--title", default="")
    add.add_argument("--jurisdiction", choices=[j.value for j in Jurisdiction],
                     help="asset owner whose commitments search this source; omit for the "
                          "municipality's own sources, searched for every commitment")
    s_sub.add_parser("list", help="print the registry")
    pr = sub.add_parser("profile", help="language profiles, the rules' word lists")
    pr_sub = pr.add_subparsers(dest="profile_cmd", required=True)
    pr_sub.add_parser("import", help="load a profile json").add_argument("file", type=Path)
    pr_sub.add_parser("export", help="print a profile as json").add_argument("code")
    nt = sub.add_parser("notes", help="plain-english notes and ai suggestions")
    nt_sub = nt.add_subparsers(dest="notes_cmd", required=True)
    nt_sub.add_parser("import", help="load a jsonl of notes").add_argument("file", type=Path)
    gen = nt_sub.add_parser("generate", help="our llm writes notes for unreviewed items")
    gen.add_argument("--links", action="store_true", help="evidence links too")
    gen.add_argument("--redo", action="store_true", help="rewrite existing notes")
    gen.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    if args.cmd == "profile":
        return profile(args)
    if args.cmd == "notes":
        return notes(args)
    url = os.environ.get("PAPER_TRAIL_DATABASE_URL")
    if not url:
        parser.error("PAPER_TRAIL_DATABASE_URL is not set")

    if args.cmd == "reset":
        counts = reset(url, cache=args.cache, everything=args.everything, yes=args.yes)
        for table, n in counts.items():
            print(f"{table:17} {n}")
        print("deleted" if args.yes else "dry run, nothing deleted: add --yes")
        return 0
    if args.cmd == "source":
        repo = EvidenceRepository(url)
        if args.source_cmd == "add":
            repo.upsert_official_source(OfficialSource(
                url=args.source_url, publisher=args.publisher, title=args.title,
                jurisdiction=Jurisdiction(args.jurisdiction) if args.jurisdiction else None))
        for src in repo.official_sources():
            print(f"{(src.jurisdiction or 'all commitments'):26} {src.publisher:30} {src.url}")
        return 0
    if args.ingest and not (args.title and args.publisher):
        parser.error("--ingest needs --title and --publisher")
    queued = rerun(url, args.ingest, args.title, args.publisher, args.url)
    # submit reuses a waiting job with the same payload, reruns don't pile up
    print(f"{len(queued)} jobs queued or already waiting, the worker picks them up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
