#!/bin/sh
# check a backup against a throwaway db, never the live one
set -eu
if [ "$#" -ne 1 ]; then
  echo 'usage: restore-check.sh /absolute/path/to/backup-directory' >&2
  exit 2
fi
backup_dir=$(cd "$1" && pwd)
(cd "$backup_dir" && sha256sum -c SHA256SUMS)
tar -tzf "$backup_dir/documents.tar.gz" > /dev/null
container=paper-trail-restore-check-$$
trap 'docker rm -fv "$container" >/dev/null 2>&1 || true' EXIT HUP INT TERM
docker run -d --name "$container" --network none \
  -e POSTGRES_HOST_AUTH_METHOD=trust pgvector/pgvector:pg16 >/dev/null
for attempt in $(seq 1 30); do
  if docker exec "$container" pg_isready -U postgres >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$container" createdb -U postgres restore_check
docker exec -i "$container" psql -U postgres -d restore_check -v ON_ERROR_STOP=1 < "$backup_dir/roles.sql"
docker exec -i "$container" pg_restore -U postgres -d restore_check --exit-on-error --no-owner < "$backup_dir/database.dump"
docker exec "$container" psql -U postgres -d restore_check -v ON_ERROR_STOP=1 \
  -c 'SELECT count(*) AS commitments FROM commitments' \
  -c 'SELECT count(*) AS links FROM links'
