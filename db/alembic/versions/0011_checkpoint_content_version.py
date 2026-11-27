"""ingest checkpoints belong to the pdf bytes they were made from"""

from pathlib import Path

from alembic import op

revision = "0011_checkpoint_content_version"
down_revision = "0010_official_sources_rls_off"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/018_checkpoint_content_version.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
