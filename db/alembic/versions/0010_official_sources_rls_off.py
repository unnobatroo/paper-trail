"""official_sources readable by the app roles again (no RLS without policies)"""

from pathlib import Path

from alembic import op

revision = "0010_official_sources_rls_off"
down_revision = "0009_drop_dead_search_sql"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/017_official_sources_rls_off.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
