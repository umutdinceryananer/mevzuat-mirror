# worker

## NAME

worker, the Cloudflare Worker that serves the MCP endpoint

## SYNOPSIS

    cd worker
    npm install
    npm run dev          local server at http://localhost:8787
    npm run typecheck
    npm run deploy

## DESCRIPTION

The worker answers MCP requests over Streamable HTTP in stateless mode. Each request gets a new server, so nothing is kept between requests. It reads from the D1 database and never writes to it.

The endpoint is /<MCP_PATH_SECRET>/mcp. Every other path returns 404. When MCP_PATH_SECRET is not set, every request returns 503.

## SETUP

One time, from worker/.

1. Run npx wrangler login.
2. Run npx wrangler d1 create mevzuat and copy the printed database_id into wrangler.jsonc.
3. Pick a long random secret, for example the output of openssl rand -hex 24, and store it with npx wrangler secret put MCP_PATH_SECRET.
4. Fill the database. From converter/, run python -m mevzuat_converter convert and python -m mevzuat_converter export-sql. Then from worker/, run npm run db:remote.
5. Run npm run deploy. Cloudflare creates the DNS record for mevzuat.yananer.dev.
6. In Claude, add a custom connector with the URL https://mevzuat.yananer.dev/<secret>/mcp.

## LOCAL RUN

Create worker/.dev.vars with the single line MCP_PATH_SECRET=local, then run

    npm run db:local
    npm run dev

The endpoint is then http://localhost:8787/local/mcp.

## FILES

worker/wrangler.jsonc
    Cloudflare settings. Logs are off, the workers.dev address is off, and the custom domain is mevzuat.yananer.dev.

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
