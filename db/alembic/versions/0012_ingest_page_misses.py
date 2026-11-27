"""count the misses per page so a page that never reads stops being retried"""

from pathlib import Path

from alembic import op

revision = "0012_ingest_page_misses"
down_revision = "0011_checkpoint_content_version"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/019_ingest_page_misses.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
