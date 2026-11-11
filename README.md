# mevzuat-mirror

A copy of selected Turkish legislation, downloaded by hand from mevzuat.gov.tr and served to Claude through a remote MCP server.

## STATUS

Not deployed yet. The converter reads text copied from mevzuat.gov.tr, and the PDF and Word readers wait for the sample files. The worker serves four MCP tools and runs locally. The first document in the catalog is 6098 Türk Borçlar Kanunu.

## WHY

mevzuat.gov.tr blocks automated requests from time to time, so Claude cannot read it reliably. This project makes no live requests to the site. A person downloads each document by hand, a converter splits it into articles, and the MCP server answers from the stored copy.

## LAYOUT

    catalog.json          list of tracked documents
    raw/                  files downloaded by hand, one per document
    data/                 converter output, one JSON file per document
    converter/            Python, turns raw/ into data/
    worker/               TypeScript, Cloudflare Worker that serves MCP
    .github/workflows/    build and deploy on push
    docs/architecture.md  how the parts fit together
    docs/data-format.md   fields of catalog.json and data/<id>.json
    docs/converter.md     converter commands
    docs/worker.md        worker setup and local run
    docs/deploy.md        the workflow, its secrets, adding a document

raw/ and data/ appear with the first converted document.

## SEE ALSO

docs/architecture.md, docs/data-format.md, docs/converter.md, docs/worker.md, docs/deploy.md
