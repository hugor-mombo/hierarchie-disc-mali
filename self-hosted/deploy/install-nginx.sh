#!/bin/sh
set -eu
if [ "$(id -u)" -ne 0 ]; then
  echo 'Exécuter avec sudo : sudo sh deploy/install-nginx.sh maintenance.disc-mali.ml' >&2
  exit 1
fi
domain=${1:-maintenance.disc-mali.ml}
case "$domain" in ''|*[!a-zA-Z0-9.-]*|.*|-*) echo 'Domaine invalide.' >&2; exit 1;; esac
site="/etc/nginx/sites-available/$domain"
enabled="/etc/nginx/sites-enabled/$domain"
marker='# maintenance-disc-mali managed vhost'
if [ -e "$site" ]; then
  if ! grep -qF "$marker" "$site"; then
    echo "Configuration existante non gérée : $site. Aucun remplacement." >&2
    exit 1
  fi
else
  cat > "$site" <<EOF
$marker
server {
    listen 80;
    listen [::]:80;
    server_name $domain;
    client_max_body_size 20m;
    location / {
        proxy_pass http://127.0.0.1:5300;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
  chmod 644 "$site"
  ln -s "$site" "$enabled"
  if ! nginx -t; then
    rm "$enabled" "$site"
    echo 'Configuration refusée ; nouveau vhost retiré.' >&2
    exit 1
  fi
fi
nginx -t
systemctl reload nginx
# Reprend le compte ACME existant. Si aucun compte n'existe, permet une
# inscription sans adresse de notification ; aucune adresse n'est inventée.
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email \
  --redirect --cert-name "$domain" --domain "$domain"
nginx -t
systemctl reload nginx
certbot certificates --cert-name "$domain"
echo "Déploiement HTTPS disponible : https://$domain"
