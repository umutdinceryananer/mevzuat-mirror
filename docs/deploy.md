# deploy

## NAME

deploy, how a change reaches the live server

## DESCRIPTION

.github/workflows/deploy.yml runs on every push to main that changes raw/, catalog.json, converter/ or worker/. It can also be started by hand from the Actions tab.

1. Installs LibreOffice and pdftotext, which the converter uses to read Word, HTML and PDF files.
2. Checks catalog.json.
3. Converts every raw file into data/<id>.json.
4. Commits the changed data/ files back to main as github-actions[bot]. Commits made by the workflow do not start it again.
5. Builds build/d1.sql.
6. Installs the worker and runs the typecheck.
7. Rebuilds the D1 database from build/d1.sql. During the import the database is unavailable for a few seconds.
8. Deploys the worker.

Steps 7 and 8 run only when the Cloudflare secrets exist. Without them the workflow stops after the typecheck and stays green.

## SECRETS

Set these under Settings, Secrets and variables, Actions in the GitHub repository.

CLOUDFLARE_API_TOKEN
    A Cloudflare API token with Workers Scripts Edit and D1 Edit on the account, and Workers Routes Edit on the yananer.dev zone.

CLOUDFLARE_ACCOUNT_ID
    The Cloudflare account id, shown on the right side of the Workers overview page.

MCP_PATH_SECRET is not a GitHub secret. It is a Worker secret, set once with npx wrangler secret put MCP_PATH_SECRET, and every deploy keeps it.

## ADDING OR UPDATING A DOCUMENT

1. Add an entry to catalog.json for a new document.
2. Put the downloaded file at raw/<id>.<ext>, replacing the old one for an update.
3. Commit and push. The workflow does the rest.

Check the Actions tab after a push. A red run usually means the converter found no articles in the new file. The old data stays live in that case.

## SEE ALSO

architecture.md, converter.md, worker.md
