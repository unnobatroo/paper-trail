"""dry-run first, import public records into an empty migrated local database"""

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from psycopg import sql

from paper_trail.repositories.postgres.store import connect

TABLES = (
    "documents",
    "candidates",
    "commitments",
    "evidence",
    "links",
    "budgets",
    "official_sources",
)
RECORDS = TABLES[:-1]


def canonical(rows):
    return json.dumps(
        rows, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":")
    ).encode()


def checksum(rows):
    return hashlib.sha256(canonical(rows)).hexdigest()


def object_inventory(directory):
    objects = []
    if directory:
        root = Path(directory).resolve(strict=True)
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"source object symlink requires manual review: {path}")
            if path.is_file():
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                objects.append(
                    {
                        "path": str(path.relative_to(root)),
                        "bytes": path.stat().st_size,
                        "sha256": digest,
                    }
                )
    return objects


def source_rows(args):
    data = {}
    if args.source_sqlite:
        uri = Path(args.source_sqlite).resolve(strict=True).as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("BEGIN")
            for table in TABLES:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                data[table] = (
                    [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
                    if exists
                    else []
                )
    elif args.source_export:
        # jsonl per table from the read-only supabase export, pages/chunks are cache and refetched
        root = Path(args.source_export).resolve(strict=True)
        for table in TABLES:
            path = root / f"{table}.jsonl"
            lines = path.read_text().splitlines() if path.exists() else []
            rows = (json.loads(line) for line in lines if line)
            data[table] = sorted(rows, key=lambda r: r["id"])
    else:
        with connect(os.environ["PAPER_TRAIL_SOURCE_DATABASE_URL"]) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            for table in TABLES:
                exists = conn.execute(
                    "SELECT to_regclass(%s) present", ("public." + table,)
                ).fetchone()["present"]
                data[table] = (
                    conn.execute(
                        sql.SQL("SELECT * FROM {} ORDER BY id").format(sql.Identifier(table))
                    ).fetchall()
                    if exists
                    else []
                )
    for row in data["candidates"]:
        if row.get("excerpt_on_page") is not None:
            row["excerpt_on_page"] = bool(row["excerpt_on_page"])
    for row in data["budgets"]:
        row.setdefault("currency", "HUF")
        row.setdefault("amount_native", None)
        # migration 010: an approved allocation is the initial appropriation; a reported
        # expenditure stays reported until the final accounts confirm it
        if row.get("kind") == "approved_allocation":
            row["kind"] = "initial_appropriation"
    return data


def merge_duplicate_commitments(data):
    """fold commitments accepted twice for one candidate into the lowest id

    the old app let you accept a candidate more than once. per (kept commitment, url) one
    evidence row + one link survive: a decided link beats an unreviewed one, between
    decided ones the lowest commitment id wins (user's call, 2026-10-30)
    """
    groups = {}
    for row in data["commitments"]:
        if row.get("candidate_id") is not None:
            groups.setdefault(row["candidate_id"], []).append(row)
    keep = {}
    for rows in groups.values():
        rows.sort(key=lambda r: r["id"])
        first = rows[0]
        for dup in rows[1:]:
            same = {k: v for k, v in dup.items() if k not in ("id", "title")}
            if same != {k: v for k, v in first.items() if k not in ("id", "title")} or (
                dup["title"].strip() != first["title"].strip()
            ):
                raise ValueError(f"commitments {first['id']} and {dup['id']} differ; merge by hand")
            keep[dup["id"]] = first["id"]
    if not keep:
        return {}
    target = lambda cid: keep.get(cid, cid)  # noqa: E731
    for row in data["commitments"]:
        if row.get("parent_id") in keep:
            row["parent_id"] = keep[row["parent_id"]]
    data["commitments"] = [r for r in data["commitments"] if r["id"] not in keep]

    # evidence: the lowest commitment's row for a url survives, the rest point at it
    evidence_map, by_url = {}, {}
    for row in sorted(data["evidence"], key=lambda r: (target(r["commitment_id"]),
                                                       r["commitment_id"], r["id"])):
        key = (target(row["commitment_id"]), row["url"])
        evidence_map[row["id"]] = by_url.setdefault(key, row)["id"]
    survivors = {row["id"] for row in by_url.values()}
    original_commitment = {r["id"]: r["commitment_id"] for r in data["evidence"]}
    data["evidence"] = [r for r in data["evidence"] if r["id"] in survivors]
    for row in data["evidence"]:
        row["commitment_id"] = target(row["commitment_id"])

    chosen = {}
    for row in data["links"]:
        decided = row["review_status"] != "unreviewed"
        rank = (not decided, row["commitment_id"], row["id"])
        key = (target(row["commitment_id"]), evidence_map[row["evidence_id"]])
        if key not in chosen or rank < chosen[key][0]:
            chosen[key] = (rank, row)
    dropped_links = len(data["links"]) - len(chosen)
    data["links"] = sorted((row for _, row in chosen.values()), key=lambda r: r["id"])
    for (commitment_id, evidence_id), (_, row) in chosen.items():
        row["commitment_id"], row["evidence_id"] = commitment_id, evidence_id

    # the same observation was recorded once per duplicate, keep the lowest id
    seen, budgets = set(), []
    for row in sorted(data["budgets"], key=lambda r: r["id"]):
        if row.get("evidence_id") is not None:
            row["evidence_id"] = evidence_map[row["evidence_id"]]
        key = json.dumps({k: v for k, v in row.items() if k != "id"}, sort_keys=True,
                         default=str)
        if key not in seen:
            seen.add(key)
            budgets.append(row)
    dropped_budgets = len(data["budgets"]) - len(budgets)
    data["budgets"] = budgets
    return {
        "commitments_merged": {str(k): v for k, v in sorted(keep.items())},
        "evidence_dropped": len(original_commitment) - len(survivors),
        "links_dropped": dropped_links,
        "budgets_dropped": dropped_budgets,
    }


def migrate(args):
    data = source_rows(args)
    manifest = {"applied": False, "tables": {}, "objects": object_inventory(args.objects)}
    if args.merge_duplicate_commitments:
        manifest["merge"] = merge_duplicate_commitments(data)
    unverified = [r for r in data["candidates"] if r.get("excerpt_on_page") is not True]
    accepted_invalid = [r for r in unverified if r.get("review_status") == "accepted"]
    manifest["receipts"] = {
        "unverified": len(unverified),
        "accepted_unverified": len(accepted_invalid),
        "quarantined": 0,
    }
    if args.apply and accepted_invalid:
        raise ValueError(
            "accepted candidates have unverified receipts; manual reconciliation required"
        )
    if args.apply and unverified:
        if not args.quarantine_unverified:
            raise ValueError("unverified candidates require --quarantine-unverified before import")
        blocked = {r["id"] for r in unverified}
        if any(r.get("candidate_id") in blocked for r in data["commitments"]):
            raise ValueError(
                "a commitment references an unverified candidate; reconcile before import"
            )
        quarantine = Path(args.manifest).with_suffix(".unverified-candidates.json")
        quarantine.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical(unverified)
        if quarantine.exists():
            if quarantine.read_bytes() != payload:
                raise ValueError("quarantine artifact already exists with different source rows")
        else:
            with os.fdopen(
                os.open(quarantine, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as f:
                f.write(payload)
        data["candidates"] = [r for r in data["candidates"] if r["id"] not in blocked]
        manifest["receipts"]["quarantined"] = len(unverified)
        manifest["receipts"]["quarantine_path"] = str(quarantine)
        manifest["receipts"]["quarantine_sha256"] = hashlib.sha256(payload).hexdigest()
    with connect(os.environ["PAPER_TRAIL_TARGET_DATABASE_URL"]) as conn:
        for table in TABLES:
            columns = conn.execute(
                """SELECT column_name, data_type FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position""",
                (table,),
            ).fetchall()
            known = {c["column_name"] for c in columns}
            floats = {c["column_name"] for c in columns if c["data_type"] == "double precision"}
            if not known:
                raise ValueError(f"target table missing: {table}; run Alembic first")
            for row in data[table]:
                unknown = set(row) - known
                if unknown:
                    raise ValueError(f"{table}: unmapped source columns {sorted(unknown)}")
                # json has no float type for 10.0, postgres reads it back as a float
                for c in floats & set(row):
                    if isinstance(row[c], int) and not isinstance(row[c], bool):
                        row[c] = float(row[c])
            manifest["tables"][table] = {
                "rows": len(data[table]),
                "source_sha256": checksum(data[table]),
            }
        if args.apply:
            # this tool is an initial migration, never a merge into an existing public record
            for table in RECORDS:
                count = conn.execute(
                    sql.SQL("SELECT count(*) n FROM {}").format(sql.Identifier(table))
                ).fetchone()["n"]
                if count:
                    raise ValueError(f"target {table} is populated; refusing to overwrite records")
            conn.execute(
                "LOCK TABLE documents,candidates,commitments,evidence,links,budgets,"
                "official_sources IN ACCESS EXCLUSIVE MODE"
            )
            # recheck after locking to close the empty-target race
            for table in RECORDS:
                if conn.execute(
                    sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier(table))
                ).fetchone():
                    raise ValueError("target changed while acquiring migration lock")
            conn.execute("DELETE FROM official_sources")
            # parents are self-referential; defer only our import ordering, not integrity checks
            for table in TABLES:
                pending = list(data[table])
                inserted = set()
                while pending:
                    ready = [
                        r
                        for r in pending
                        if table != "commitments"
                        or r.get("parent_id") is None
                        or r["parent_id"] in inserted
                    ]
                    if not ready:
                        raise ValueError("commitment parent cycle or missing parent")
                    for row in ready:
                        columns = list(row)
                        query = sql.SQL("INSERT INTO {} ({}) OVERRIDING SYSTEM VALUE VALUES ({})")
                        query = query.format(
                            sql.Identifier(table),
                            sql.SQL(",").join(map(sql.Identifier, columns)),
                            sql.SQL(",").join(sql.Placeholder() for _ in columns),
                        )
                        conn.execute(query, tuple(row[c] for c in columns))
                        inserted.add(row["id"])
                        pending.remove(row)
                if data[table]:
                    # source rows may omit newly added columns; compare only preserved source fields
                    columns = list(data[table][0])
                    restored = conn.execute(
                        sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                            sql.SQL(",").join(map(sql.Identifier, columns)), sql.Identifier(table)
                        )
                    ).fetchall()
                    if checksum(restored) != checksum(data[table]):
                        raise ValueError(
                            f"{table}: content verification failed; import rolled back"
                        )
                conn.execute(
                    sql.SQL(
                        "SELECT setval(pg_get_serial_sequence(%s,'id'),"
                        "greatest(coalesce((SELECT max(id) FROM {}),0),1),"
                        "EXISTS(SELECT 1 FROM {}))"
                    ).format(sql.Identifier(table), sql.Identifier(table)),
                    (table,),
                )
            manifest["applied"] = True
    output = Path(args.manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                "applied": manifest["applied"],
                "rows": {t: v["rows"] for t, v in manifest["tables"].items()},
                "source_objects": len(manifest["objects"]),
                "manifest": str(output),
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source-sqlite", help="read-only SQLite source path")
    source.add_argument("--source-export", help="read-only supabase jsonl export directory")
    source.add_argument(
        "--source-postgres",
        action="store_true",
        help="read staging DB from PAPER_TRAIL_SOURCE_DATABASE_URL",
    )
    parser.add_argument("--objects", help="inventory source PDFs and provenance artifacts")
    parser.add_argument(
        "--manifest", required=True, help="counts/checksums; contains no source text"
    )
    parser.add_argument(
        "--apply", action="store_true", help="write only into empty public-record tables"
    )
    parser.add_argument(
        "--merge-duplicate-commitments",
        action="store_true",
        help="fold repeated acceptances of one candidate into its lowest commitment id",
    )
    parser.add_argument(
        "--quarantine-unverified",
        action="store_true",
        help="retain unverified nonaccepted candidates in a private source artifact",
    )
    migrate(parser.parse_args())


if __name__ == "__main__":
    main()
