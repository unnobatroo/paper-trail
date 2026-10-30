"""event polarity, implementation artifacts, 5-state money, jurisdiction, gazetteer"""

from pathlib import Path

from alembic import op

revision = "0003_accountability"
down_revision = "0002_worker_leases"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/010_accountability.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup rather than dropping audit evidence")
