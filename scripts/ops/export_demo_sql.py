"""Export the review tables as SQL that creates and fills a separate `demo` schema.

For a public, read-only demo on a database that already holds other tables: nothing here
refers to `public`, so applying the files leaves everything else untouched. Triggers and
row security are left out (the demo's login only reads), and so are the page and vector
caches, job rows and the migration table.

  uv run python scripts/ops/export_demo_sql.py SOURCE_URL OUT_DIR --pg-dump /path/to/pg_dump

Then apply demo_schema.sql and demo_data.sql, and give a SELECT-only role the schema:
  GRANT USAGE ON SCHEMA demo TO demo_ro; GRANT SELECT ON ALL TABLES IN SCHEMA demo TO demo_ro;
  ALTER ROLE demo_ro SET search_path = demo;
"""

import argparse
import re
import subprocess
from pathlib import Path

TABLES = [
    "documents", "candidates", "commitments", "official_sources", "evidence", "budgets",
    "links", "implementation_artifacts", "artifact_evidence", "places", "language_profiles",
    "notes",
]
# Statements the read-only demo doesn't need; their functions aren't copied either.
SKIPPED = re.compile(r"^(CREATE TRIGGER|CREATE POLICY)\b|ENABLE ROW LEVEL SECURITY", re.I)


def dump(pg_dump: str, source: str, *flags: str) -> str:
    """Run pg_dump for the review tables and return its SQL."""
    cmd = [pg_dump, "--no-owner", "--no-privileges", "--no-comments", *flags]
    for table in TABLES:
        cmd += ["-t", f"public.{table}"]
    cmd.append(f"--dbname={source}")
    return subprocess.run(cmd, check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def to_demo_schema(sql: str) -> str:
    """Move the table definitions into the `demo` schema. Definitions only: no row text in it."""
    return sql.replace("public.", "demo.")


def to_demo_data(sql: str) -> str:
    """Point the inserts and sequence resets at `demo`. Only the statements pg_dump writes
    are touched, so a row's text that happens to say "public." stays as it was."""
    return re.sub(r"(?m)^(INSERT INTO |SELECT pg_catalog\.setval\(')public\.", r"demo.", sql)


def main() -> None:
    """Write demo_schema.sql and demo_data.sql into OUT_DIR."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="owner URL of the database holding the review data")
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--pg-dump", default="pg_dump")
    args = ap.parse_args()

    schema = dump(args.pg_dump, args.source, "--schema-only")
    kept = [line for line in schema.splitlines() if not SKIPPED.search(line.strip())]
    header = ("-- the public demo's tables, in their own schema so nothing in public is touched\n"
              "CREATE SCHEMA IF NOT EXISTS demo;\n\n")
    data = dump(args.pg_dump, args.source, "--data-only", "--inserts", "--rows-per-insert=100")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "demo_schema.sql").write_text(
        header + to_demo_schema("\n".join(kept)), encoding="utf-8", newline="\n")
    (args.out_dir / "demo_data.sql").write_text(
        to_demo_data(data), encoding="utf-8", newline="\n")
    print(f"wrote demo_schema.sql and demo_data.sql to {args.out_dir}")


if __name__ == "__main__":
    main()
