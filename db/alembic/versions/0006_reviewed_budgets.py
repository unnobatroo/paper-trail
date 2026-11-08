"""workers can't add money to reviewed evidence"""

from pathlib import Path

from alembic import op

revision = "0006_reviewed_budgets"
down_revision = "0005_notes"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/013_reviewed_budgets.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
