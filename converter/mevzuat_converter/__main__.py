"""Command line entry point.

Run it from the converter/ directory:

    python -m mevzuat_converter check
"""

import argparse
import sys
from pathlib import Path

from . import VERSION
from .catalog import CatalogError, find_raw_files, load_catalog

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

    args = parser.parse_args()
    if args.command == "check":
        return check(args.root)
    return 2


if __name__ == "__main__":
    sys.exit(main())
