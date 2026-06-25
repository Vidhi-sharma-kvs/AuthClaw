#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/authclaw"
FRONTEND_DIR="/var/www/authclaw"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/main.py" ]]; then
  echo "AuthClaw source files are missing from $APP_DIR." >&2
  exit 1
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "$APP_DIR/.env is missing. Copy deployment/ec2/backend.env.template and fill real values first." >&2
  exit 1
fi

cd "$APP_DIR"

python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt

chown -R authclaw:authclaw "$APP_DIR"

install -m 0644 deployment/ec2/authclaw-api.service /etc/systemd/system/authclaw-api.service
systemctl daemon-reload
systemctl enable authclaw-api
systemctl restart authclaw-api

cd "$APP_DIR/frontend"
npm ci
npm run build

rm -rf "$FRONTEND_DIR"/*
cp -r dist/* "$FRONTEND_DIR"/
chown -R www-data:www-data "$FRONTEND_DIR"

install -m 0644 "$APP_DIR/deployment/ec2/nginx-authclaw-frontend.conf" /etc/nginx/sites-available/authclaw
rm -f /etc/nginx/sites-enabled/default
ln -sfn /etc/nginx/sites-available/authclaw /etc/nginx/sites-enabled/authclaw
nginx -t
systemctl restart nginx

echo "AuthClaw backend and frontend started."
echo "Backend health: curl http://127.0.0.1:8000/health/ready"
echo "Frontend health: curl http://127.0.0.1/health"
