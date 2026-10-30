"""language profiles move from code into the db"""

from pathlib import Path

from alembic import op

revision = "0004_language_profiles"
down_revision = "0003_accountability"
branch_labels = None
depends_on = None


def upgrade():
    path = Path(__file__).resolve().parents[2] / "sql/011_language_profiles.sql"
    op.get_bind().exec_driver_sql(path.read_text())


def downgrade():
    raise RuntimeError("restore a verified backup instead")
