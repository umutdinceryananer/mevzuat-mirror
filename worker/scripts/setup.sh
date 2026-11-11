#!/usr/bin/env bash
# One-time Cloudflare setup of the mevzuat-mirror worker. Safe to run again.
#
#   cd worker
#   npm install
#   npx wrangler login
#   npm run setup                  npm run setup -- --rotate makes a new address
#
# It creates the D1 database, writes its id into wrangler.jsonc, fills the
# database from data/, deploys the worker and sets the MCP path secret. At
# the end it prints the address to add in Claude. See docs/worker.md.
set -euo pipefail

cd "$(dirname "$0")/.."   # the worker/ directory

PLACEHOLDER="00000000-0000-0000-0000-000000000000"
ROTATE=false
if [ "${1:-}" = "--rotate" ]; then
  ROTATE=true
fi

wrangler() { npx --no-install wrangler "$@"; }
step() { printf '\n== %s\n' "$1"; }

# Prints the id of the D1 database called mevzuat, or nothing.
find_database() {
  wrangler d1 list --json | python3 -c '
import json, sys
for database in json.load(sys.stdin):
    if database.get("name") == "mevzuat":
        print(database.get("uuid") or database.get("id") or "")
'
}

step "1/5 Cloudflare login"
if ! wrangler whoami --json > /dev/null 2>&1; then
  echo "Not logged in to Cloudflare. Run npx wrangler login, then run this again."
  exit 1
fi
echo "Logged in."

step "2/5 D1 database"
id=$(grep -o '"database_id": *"[^"]*"' wrangler.jsonc | sed 's/.*"\([^"]*\)"$/\1/')
if [ "$id" = "$PLACEHOLDER" ]; then
  id=$(find_database)
  if [ -z "$id" ]; then
    # Eastern Europe is the closest location to Türkiye.
    wrangler d1 create mevzuat --location eeur > /dev/null
    id=$(find_database)
  fi
  if [ -z "$id" ]; then
    echo "Could not find the id of the mevzuat database."
    exit 1
  fi
  sed -i.bak "s/$PLACEHOLDER/$id/" wrangler.jsonc
  rm -f wrangler.jsonc.bak
  echo "Wrote database_id $id into wrangler.jsonc. Commit and push this change."
else
  echo "wrangler.jsonc already has database_id $id."
fi

step "3/5 Import data/ into D1"
(cd ../converter && python3 -m mevzuat_converter export-sql)
wrangler d1 execute mevzuat --remote --file=../build/d1.sql --yes

step "4/5 Deploy"
wrangler deploy

step "5/5 MCP path secret"
has_secret=$(wrangler secret list --format json 2> /dev/null | python3 -c '
import json, sys
try:
    names = [item.get("name") for item in json.load(sys.stdin)]
except ValueError:
    names = []
print("yes" if "MCP_PATH_SECRET" in names else "no")
')
if [ "$has_secret" = "yes" ] && [ "$ROTATE" = false ]; then
  echo "MCP_PATH_SECRET is already set, so the address stays the same."
  echo "npm run setup -- --rotate makes a new address and stops the old one."
else
  secret=$(openssl rand -hex 24)
  printf '%s' "$secret" | wrangler secret put MCP_PATH_SECRET > /dev/null
  printf '\nAdd this address in Claude as a custom connector.\n'
  printf 'Keep it private. Anyone who has it can use the server.\n\n'
  printf '  https://mevzuat.yananer.dev/%s/mcp\n\n' "$secret"
fi
