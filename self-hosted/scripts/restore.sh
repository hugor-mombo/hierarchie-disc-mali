#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ "${1:-}" != '--confirm-restore' ] || [ ! -f "${2:-}" ]; then
  echo 'Usage : ./scripts/restore.sh --confirm-restore backups/postgres-DATE.dump' >&2
  echo 'Remplace la base du registre ; ne restaure pas DISC ni DHIS2.' >&2
  exit 1
fi
docker compose stop web worker
docker compose exec -T db sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --exit-on-error' < "$2"
docker compose run --rm migrate
docker compose up -d web worker
