"""candidates dedupe on the verbatim receipt instead of the llm's wording"""

from pathlib import Path

from alembic import op

revision = "0008_candidate_receipt_key"
down_revision = "0007_ingest_checkpoints"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/015_candidate_receipt_key.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
