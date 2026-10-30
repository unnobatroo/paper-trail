"""owner credentials are supplied only to the migration process"""

import os

from alembic import context
from sqlalchemy import create_engine

url = os.environ["PAPER_TRAIL_DATABASE_URL"]
if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
if context.is_offline_mode():
    raise RuntimeError("use an online migration against PostgreSQL")
with create_engine(url).connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
