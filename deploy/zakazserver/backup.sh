#!/bin/sh
set -eu
umask 077
mkdir -p /backups
backup_once() {
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  temporary=/backups/.pending-$stamp
  mkdir "$temporary"
  pg_dump --format=custom --file="$temporary/database.dump"
  pg_dumpall --globals-only > "$temporary/roles.sql"
  tar -czf "$temporary/documents.tar.gz" -C /documents .
  (cd "$temporary" && sha256sum database.dump roles.sql documents.tar.gz > SHA256SUMS)
  mv "$temporary" "/backups/$stamp"
  find /backups -mindepth 1 -maxdepth 1 -type d -name '20*T*Z' \
    -mtime "+${BACKUP_RETENTION_DAYS:-7}" -exec rm -rf -- {} +
  printf '%s backup complete\n' "$stamp"
}
if [ "${1:-}" = once ]; then
  backup_once
  exit
fi
while :; do
  backup_once
  sleep 86400 &
  wait "$!"
done
