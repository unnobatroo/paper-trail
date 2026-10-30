"""worker leases, uniqueness and review capability grants"""

from pathlib import Path

from alembic import op

revision = "0002_worker_leases"
down_revision = "0001_local_baseline"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/009_local_workers.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup rather than weakening review boundaries")
