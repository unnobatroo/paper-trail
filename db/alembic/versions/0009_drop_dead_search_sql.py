"""drop sql functions and the hungarian tsv column nothing reads"""

from pathlib import Path

from alembic import op

revision = "0009_drop_dead_search_sql"
down_revision = "0008_candidate_receipt_key"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/016_drop_dead_search_sql.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
