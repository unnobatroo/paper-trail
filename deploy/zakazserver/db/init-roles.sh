#!/bin/sh
set -eu
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=api_password="$API_DB_PASSWORD" \
  --set=worker_password="$WORKER_DB_PASSWORD" <<'SQL'
\set ON_ERROR_STOP on
CREATE ROLE paper_trail_api LOGIN PASSWORD :'api_password';
CREATE ROLE paper_trail_worker LOGIN PASSWORD :'worker_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
