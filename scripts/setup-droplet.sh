#!/bin/sh
set -eu

APP_DIR=/opt/suffertracker

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root."
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git rsync
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

mkdir -p "$APP_DIR"
if [ ! -f "$APP_DIR/.env" ]; then
  if [ -f "$APP_DIR/.env.example" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  else
    cat > "$APP_DIR/.env" <<'EOF'
POSTGRES_PASSWORD=change-me-to-a-long-random-password
JWT_KEY=change-me-to-at-least-32-random-characters
CADDY_EMAIL=you@example.com
ADMIN_EMAIL=you@example.com
EOF
  fi
  echo "Created $APP_DIR/.env — edit passwords, JWT_KEY, CADDY_EMAIL, and ADMIN_EMAIL before the first deploy."
fi

echo "Open ports 22, 80, and 443. Do not publish 5432."
echo "DNS: A  @ -> this droplet IPv4 ;  CNAME  www -> suffertracker.net"
