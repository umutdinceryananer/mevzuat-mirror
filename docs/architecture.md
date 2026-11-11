# architecture

## NAME

architecture, how a document moves from mevzuat.gov.tr to Claude

## OVERVIEW

    mevzuat.gov.tr
        |   downloaded by hand (PDF or Word)
        v
    raw/<id>.<ext>          committed to git
        |   converter (Python, runs in a GitHub Action)
        v
    data/<id>.json          committed to git, one file per document
        |   import (same GitHub Action)
        v
    Cloudflare D1           documents, articles, search index
        |
        v
    Cloudflare Worker       MCP server at mevzuat.yananer.dev
        |
        v
    Claude                  custom connector on the lawyer's account

Nothing in this chain sends a request to mevzuat.gov.tr when the lawyer asks a question. The bot protection on the site therefore does not affect queries. The cost is that the stored copy goes stale when a document is amended. See FRESHNESS.

## COMPONENTS

converter
    Python script in converter/. Reads raw/<id>.<ext>, reads metadata from the document header, splits the text into articles, and writes data/<id>.json in the format described in data-format.md. It stops with a clear message when it cannot find articles, so a bad file is caught before it reaches the server.

worker
    TypeScript Cloudflare Worker in worker/. Serves the MCP endpoint over Streamable HTTP and reads from D1. It has no write access to anything.

D1 database
    Holds a documents table, an articles table, and an FTS5 table for keyword search. The import rebuilds all tables on every run. With 10 to 30 documents a full rebuild is small.

GitHub Action
    Runs on every push that changes raw/, catalog.json or converter/. It runs the converter, commits the changed data/ files, rebuilds D1, and deploys the worker when worker/ changed.

upload page (planned for v2)
    A page at mevzuat.yananer.dev/yukle where the lawyer uploads a new file. It commits the file to raw/ through the GitHub API, which starts the Action. Cloudflare Access protects the page with a one-time code sent to the lawyer's email.

## MCP TOOLS

list_documents
    All stored documents with title, short names, download date, latest amendment seen, and source URL.

get_outline
    Section headings and article headings of one document. Claude reads this to find the right articles for a question asked in plain language.

get_articles
    Full text of one or more articles. Accepts single articles (TBK 344), ranges (TBK 347-352), and special articles (geçici 1, ek 2).

search
    Keyword search over article text and headings, in all documents or in one. Matches by word prefix, so kiracı also finds kiracının.

Every tool result includes the download date and the source URL of each document it returns.

## HOSTING

The worker runs on a Workers custom domain, mevzuat.yananer.dev. The yananer.dev zone is already on Cloudflare. At this scale the free tier is expected to be enough. Check CPU time per request after the first deploy.

## ACCESS

The MCP endpoint sits under a long random path segment, for example mevzuat.yananer.dev/<secret>/mcp. The worker reads the secret from a Cloudflare secret, never from the repository. Requests to any other path get 404. To rotate access, change the secret and update the connector URL in Claude.

The repository is public. It holds law text, code and documentation only. It holds no secrets, no logs and no user data.

## PRIVACY

The worker does not log tool arguments, because search terms can hint at client matters. Workers Logs are turned off in the worker config, so request details are not kept either.

## FRESHNESS

Each document carries two dates.

downloaded_at
    When raw/<id>.<ext> last changed in git. Shows how old the copy is.

latest_amendment_seen
    The newest date found in the amendment notes of the text, for example in (Değişik: 24/11/2016-6763/14 md.). Shows up to which amendment the copy reaches.

The lawyer downloads a document again when it changes. A watcher that checks Resmi Gazete for amendments to tracked documents is planned for a later phase.

## PHASES

v1
    Pick the input format from samples, write the converter, the D1 import and the worker with four tools, connect to Claude, compare answers against live mevzuat.gov.tr.

v2
    Upload page behind Cloudflare Access. Uploads start the GitHub Action.

later
    Resmi Gazete watcher, search by meaning with embeddings, more document types.

## SEE ALSO

data-format.md
