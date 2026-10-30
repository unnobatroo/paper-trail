"""the job worker. parsing + inference stay out of the api processes"""

import logging
import signal

from .api.deps import _handlers, get_state
from .repositories.postgres.db import connect
from .repositories.postgres.jobs import PostgresWorker


def main():
    logging.basicConfig(level=logging.INFO)
    state = get_state()
    with connect(state.settings.database_url) as conn:
        role = conn.execute("""SELECT current_user AS name,
            has_column_privilege(current_user,'candidates','review_status','UPDATE')
            OR has_column_privilege(current_user,'links','review_status','UPDATE')
            OR has_table_privilege(current_user,'commitments','INSERT') AS can_accept""").fetchone()
        if role["name"] != "paper_trail_worker" or role["can_accept"]:
            raise RuntimeError("worker credentials must have no review capabilities")
    if state.settings.process_role != "worker":
        raise RuntimeError("worker requires PROCESS_ROLE=worker")
    worker = PostgresWorker(state.settings.database_url, _handlers())
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: worker.stop.set())
    worker.run()


if __name__ == "__main__":
    main()
