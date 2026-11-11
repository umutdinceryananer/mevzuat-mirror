"""Recognize the special lines of a legislation text.

Three kinds of lines matter to the converter.

    article labels      MADDE 344 – ..., GEÇİCİ MADDE 1 – ...
    section headings    BİRİNCİ KISIM, İKİNCİ BÖLÜM, ...
    amendment notes     (Değişik: 24/11/2016-6763/14 md.)

docs/data-format.md lists the known forms under KNOWN TEXT PATTERNS.
These rules are a first version. They will change once we look at the
real sample files.
"""

import re
from dataclasses import dataclass
from datetime import date

from .normalize import normalize

# ---------------------------------------------------------------------------
# Article labels
# ---------------------------------------------------------------------------

# Words that can come before MADDE. Longer ones come first, so that
# "EK GEÇİCİ" is tried before "EK".
_PREFIX = r"EK\s+GEÇİCİ|Ek\s+Geçici|Ek\s+geçici|GEÇİCİ|Geçici|EK|Ek|MÜKERRER|Mükerrer"

# MADDE, then the number (344, or 4/A for an inserted article), then a
# hyphen, an en dash or an em dash, then the start of the article text.
# The dashes are written as – and — so the file stays plain ASCII there.
_ARTICLE_LABEL = re.compile(
    rf"^(?:(?P<prefix>{_PREFIX})\s+)?"
    r"(?:MADDE|Madde)\s+"
    r"(?P<number>\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)"
    r"\s*[-–—]\s*"
    r"(?P<rest>.*)$",
    re.DOTALL,
)

# The prefix, after normalize(), decides the kind of the article.
_KIND_BY_PREFIX = {
    "": "madde",
    "ek": "ek_madde",
    "gecici": "gecici_madde",
    "ek gecici": "ek_gecici_madde",
    "mukerrer": "mukerrer_madde",
}

# A whole article is repealed when its text starts with "(Mülga:".
# "(Mülga birinci fıkra: ...)" only repeals a part, so it does not count.
_WHOLE_ARTICLE_REPEALED = re.compile(r"^\(\s*(?:Mülga|MÜLGA)\s*:")


@dataclass
class ArticleLabel:
    """The label at the start of an article, and the text that follows it."""

    kind: str     # madde, ek_madde, gecici_madde, ek_gecici_madde or mukerrer_madde
    number: str   # without spaces, for example "344" or "4/A"
    label: str    # as printed, for example "GEÇİCİ MADDE 1"
    rest: str     # the text after the dash, the start of the article body


def match_article_label(paragraph: str) -> ArticleLabel | None:
    """Return the article label at the start of a paragraph, or None."""
    text = paragraph.strip()
    match = _ARTICLE_LABEL.match(text)
    if match is None:
        return None

    prefix = normalize(match.group("prefix") or "")
    number = re.sub(r"\s+", "", match.group("number")).upper()
    label = " ".join(text[: match.end("number")].split())
    return ArticleLabel(
        kind=_KIND_BY_PREFIX[prefix],
        number=number,
        label=label,
        rest=match.group("rest").strip(),
    )


def is_repealed(article_start: str) -> bool:
    """True when the start of an article says the whole article is repealed."""
    return _WHOLE_ARTICLE_REPEALED.match(article_start) is not None


# ---------------------------------------------------------------------------
# Section headings
# ---------------------------------------------------------------------------

# Ordinal words after normalize(). "ON BİRİNCİ" is "on" followed by "birinci".
_TENS = r"(?:on|yirmi|otuz|kirk|elli)"
_ORDINAL = (
    r"(?:birinci|ikinci|ucuncu|dorduncu|besinci|altinci|yedinci|sekizinci|dokuzuncu"
    r"|onuncu|yirminci|otuzuncu|kirkinci|ellinci)"
)
_LEVEL = r"(?P<level>kitap|kisim|bap|bolum|fasil|ayirim)"

# Matched against the normalized paragraph, so case and Turkish letters do
# not matter. The heading must be followed by a space or the end of the line.
_SECTION_HEADING = re.compile(rf"^(?:{_TENS} )?{_ORDINAL} {_LEVEL}(?: |$)")

# Real headings are short. A long paragraph is article text, even if it
# happens to start with "Birinci bölüm".
_MAX_HEADING_LENGTH = 200


@dataclass
class SectionHeading:
    """A heading such as "İKİNCİ KISIM" or "BİRİNCİ BÖLÜM Genel Hükümler"."""

    level: str          # kitap, kisim, bap, bolum, fasil or ayirim
    label: str          # as printed, for example "İKİNCİ KISIM"
    title: str | None   # text after the label on the same line, if any


def match_section_heading(paragraph: str) -> SectionHeading | None:
    """Return the section heading in a paragraph, or None."""
    if len(paragraph) > _MAX_HEADING_LENGTH:
        return None

    match = _SECTION_HEADING.match(normalize(paragraph))
    if match is None:
        return None

    # The label has as many words as the matched part. Taking that many
    # words from the original paragraph keeps the Turkish letters.
    label_word_count = len(match.group(0).split())
    words = paragraph.split()
    return SectionHeading(
        level=match.group("level"),
        label=" ".join(words[:label_word_count]),
        title=" ".join(words[label_word_count:]) or None,
    )


# ---------------------------------------------------------------------------
# Amendment notes and dates
# ---------------------------------------------------------------------------

# A note is a bracket that starts with one of these words and has a colon,
# for example "(Değişik: 24/11/2016-6763/14 md.)" or
# "(Mülga ikinci fıkra: 2/7/2012-6352/101 md.)". The \b after the word stops
# "(Ekonomik ...)" from matching as "(Ek ...)".
_NOTE = re.compile(
    r"\((?:Değişik|DEĞİŞİK|Ek|EK|Mülga|MÜLGA|İptal|İPTAL|Yeniden düzenleme)\b[^():]*:[^()]*\)"
)

# Dates are written day/month/year or day.month.year.
_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")


def find_notes(text: str) -> list[str]:
    """Return the amendment notes in a text, as printed."""
    return _NOTE.findall(text)


def dates_in(text: str) -> list[str]:
    """Return every real date in a text as an ISO string, such as "2011-02-04"."""
    found = []
    for day, month, year in _DATE.findall(text):
        try:
            found.append(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            pass  # not a real date, such as 31/2/2020
    return found
