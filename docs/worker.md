# worker

## NAME

worker, the Cloudflare Worker that serves the MCP endpoint

## SYNOPSIS

    cd worker
    npm install
    npm run setup        one-time Cloudflare setup, see SETUP
    npm run dev          local server at http://localhost:8787
    npm run typecheck
    npm run deploy

## DESCRIPTION

The worker answers MCP requests over Streamable HTTP in stateless mode. Each request gets a new server, so nothing is kept between requests. It reads from the D1 database and never writes to it.

The endpoint is /<MCP_PATH_SECRET>/mcp. Every other path returns 404. When MCP_PATH_SECRET is not set, every request returns 503.

## SETUP

One time, on a computer with Node.js, Python 3 and openssl. LibreOffice is not needed, because data/ is already converted.

    git clone https://github.com/umutdinceryananer/mevzuat-mirror
    cd mevzuat-mirror/worker
    npm install
    npx wrangler login
    npm run setup

npx wrangler login opens the browser to approve access to the Cloudflare account that holds yananer.dev. npm run setup runs scripts/setup.sh, which takes five steps.

1. Checks the login.
2. Finds the D1 database called mevzuat, or creates it in Eastern Europe, and writes its id into wrangler.jsonc.
3. Builds build/d1.sql from data/ and imports it into the database.
4. Deploys the worker. The first deploy also creates the DNS record and certificate for mevzuat.yananer.dev, which can take a few minutes to answer.
5. Sets MCP_PATH_SECRET to a random value and prints the address to add in Claude as a custom connector.

Commit and push the database_id change in wrangler.jsonc, so the workflow uses the same database. The address works like a password, so share it only with the person who uses the connector.

Running the script again is safe. It keeps the secret and the address. npm run setup -- --rotate sets a new secret, prints a new address and stops the old one.

## LOCAL RUN

Create worker/.dev.vars with the single line MCP_PATH_SECRET=local, then run

    npm run db:local
    npm run dev

The endpoint is then http://localhost:8787/local/mcp.

## FILES

worker/wrangler.jsonc
    Cloudflare settings. Logs are off, the workers.dev address is off, and the custom domain is mevzuat.yananer.dev.

worker/scripts/setup.sh
    The one-time setup behind npm run setup.

worker/schema.sql
    The D1 tables. The export-sql command of the converter runs it on every import.

worker/src/index.ts
    Routing and the MCP transport.

worker/src/server.ts
    The MCP server, its instructions to Claude, and the tool registrations.

worker/src/env.ts
    Types of the bindings and secrets.

worker/src/tools/
    One file per MCP tool.

worker/src/documents.ts
    Reads documents and finds the one a tool call names, by short name, number, id or title.

worker/src/articles.ts
    Reads article references such as 344, 347-352, geçici 1, ek 2 or 4/A, and fetches the articles.

worker/src/normalize.ts
    Same steps as normalize.py in the converter, see NORMALIZATION in data-format.md.

worker/src/result.ts
    Wraps text into MCP tool results.

## SEE ALSO

architecture.md, data-format.md, converter.md
