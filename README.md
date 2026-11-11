# mevzuat-mirror

A copy of selected Turkish legislation, downloaded by hand from mevzuat.gov.tr and served to Claude through a remote MCP server.

## STATUS

Design stage. The converter and the server are not written yet. The first sample document is 6098 Türk Borçlar Kanunu.

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

This is the planned layout. Each path appears with the commit that adds it.

## SEE ALSO

docs/architecture.md, docs/data-format.md
