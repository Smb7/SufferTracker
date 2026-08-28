#!/bin/bash
set -eu

APP_DIR=/opt/suffertracker

: "${ADMIN_EMAIL:?ADMIN_EMAIL is required}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD is required}"
: "${CADDY_EMAIL:?CADDY_EMAIL is required}"
: "${JWT_KEY:?JWT_KEY is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
LLM_API_KEY="${LLM_API_KEY:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root."
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker
bash "$APP_DIR/scripts/free-http-ports.sh"

mkdir -p "$APP_DIR"
cat > "$APP_DIR/.env" <<EOF
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
JWT_KEY=$JWT_KEY
CADDY_EMAIL=$CADDY_EMAIL
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
LLM_API_KEY=$LLM_API_KEY
EOF
chmod 600 "$APP_DIR/.env"
