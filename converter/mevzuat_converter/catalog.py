"""Read and check catalog.json.

catalog.json is the hand-edited list of documents this project tracks.
The rules for each entry are in docs/data-format.md, under CATALOG ENTRY.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Document types we accept. Keep this in sync with docs/data-format.md (ID).
TYPES = {"kanun", "khk", "cbk", "tuzuk", "yonetmelik", "teblig", "karar", "genelge"}

# File types a person can download from mevzuat.gov.tr.
RAW_EXTENSIONS = ["pdf", "doc", "docx", "html"]

# Lowercase ASCII letters and digits, with one hyphen after the type.
# Examples that match are "kanun-6098" and "yonetmelik-12345".
ID_PATTERN = re.compile(r"[a-z]+-[a-z0-9]+")

REQUIRED_FIELDS = ["id", "type", "number", "title", "source_url"]
OPTIONAL_FIELDS = ["short_names"]

SOURCE_URL_PREFIX = "https://www.mevzuat.gov.tr/"


class CatalogError(Exception):
    """A problem in catalog.json. The message tells the person what to fix."""


@dataclass
class Document:
    """One entry of catalog.json."""

    id: str
    type: str
    number: str
    title: str
    source_url: str
    short_names: list[str] = field(default_factory=list)


def load_catalog(path: Path) -> list[Document]:
    """Read catalog.json and return its entries as Document objects.

    Raises CatalogError with a readable message when something is wrong.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise CatalogError(f"{path} does not exist")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise CatalogError(f"{path} is not valid JSON ({error})")

    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise CatalogError(f'{path} must be an object with a "documents" list')

    documents = []
    seen_ids = set()
    for position, entry in enumerate(data["documents"], start=1):
        document = _check_entry(entry, position)
        if document.id in seen_ids:
            raise CatalogError(f"entry {position}: id {document.id!r} is used twice")
        seen_ids.add(document.id)
        documents.append(document)
    return documents


def _check_entry(entry: object, position: int) -> Document:
    """Check one catalog entry and turn it into a Document."""
    where = f"entry {position}"

    if not isinstance(entry, dict):
        raise CatalogError(f"{where}: must be an object")

    # An unknown field is usually a typo, such as "short_name" for "short_names".
    for key in entry:
        if key not in REQUIRED_FIELDS and key not in OPTIONAL_FIELDS:
            raise CatalogError(f"{where}: unknown field {key!r}")

    for key in REQUIRED_FIELDS:
        value = entry.get(key)
        if not isinstance(value, str) or not value.strip():
            raise CatalogError(f"{where}: {key!r} must be a non-empty string")

    short_names = entry.get("short_names", [])
    if not isinstance(short_names, list):
        raise CatalogError(f"{where}: 'short_names' must be a list")
    for name in short_names:
        if not isinstance(name, str) or not name.strip():
            raise CatalogError(f"{where}: every short name must be a non-empty string")

    document = Document(
        id=entry["id"],
        type=entry["type"],
        number=entry["number"],
        title=entry["title"],
        source_url=entry["source_url"],
        short_names=short_names,
    )

    # From here on the id is known, so error messages name it.
    where = f"{where} ({document.id})"

    if document.type not in TYPES:
        allowed = ", ".join(sorted(TYPES))
        raise CatalogError(f"{where}: type {document.type!r} is not one of {allowed}")

    if not ID_PATTERN.fullmatch(document.id) or not document.id.startswith(document.type + "-"):
        raise CatalogError(f"{where}: id must look like {document.type}-<number>, in lowercase ASCII")

    if not document.source_url.startswith(SOURCE_URL_PREFIX):
        raise CatalogError(f"{where}: source_url must start with {SOURCE_URL_PREFIX}")

    return document


def find_raw_files(document: Document, raw_dir: Path) -> list[Path]:
    """Return the downloaded files of a document, such as raw/kanun-6098.pdf.

    Normally there is one file. There can be more while we compare formats.
    """
    found = []
    for extension in RAW_EXTENSIONS:
        candidate = raw_dir / f"{document.id}.{extension}"
        if candidate.exists():
            found.append(candidate)
    return found
