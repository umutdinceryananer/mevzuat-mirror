"""Build the data/<id>.json object of one document and write it.

The fields are described in docs/data-format.md, under DOCUMENT FILE and
ARTICLE.
"""

import json
import re
import subprocess
from datetime import date
from pathlib import Path

from . import VERSION
from .catalog import Document
from .normalize import normalize
from .patterns import dates_in, find_notes
from .splitter import SplitResult

# The header gives the acceptance date in two ways.
#   law        Kabul Tarihi : 11/1/2011
#   decision   Bakanlar Kurulu Kararının Tarihi : 19/12/2012
_ACCEPTED_AT = re.compile(
    r"(?:Kabul\s+Tarihi|Kararının\s+Tarihi)\s*:?\s*(\d{1,2}[/.]\d{1,2}[/.]\d{4})"
)

# The header names the Resmi Gazete in several ways.
#   law         Yayımlandığı Resmî Gazete : Tarih : 4/2/2011 Sayı : 27836
#   decision    Yayımlandığı R.Gazetenin Tarihi : 27/1/2013 No : 28541
#   regulation  Resmî Gazete Tarihi: 25.07.2012 Resmî Gazete Sayısı: 28364
_OFFICIAL_GAZETTE = re.compile(
    r"(?:R\.\s*Gazete|Resm[iî]\s+Gazete)\D*?(\d{1,2}[/.]\d{1,2}[/.]\d{4})"
    r"\D*?(?:Say[ıi](?:s[ıi])?|No)\s*:?\s*(\d+)"
)

# Regulations from mevzuat.gov.tr have no header. The table at their end
# starts with the original publication, as in "Yönetmeliğin Yayımlandığı
# Resmî Gazete’nin Tarihi Sayısı 9/5/2021 31479".
_GAZETTE_TABLE_ROW = re.compile(
    r"Yayımlandığı\s+Resm[iî]\s+Gazete\S*\s+Tarihi\s+Sayısı\s+(\d{1,2}[/.]\d{1,2}[/.]\d{4})\s+(\d+)"
)


def build_document(entry: Document, split: SplitResult, raw_file: Path, root: Path) -> tuple[dict, list[str]]:
    """Return the data/<id>.json object of one document and a list of warnings.

    Warnings do not stop the conversion. They point at things a person
    should look at, such as a title that does not match catalog.json.
    """
    warnings: list[str] = []
    header = " ".join(split.preamble)

    if not split.articles:
        warnings.append("no articles found")

    # Long titles often take two lines, so the first few header lines are
    # searched together.
    header_start = normalize(" ".join(split.preamble[:4]))
    if split.preamble and normalize(entry.title) not in header_start:
        warnings.append(
            f"title in catalog.json ({entry.title!r}) is not in the first header lines ({split.preamble[0]!r})"
        )

    articles = []
    note_dates: list[str] = []
    for article in split.articles:
        # Notes can sit in the heading too, such as "(Değişik başlık: ...)".
        notes = find_notes(article.heading or "") + find_notes(article.text)
        for note in notes:
            note_dates.extend(dates_in(note))
        articles.append(
            {
                "order": article.order,
                "kind": article.kind,
                "number": article.number,
                "label": article.label,
                "heading": article.heading,
                "path": article.path,
                "repealed": article.repealed,
                "text": article.text,
                "notes": notes,
            }
        )

    document = {
        "id": entry.id,
        "type": entry.type,
        "number": entry.number,
        "title": entry.title,
        "short_names": entry.short_names,
        "source_url": entry.source_url,
        "accepted_at": _find_accepted_at(header),
        "official_gazette": _find_official_gazette(header, split.trailer),
        "downloaded_at": downloaded_at(raw_file, root),
        "latest_amendment_seen": _latest_date(note_dates, split),
        "converter_version": VERSION,
        "articles": articles,
    }
    return document, warnings


def downloaded_at(raw_file: Path, root: Path) -> str:
    """Return the date raw_file last changed in git, such as "2026-11-11".

    A file that is not committed yet gets today's date, because it is being
    added now.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(raw_file.relative_to(root))],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        committed = result.stdout.strip()
    except (OSError, ValueError, subprocess.CalledProcessError):
        committed = ""
    return committed or date.today().isoformat()


def write_document(document: dict, path: Path) -> None:
    """Write the document as UTF-8 JSON and keep Turkish letters readable."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def _find_accepted_at(header: str) -> str | None:
    match = _ACCEPTED_AT.search(header)
    if match is None:
        return None
    found = dates_in(match.group(1))
    return found[0] if found else None


def _find_official_gazette(header: str, trailer: list[str]) -> dict | None:
    """Read the Resmi Gazete date and issue from the header, or else from
    the table at the end of a regulation."""
    match = _OFFICIAL_GAZETTE.search(header) or _GAZETTE_TABLE_ROW.search(" ".join(trailer))
    if match is None:
        return None
    found = dates_in(match.group(1))
    if not found:
        return None
    return {"date": found[0], "number": match.group(2)}


def _latest_date(note_dates: list[str], split: SplitResult) -> str | None:
    """Return the newest date of the amendment notes, the footnotes and the
    closing parts, such as the list of amending legislation.

    Some of these are entry into force dates, so the result can be later
    than the download date. ISO dates sort correctly as plain text, so max()
    gives the newest.
    """
    dates = list(note_dates)
    for paragraph in split.footnotes + split.trailer:
        dates.extend(dates_in(paragraph))
    return max(dates) if dates else None
