"""plain-english notes + ai suggestions on queue items"""

from pathlib import Path

from alembic import op

revision = "0005_notes"
down_revision = "0004_language_profiles"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/012_notes.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
