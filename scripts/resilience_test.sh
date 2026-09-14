#!/usr/bin/env bash
# Delivery resilience: head office goes down, the store keeps selling.
#
# This one has to run from the HOST, because it stops and starts containers,
# which nothing inside a container can do. The assertions themselves still run
# inside the forwarder, through `docker compose exec`.
#
# What it proves:
#   1. With head office stopped, a store still takes payments and records sales.
#   2. Those sales stay queued rather than being lost.
#   3. When head office returns, the backlog drains.
#   4. Nothing is duplicated: head office gains exactly as many invoices as
#      were made while it was down.

set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE="docker compose"
SYNC="store-1-sync"
STORE="store-1"
SALES_WHILE_DOWN=3

GREEN=$'\033[32m'
RED=$'\033[31m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

failures=0

check() {
    local description="$1"
    local condition="$2"
    local detail="${3:-}"
    if [ "$condition" = "true" ]; then
        printf '  %sPASS%s  %s\n' "$GREEN" "$RESET" "$description"
    else
        printf '  %sFAIL%s  %s\n' "$RED" "$RESET" "$description"
        [ -n "$detail" ] && printf '        %s\n' "$detail"
        failures=$((failures + 1))
    fi
}

run_in_sync() {
    $COMPOSE exec -T "$SYNC" python -m app.consolidation_tests "$@"
}

printf '%sDelivery resilience: head office unavailable%s\n\n' "$BOLD" "$RESET"

# Start from a drained queue so the counts below mean what they say.
printf 'Draining anything already queued...\n'
run_in_sync wait-drain 90 >/dev/null 2>&1 || true

before_central=$(run_in_sync central-count "$STORE" | tr -d '\r')

printf 'Stopping the central site...\n'
$COMPOSE stop central-api >/dev/null

# --- 1. Selling continues while head office is down ---------------------

if run_in_sync sell "$SALES_WHILE_DOWN" "$STORE" >/dev/null 2>&1; then
    check "The store keeps selling while head office is down" true
else
    check "The store keeps selling while head office is down" false \
          "A purchase failed, so the store depends on head office to sell"
fi

# Give the forwarder a few cycles to try and fail.
sleep 12

pending=$(run_in_sync pending | tr -d '\r')
if [ "$pending" -ge "$SALES_WHILE_DOWN" ]; then
    check "The sales stay queued instead of being lost" true
else
    check "The sales stay queued instead of being lost" false \
          "Expected at least $SALES_WHILE_DOWN queued, found $pending"
fi

during_central=$(run_in_sync central-count "$STORE" 2>/dev/null | tr -d '\r' || echo "unreachable")
if [ "$during_central" = "unreachable" ]; then
    check "Head office is genuinely unreachable while stopped" true
else
    check "Head office is genuinely unreachable while stopped" false \
          "Got a report back: $during_central"
fi

# --- 2. The backlog drains on recovery ----------------------------------

printf 'Starting the central site again...\n'
$COMPOSE start central-api >/dev/null

# Wait for it to accept connections again before asking it anything.
for _ in $(seq 1 30); do
    if run_in_sync central-count "$STORE" >/dev/null 2>&1; then
        break
    fi
    sleep 2
done

if run_in_sync wait-drain 120 >/dev/null; then
    check "The backlog drains once head office returns" true
else
    check "The backlog drains once head office returns" false \
          "Sales are still queued after two minutes"
fi

after_central=$(run_in_sync central-count "$STORE" | tr -d '\r')
expected=$((before_central + SALES_WHILE_DOWN))

if [ "$after_central" -eq "$expected" ]; then
    check "Every queued sale arrived exactly once" true
else
    check "Every queued sale arrived exactly once" false \
          "Expected $expected invoices, head office holds $after_central"
fi

printf '\n'
if [ "$failures" -gt 0 ]; then
    printf '%s%s%d check(s) failed.%s\n' "$RED" "$BOLD" "$failures" "$RESET"
    exit 1
fi
printf '%s%sAll checks passed.%s\n' "$GREEN" "$BOLD" "$RESET"
