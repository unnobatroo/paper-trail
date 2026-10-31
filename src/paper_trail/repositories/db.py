"""raw psycopg for one-off connections: maintenance, the worker's role check, ops scripts
the stores go through store.Repo's pooled engine
"""


def connect(database_url):
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=10)
