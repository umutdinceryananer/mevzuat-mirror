# converter

## NAME

converter, turns files in raw/ into data/<id>.json

## SYNOPSIS

    cd converter
    python -m mevzuat_converter check

## DESCRIPTION

check
    Reads catalog.json, checks every entry against the rules in data-format.md, and lists the raw files found for each document. Exits with status 1 when catalog.json has an error, so it can run as a step in the GitHub Action.

More commands arrive with later commits. The plan is to read the raw file, split it into articles, and write data/<id>.json.

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

converter/tests/
    Tests. test_repository_catalog_is_valid also checks the real catalog.json, so a broken catalog fails the tests.

## SEE ALSO

data-format.md, architecture.md
