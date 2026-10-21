#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T db sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/postgres-$stamp.dump"
if [ "${1:-}" = '--with-work' ]; then
  docker compose exec -T worker tar -C /var/lib/hierarchie -czf - . > "backups/deplacements-$stamp.tar.gz"
fi
printf 'Sauvegarde PostgreSQL : backups/postgres-%s.dump\n' "$stamp"
