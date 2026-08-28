#!/bin/bash
set -eu

for svc in apache2 nginx httpd; do
  systemctl disable --now "$svc" 2>/dev/null || true
done

if command -v docker >/dev/null 2>&1; then
  docker ps --format '{{.ID}} {{.Ports}}' | awk '/(^|[, ])0.0.0.0:80->|(^|[, ]):::80->|(^|[, ])0.0.0.0:443->|(^|[, ]):::443->/ { print $1 }' | xargs -r docker stop
fi

if ! command -v fuser >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get install -y psmisc >/dev/null
fi
fuser -k 80/tcp 443/tcp 2>/dev/null || true
