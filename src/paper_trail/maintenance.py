"""erase machine output, queue the pipeline again, manage deployment data

  python -m paper_trail.maintenance --help        every command, with its options

reset/rerun/source need the owner dsn in DATABASE_URL (api/worker roles
can't delete)
"""

import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from .domain.enums import Jurisdiction
from .domain.models import OfficialSource
from .repositories.postgres.db import connect
from .repositories.postgres.jobs import PostgresJobRunner
from .repositories.store import EvidenceRepository, PolicyRepository

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
source_app = typer.Typer(help="the official_sources registry: domains + asset-owner routing")
profile_app = typer.Typer(help="language profiles, the rules' word lists")
notes_app = typer.Typer(help="plain-english notes and ai suggestions on queue items")
app.add_typer(source_app, name="source")
app.add_typer(profile_app, name="profile")
app.add_typer(notes_app, name="notes")


def _owner_dsn() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise typer.BadParameter("DATABASE_URL is not set")
    return url


def _local_repo():
    from .infrastructure.settings import load
    settings = load()
    return settings, PolicyRepository(settings.database_url)


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


@app.command("reset")
def reset_cmd(
        cache: Annotated[bool, typer.Option(help="also drop fetched pages and chunks")] = False,
        everything: Annotated[bool, typer.Option(help="empty every table, decisions too")] = False,
        yes: Annotated[bool, typer.Option(help="actually delete")] = False) -> None:
    """erase generated rows, keep human decisions. a dry run without --yes"""
    for table, n in reset(_owner_dsn(), cache=cache, everything=everything, yes=yes).items():
        print(f"{table:24} {n}")
    print("deleted" if yes else "dry run, nothing deleted: add --yes")


@app.command()
def rerun(ingest: Annotated[list[str], typer.Option(help="document to extract again")] = [],  # noqa: B006
          title: str = "", publisher: str = "", url: str = "") -> None:
    """queue the pipeline for the worker: ingest documents again, then every evidence search"""
    if ingest and not (title and publisher):
        raise typer.BadParameter("--ingest needs --title and --publisher")
    dsn = _owner_dsn()
    jobs = PostgresJobRunner(dsn)
    queued = [jobs.submit("ingest", {"name": n, "title": title, "publisher": publisher,
                                     "url": url}) for n in ingest]
    with connect(dsn) as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM commitments ORDER BY id")]
    queued += [jobs.submit("find_evidence", {"commitment_id": i}) for i in ids]
    # submit reuses a waiting job with the same payload, reruns don't pile up
    print(f"{len(queued)} jobs queued or already waiting, the worker picks them up")


@source_app.command("add")
def source_add(source_url: str, publisher: Annotated[str, typer.Option()], title: str = "",
               jurisdiction: Annotated[Jurisdiction | None, typer.Option(
                   help="asset owner whose commitments search this source; omit for the "
                        "municipality's own")] = None) -> None:
    """add or update a source"""
    EvidenceRepository(_owner_dsn()).upsert_official_source(OfficialSource(
        url=source_url, publisher=publisher, title=title, jurisdiction=jurisdiction))
    source_list()


@source_app.command("list")
def source_list() -> None:
    """print the registry with each source's asset owner"""
    for src in EvidenceRepository(_owner_dsn()).official_sources():
        print(f"{(src.jurisdiction or 'all commitments'):26} {src.publisher:30} {src.url}")


@profile_app.command("import")
def profile_import(file: Path) -> None:
    """load a profile json into the db"""
    from .ml.lang import LanguageProfile
    # round-trip through the dataclass so a typo'd field or enum fails here, not at boot
    data = LanguageProfile.from_dict(json.loads(file.read_text())).to_dict()
    _local_repo()[1].put_language_profile(data["code"], data)
    print(f"imported {data['code']}")


@profile_app.command("export")
def profile_export(code: str) -> None:
    """print a profile as json"""
    data = _local_repo()[1].language_profile(code)
    if data is None:
        print(f"no profile {code}", file=sys.stderr)
        raise typer.Exit(1)
    print(json.dumps(data, ensure_ascii=False, indent=1))


@notes_app.command("import")
def notes_import(file: Path) -> None:
    """load a jsonl of notes, one Note per line"""
    from .domain.models import Note
    # validate everything first, a bad line halfway shouldn't leave half an import
    rows = [Note.model_validate_json(line)
            for line in file.read_text().splitlines() if line.strip()]
    repo = _local_repo()[1]
    for note in rows:
        repo.put_note(note)
    print(f"import: {len(rows)} notes written")


@notes_app.command("generate")
def notes_generate(links: Annotated[bool, typer.Option(help="evidence links too")] = False,
                   redo: Annotated[bool, typer.Option(help="rewrite existing notes")] = False,
                   limit: int = 0) -> None:
    """our llm writes notes for unreviewed items (goethe in the extraction phase)"""
    settings, repo = _local_repo()
    rows = _generate_notes(settings, repo,
                           EvidenceRepository(settings.database_url),
                           links, redo, limit)
    for note in rows:
        repo.put_note(note)
    print(f"generate: {len(rows)} notes written")


def _generate_notes(settings, repo, evidence, links: bool, redo: bool, limit: int) -> list:
    """our own llm writes them, needs goethe in the extraction phase"""
    from .bootstrap import load_profile
    from .domain.enums import ReviewStatus
    from .ml.client import model_client
    from .ml.notes import NoteWriter, candidate_item, link_item
    if not settings.llm_configured:
        raise SystemExit("LLM_BASE_URL / _MODEL not set, nothing to write notes with")
    profile = load_profile(repo, settings.language)
    items = []
    cands = repo.candidates(ReviewStatus.UNREVIEWED)
    have = set() if redo else set(repo.notes("candidate", [c.id for c in cands]))
    items += [("candidate", c.id, candidate_item(c)) for c in cands if c.id not in have]
    if links:
        links = evidence.links(ReviewStatus.UNREVIEWED)
        have = set() if redo else set(repo.notes("link", [l.id for l in links]))
        todo = [l for l in links if l.id not in have]
        ev = evidence.evidence_many([l.evidence_id for l in todo])
        coms = {c.id: c for c in repo.commitments()}
        items += [("link", l.id, link_item(coms[l.commitment_id], ev[l.evidence_id]))
                  for l in todo if l.evidence_id in ev and l.commitment_id in coms]
    items = items[:limit] if limit else items
    print(f"writing {len(items)} notes with {settings.llm_model}", file=sys.stderr)
    writer = NoteWriter(model_client(settings.llm_base_url, settings.llm_api_key),
                        settings.llm_model, profile, settings.llm_concurrency)
    return writer.write(items)


def main(argv: list[str] | None = None) -> int:
    """entry point, also callable from tests with an argv list"""
    try:
        app(argv, standalone_mode=False)
    except typer.Exit as exc:
        return exc.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
