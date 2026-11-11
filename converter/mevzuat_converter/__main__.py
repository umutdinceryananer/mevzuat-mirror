"""Command line entry point.

Run it from the converter/ directory.

    python -m mevzuat_converter check
    python -m mevzuat_converter convert
"""

import argparse
import sys
from pathlib import Path

from . import VERSION
from .catalog import CatalogError, find_raw_files, load_catalog
from .document import build_document, write_document
from .extract import UnsupportedFormat, read_paragraphs
from .splitter import split_articles

# The repository root is two levels above this file.
# converter/mevzuat_converter/__main__.py -> converter/ -> repository root
DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def check(root: Path) -> int:
    """Check catalog.json and list the raw files found for each document.

    Returns the exit status, 0 when catalog.json is valid and 1 when it is not.
    """
    try:
        documents = load_catalog(root / "catalog.json")
    except CatalogError as error:
        print(f"catalog.json: {error}", file=sys.stderr)
        return 1

    print(f"catalog.json: {len(documents)} document(s)")
    for document in documents:
        files = find_raw_files(document, root / "raw")
        if files:
            names = ", ".join(str(path.relative_to(root)) for path in files)
        else:
            names = "no raw file yet"
        print(f"  {document.id:<20} {document.title}  [{names}]")
    return 0


def convert(root: Path, only: str | None) -> int:
    """Convert every document that has a raw file into data/<id>.json.

    Returns 0 when every document converted and 1 when any of them failed.
    A failed document keeps its old data file, so a bad upload never
    replaces good data.
    """
    try:
        documents = load_catalog(root / "catalog.json")
    except CatalogError as error:
        print(f"catalog.json: {error}", file=sys.stderr)
        return 1

    failed = False
    for entry in documents:
        if only is not None and entry.id != only:
            continue

        files = find_raw_files(entry, root / "raw")
        if not files:
            print(f"{entry.id}: skipped, no raw file yet")
            continue
        if len(files) > 1:
            names = ", ".join(path.name for path in files)
            print(f"{entry.id}: more than one raw file ({names}), keep only one", file=sys.stderr)
            failed = True
            continue
        raw_file = files[0]

        try:
            paragraphs = read_paragraphs(raw_file)
        except UnsupportedFormat as error:
            print(f"{entry.id}: {error}", file=sys.stderr)
            failed = True
            continue

        split = split_articles(paragraphs)
        if not split.articles:
            print(f"{entry.id}: no articles found in {raw_file.name}, nothing written", file=sys.stderr)
            failed = True
            continue

        document, warnings = build_document(entry, split, raw_file, root)
        write_document(document, root / "data" / f"{entry.id}.json")
        print(f"{entry.id}: {len(split.articles)} articles written to data/{entry.id}.json")
        for warning in warnings:
            print(f"{entry.id}: warning, {warning}")

    if only is not None and all(entry.id != only for entry in documents):
        print(f"{only}: not in catalog.json", file=sys.stderr)
        failed = True

    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="mevzuat_converter",
        description="Turn files in raw/ into data/<id>.json.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="repository root, defaults to the repository this converter lives in",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="check catalog.json and list raw files")
    convert_parser = commands.add_parser("convert", help="write data/<id>.json for documents with a raw file")
    convert_parser.add_argument("--only", metavar="ID", help="convert only this document, such as kanun-6098")

    args = parser.parse_args()
    if args.command == "check":
        return check(args.root)
    if args.command == "convert":
        return convert(args.root, args.only)
    return 2


if __name__ == "__main__":
    sys.exit(main())
