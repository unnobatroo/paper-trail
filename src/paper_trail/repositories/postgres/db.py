"""raw psycopg for the postgres-only bits (vector index, job queue, ops scripts)"""


def connect(database_url):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10)
