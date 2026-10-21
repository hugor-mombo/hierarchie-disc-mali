#!/bin/sh
# À exécuter en tant que propriétaire du dossier de déploiement.
set -eu
app=${1:-/opt/maintenance-disc-mali}
revision=${2:-main}
repo="$app/.deploy-repository.git"
[ -f "$app/.env" ] || { echo 'Configuration .env manquante.' >&2; exit 1; }
if [ ! -d "$repo" ]; then
  git clone --bare --branch main https://github.com/hugor-mombo/hierarchie-disc-mali.git "$repo"
fi
git --git-dir="$repo" fetch origin main
commit=$(git --git-dir="$repo" rev-parse --verify 'FETCH_HEAD^{commit}')
if [ "$revision" != main ]; then
  expected=$(git --git-dir="$repo" rev-parse --verify "$revision^{commit}")
  [ "$commit" = "$expected" ] || { echo 'La version demandée ne correspond pas à main.' >&2; exit 1; }
fi
# L'archive Git ne contient ni .env, ni données, ni sauvegardes.
archive=$(mktemp)
trap 'rm -f "$archive"' EXIT HUP INT TERM
git --git-dir="$repo" archive "$commit:self-hosted" > "$archive"
# Remplacer le script par renommage conserve le descripteur du script en cours.
# Une extraction directe pourrait tronquer le fichier que le shell lit encore.
tar --exclude=deploy/update-from-git.sh -xf "$archive" -C "$app"
next_script=$(mktemp "$app/deploy/.update-from-git.XXXXXX")
git --git-dir="$repo" show "$commit:self-hosted/deploy/update-from-git.sh" > "$next_script"
chmod 644 "$next_script"
mv "$next_script" "$app/deploy/update-from-git.sh"
cd "$app"
docker compose config --quiet
docker compose build
docker compose up -d --wait --wait-timeout 180
printf '%s\n' "$commit" > DEPLOYED_REVISION
curl --fail --silent --show-error http://127.0.0.1:5300/api/health
printf '\nVersion déployée : %s\n' "$commit"
