"""Tests for catalog.py and the check command.

Run them from the converter/ directory with python -m pytest
"""

import json
import re
from pathlib import Path

import pytest

from mevzuat_converter.__main__ import check
from mevzuat_converter.catalog import CatalogError, find_raw_files, load_catalog

TBK = {
    "id": "kanun-6098",
    "type": "kanun",
    "number": "6098",
    "title": "Türk Borçlar Kanunu",
    "short_names": ["TBK"],
    "source_url": "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=6098&MevzuatTur=1&MevzuatTertip=5",
}


def write_catalog(folder: Path, entries: list) -> Path:
    """Write a catalog.json with the given entries and return its path."""
    path = folder / "catalog.json"
    path.write_text(json.dumps({"documents": entries}, ensure_ascii=False), encoding="utf-8")
    return path


def test_valid_entry_is_loaded(tmp_path):
    documents = load_catalog(write_catalog(tmp_path, [TBK]))
    assert len(documents) == 1
    assert documents[0].id == "kanun-6098"
    assert documents[0].short_names == ["TBK"]


def test_short_names_are_optional(tmp_path):
    entry = dict(TBK)
    del entry["short_names"]
    documents = load_catalog(write_catalog(tmp_path, [entry]))
    assert documents[0].short_names == []


# Each case changes one field of a valid entry and names the error we expect.
@pytest.mark.parametrize(
    "change, message",
    [
        ({"title": ""}, "'title' must be a non-empty string"),
        ({"type": "law"}, "type 'law' is not one of"),
        ({"id": "Kanun-6098"}, "id must look like kanun-<number>"),
        ({"id": "yonetmelik-6098"}, "id must look like kanun-<number>"),
        ({"source_url": "https://example.com/6098"}, "source_url must start with"),
        ({"short_name": ["TBK"]}, "unknown field 'short_name'"),
        ({"short_names": "TBK"}, "'short_names' must be a list"),
    ],
)
def test_bad_entry_is_rejected(tmp_path, change, message):
    entry = {**TBK, **change}
    with pytest.raises(CatalogError, match=re.escape(message)):
        load_catalog(write_catalog(tmp_path, [entry]))


def test_duplicate_id_is_rejected(tmp_path):
    with pytest.raises(CatalogError, match="used twice"):
        load_catalog(write_catalog(tmp_path, [TBK, TBK]))


def test_missing_or_broken_file_is_rejected(tmp_path):
    path = tmp_path / "catalog.json"
    with pytest.raises(CatalogError, match="does not exist"):
        load_catalog(path)

    path.write_text("{ not json", encoding="utf-8")
    with pytest.raises(CatalogError, match="not valid JSON"):
        load_catalog(path)


def test_find_raw_files(tmp_path):
    document = load_catalog(write_catalog(tmp_path, [TBK]))[0]
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    assert find_raw_files(document, raw_dir) == []

    (raw_dir / "kanun-6098.pdf").write_bytes(b"")
    (raw_dir / "kanun-6098.docx").write_bytes(b"")
    names = [path.name for path in find_raw_files(document, raw_dir)]
    assert names == ["kanun-6098.pdf", "kanun-6098.docx"]


def test_check_command_lists_documents(tmp_path, capsys):
    write_catalog(tmp_path, [TBK])
    assert check(tmp_path) == 0
    output = capsys.readouterr().out
    assert "kanun-6098" in output
    assert "no raw file yet" in output


def test_check_command_fails_on_bad_catalog(tmp_path, capsys):
    write_catalog(tmp_path, [{**TBK, "type": "law"}])
    assert check(tmp_path) == 1
    assert "is not one of" in capsys.readouterr().err


def test_repository_catalog_is_valid():
    """The real catalog.json at the repository root must always pass."""
    root = Path(__file__).resolve().parents[2]
    load_catalog(root / "catalog.json")
