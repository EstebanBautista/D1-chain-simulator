#!/bin/sh
# Prepare this register, then hand over to nginx.
#
# Two things are rendered from the environment at container start, so that one
# image serves all four registers:
#
#   1. register-config.js, which tells the site which store and which register
#      it is running on. The site loads it from whichever register served it,
#      so a sale's attribution is decided by the URL the cashier opened, not by
#      anything the page could choose for itself.
#
#   2. The nginx upstream, so each register proxies to ITS OWN store's web
#      server. Store 1's registers must never reach store 2's site, and with
#      the two stores on separate networks they could not anyway.

set -e

STORE_ID="${STORE_ID:-unknown-store}"
STORE_NAME="${STORE_NAME:-Tienda desconocida}"
REGISTER_ID="${REGISTER_ID:-unknown-register}"
FRONTEND_URL="${FRONTEND_URL:-http://frontend:80}"

# Strip the scheme: nginx wants host:port in proxy_pass, and the variable is
# written as a URL to match how every other service address is configured.
FRONTEND_UPSTREAM="$(echo "$FRONTEND_URL" | sed -e 's#^https\?://##' -e 's#/$##')"

mkdir -p /usr/share/nginx/html

cat > /usr/share/nginx/html/register-config.js <<EOF
// Generated at container start from this register's environment.
//
// The page cannot choose these values; it can only read what the register that
// served it declares. That is what makes the attribution unfalsifiable from
// the browser.
window.REGISTER_ID = "${REGISTER_ID}";
window.STORE_ID = "${STORE_ID}";
window.STORE_NAME = "${STORE_NAME}";
EOF

sed "s#__FRONTEND_UPSTREAM__#${FRONTEND_UPSTREAM}#" \
    /etc/nginx/templates/register.conf.template \
    > /etc/nginx/conf.d/register.conf

echo "Register ${REGISTER_ID} of ${STORE_ID} ready;" \
     "serving ${FRONTEND_UPSTREAM} on port 80"

exec "$@"
