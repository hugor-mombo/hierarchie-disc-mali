#!/bin/sh
set -eu
cd "$(dirname "$0")/../self-hosted"
if [ -e .env ]; then
  echo 'self-hosted/.env existe déjà ; configuration conservée.'
  exit 0
fi
umask 077
secret=$(openssl rand -hex 32)
sed -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$secret/" \
    -e 's|^APP_URL=.*|APP_URL=http://localhost:5300|' \
    .env.example > .env
echo 'self-hosted/.env créé avec un mot de passe PostgreSQL aléatoire.'
