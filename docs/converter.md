# converter

## NAME

converter, turns files in raw/ into data/<id>.json

## SYNOPSIS

    cd converter
    python -m mevzuat_converter check
    python -m mevzuat_converter convert [--only <id>]
    python -m mevzuat_converter export-sql [--output <file>]

## DESCRIPTION

check
    Reads catalog.json, checks every entry against the rules in data-format.md, and lists the raw files found for each document. Exits with status 1 when catalog.json has an error, so it can run as a step in the GitHub Action.

convert
    For every document in catalog.json that has exactly one raw file, reads the file into paragraphs, splits it into articles, and writes data/<id>.json. --only <id> converts one document. When no articles are found, the document is reported and its old data file stays as it was. Exits with status 1 when any document fails.

export-sql
    Writes build/d1.sql, which drops every table, recreates them from worker/schema.sql, and inserts all of data/. The search index gets the normalized form of each heading and text. build/ is not committed.

Only .txt raw files can be read so far, text copied from the mevzuat.gov.tr page with one paragraph per line. The PDF, Word and HTML readers come after the sample files are checked.

## SETUP

Python 3.11 or newer. The converter itself needs no packages yet. Tests need pytest.

    cd converter
    pip install -r requirements-dev.txt
    python -m pytest

## FILES

converter/mevzuat_converter/__main__.py
    Command line entry point.

converter/mevzuat_converter/catalog.py
    Reading and checking catalog.json, finding raw files.

converter/mevzuat_converter/normalize.py
    Search normalization, see NORMALIZATION in data-format.md.

converter/mevzuat_converter/patterns.py
    Recognizes article labels, section headings and amendment notes, see KNOWN TEXT PATTERNS in data-format.md.

converter/mevzuat_converter/splitter.py
    Splits a list of paragraphs into preamble, articles and trailer. Decides which lines are article headings and keeps the section path of each article.

converter/mevzuat_converter/document.py
    Builds the data/<id>.json object, reads Kabul Tarihi and Resmi Gazete from the header, takes downloaded_at from git, and writes the file.

converter/mevzuat_converter/extract.py
    Reads a raw file into paragraphs. Only .txt for now.

converter/mevzuat_converter/export_sql.py
    Builds the SQL file for D1 from data/*.json.

converter/tests/
    Tests. test_repository_catalog_is_valid also checks the real catalog.json, so a broken catalog fails the tests.

## SEE ALSO

data-format.md, architecture.md
