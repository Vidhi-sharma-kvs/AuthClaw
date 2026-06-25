#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/authclaw"
FRONTEND_DIR="/var/www/authclaw"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

apt-get update
apt-get install -y --no-install-recommends \
  git \
  nginx \
  python3 \
  python3-venv \
  python3-pip \
  postgresql \
  postgresql-client \
  build-essential \
  libpq-dev \
  curl \
  ca-certificates

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

id -u authclaw >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin authclaw

mkdir -p "$APP_DIR" "$FRONTEND_DIR"
chown -R authclaw:authclaw "$APP_DIR"

echo "Base EC2 packages installed."
echo "Next:"
echo "1. Copy the AuthClaw repository contents to $APP_DIR."
echo "2. Copy deployment/ec2/backend.env.template to $APP_DIR/.env and fill real values."
echo "3. Run deployment/ec2/setup-app.sh with sudo from inside $APP_DIR."
