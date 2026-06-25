#!/usr/bin/env bash
set -euo pipefail

APP_ENV="/opt/authclaw/.env"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

if [[ ! -f "$APP_ENV" ]]; then
  echo "$APP_ENV is missing." >&2
  exit 1
fi

DATABASE_URL="$(grep -E '^DATABASE_URL=' "$APP_ENV" | sed 's/^DATABASE_URL=//')"

if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL is missing in $APP_ENV." >&2
  exit 1
fi

read -r DB_USER DB_PASSWORD DB_HOST DB_PORT DB_NAME < <(
  DATABASE_URL="$DATABASE_URL" python3 - <<'PY'
import os
from urllib.parse import urlparse, unquote

url = urlparse(os.environ["DATABASE_URL"])
print(
    unquote(url.username or ""),
    unquote(url.password or ""),
    url.hostname or "",
    url.port or 5432,
    (url.path or "/").lstrip("/"),
)
PY
)

if [[ "$DB_HOST" != "127.0.0.1" && "$DB_HOST" != "localhost" ]]; then
  echo "DATABASE_URL host is $DB_HOST, not local PostgreSQL. Skipping local database setup."
  exit 0
fi

if [[ -z "$DB_USER" || -z "$DB_PASSWORD" || -z "$DB_NAME" ]]; then
  echo "Could not parse local PostgreSQL credentials from DATABASE_URL." >&2
  exit 1
fi

systemctl enable postgresql
systemctl start postgresql

sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v db_user="$DB_USER" \
  -v db_password="$DB_PASSWORD" \
  -v db_name="$DB_NAME" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE NOT EXISTS (
   SELECT FROM pg_catalog.pg_roles WHERE rolname = :'db_user'
)
\gexec

SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'db_user', :'db_password')
\gexec

SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_user')
WHERE NOT EXISTS (
   SELECT FROM pg_database WHERE datname = :'db_name'
)
\gexec
SQL

echo "Local PostgreSQL is ready."
echo "Database: $DB_NAME"
echo "User:     $DB_USER"
