"""baseline the immutable SQL history without Supabase-specific RLS roles"""

from pathlib import Path

from alembic import op

revision = "0001_local_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    root = Path(__file__).resolve().parents[2] / "sql"
    # these files remain immutable; cloud RLS role assumptions in 004 are excluded
    for name in [
        "001_schema.sql",
        "002_pgvector.sql",
        "003_jobs.sql",
        "005_official_sources.sql",
        "006_hybrid_search.sql",
        "007_hybrid_or_query.sql",
        "008_reviewed_rows_are_final.sql",
    ]:
        sql = (root / name).read_text()
        if name == "002_pgvector.sql":
            sql = sql.split("-- Source documents", 1)[0]
        op.get_bind().exec_driver_sql(sql)


def downgrade():
    raise RuntimeError("restore a verified backup rather than dropping public records")
