#!/bin/sh
set -eu
umask 077
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
tmp="backups/$stamp.sql.gz.tmp"
# Avoid losing a pg_dump failure in a shell pipeline.
docker compose exec -T db pg_dump -U lightning -d lightning --no-owner --no-acl > "backups/$stamp.sql.tmp"
gzip -c "backups/$stamp.sql.tmp" > "$tmp"
rm "backups/$stamp.sql.tmp"
mv "$tmp" "backups/$stamp.sql.gz"
tar -czf "backups/$stamp.configuration.tar.gz" .env compose.yaml
echo "Sauvegarde privée créée : $stamp. Conserver une copie hors du serveur."
