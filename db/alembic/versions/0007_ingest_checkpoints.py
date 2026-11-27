"""per-page ingest checkpoints, a retried job resumes where it stopped"""

from pathlib import Path

from alembic import op

revision = "0007_ingest_checkpoints"
down_revision = "0006_reviewed_budgets"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/014_ingest_checkpoints.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
