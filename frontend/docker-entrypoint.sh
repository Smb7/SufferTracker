#!/bin/sh
set -eu
key=${MAP_APIKEY:-}
escaped=$(printf '%s' "$key" | sed 's/\\/\\\\/g; s/"/\\"/g')
printf 'window.__MAP_APIKEY="%s";\n' "$escaped" > /usr/share/nginx/html/map-config.js
exec nginx -g 'daemon off;'
