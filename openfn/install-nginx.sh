#!/bin/sh
set -eu
[ "$(id -u)" = 0 ] || { echo 'Exécuter avec sudo.' >&2; exit 1; }
domain=openfn.disc-mali.ml
site=/etc/nginx/sites-available/$domain
if [ -e "$site" ]; then
  echo 'Un vhost OpenFn existe déjà : vérifier sa configuration avant modification.' >&2
  exit 1
fi
cat > "$site" <<'EOF'
# disc-openfn managed vhost
server {
    listen 80;
    listen [::]:80;
    server_name openfn.disc-mali.ml;
    client_max_body_size 12m;
    location / {
        proxy_pass http://127.0.0.1:5400;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
ln -s "$site" /etc/nginx/sites-enabled/$domain
if ! nginx -t; then
    rm /etc/nginx/sites-enabled/$domain "$site"
    exit 1
fi
systemctl reload nginx
certbot --nginx --non-interactive --agree-tos --register-unsafely-without-email --redirect --cert-name "$domain" --domain "$domain"
nginx -t
systemctl reload nginx
