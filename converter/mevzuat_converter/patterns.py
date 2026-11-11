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

# The dash after the number is a hyphen, an en dash or an em dash. The two
# long dashes are made with chr(), so the source file holds only the plain
# hyphen and the patterns stay easy to read in any editor.
_DASHES = "-" + chr(0x2013) + chr(0x2014)

# MADDE, then the number (344, or 4/A for an inserted article), then the
# start of the article text. Most labels have a dash after the number. Some
# real files leave it out, as in "MADDE 428 İşyerinin" or "Madde 87 (Mülga",
# so a missing dash is accepted when the text goes on with a capital letter
# or a bracket. A lowercase word, as in "Madde 5 uyarınca", is not a label.
_ARTICLE_LABEL = re.compile(
    rf"^(?:(?P<prefix>{_PREFIX})\s+)?"
    r"(?:MADDE|Madde)\s+"
    r"(?P<number>\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)"
    rf"(?:\s*[{_DASHES}]\s*|\s+(?=[A-ZÇĞİÖŞÜ(])|\s*$)"
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

# A whole article is repealed when its text starts with "(Mülga:" or
# "(Başlığıyla birlikte mülga:". "(Mülga birinci fıkra: ...)" only repeals a
# part, so it does not count.
_WHOLE_ARTICLE_REPEALED = re.compile(
    r"^\(\s*(?:Başlığı(?:yla| ile) [Bb]irlikte\s+)?(?:Mülga|MÜLGA|mülga)\s*:"
)


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
# not matter. The tens can be written apart or together, as in "ON BİRİNCİ"
# and "ONBİRİNCİ", which TBK and TTK use. The heading must be followed by a
# space or the end of the line.
_SECTION_HEADING = re.compile(rf"^(?:{_TENS} ?)?{_ORDINAL} {_LEVEL}(?: |$)")

# Real headings are short. A long paragraph is article text, even if it
# happens to start with "Birinci bölüm".
_MAX_HEADING_LENGTH = 200


@dataclass
class SectionHeading:
    """A heading such as "İKİNCİ KISIM" or "BİRİNCİ BÖLÜM Genel Hükümler"."""

    level: str          # kitap, kisim, bap, bolum, fasil, ayirim or baslangic
    label: str          # as printed, for example "İKİNCİ KISIM"
    title: str | None   # text after the label on the same line, if any


def match_section_heading(paragraph: str) -> SectionHeading | None:
    """Return the section heading in a paragraph, or None."""
    if len(paragraph) > _MAX_HEADING_LENGTH:
        return None

    # TTK and TMK open with a part called BAŞLANGIÇ, which has no number
    # and no title line.
    if normalize(paragraph) == "baslangic":
        return SectionHeading(level="baslangic", label=paragraph, title=None)

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
# "(Mülga ikinci fıkra: 2/7/2012-6352/101 md.)". A note about a whole article
# can start with "Başlığıyla birlikte" or "Başlığı ile birlikte". The \b after
# the word stops "(Ekonomik ...)" from matching as "(Ek ...)".
_NOTE_WORDS = r"(?:Değişik|DEĞİŞİK|Ek|EK|Mülga|MÜLGA|İptal|İPTAL|Yeniden düzenleme)"
_WITH_HEADING = r"Başlığı(?:yla| ile) [Bb]irlikte (?:değişik|mülga|ek|Değişik|Mülga|Ek)"
_NOTE = re.compile(rf"\((?:{_WITH_HEADING}|{_NOTE_WORDS})\b[^():]*:[^()]*\)")

# Word files glue footnote numbers to the end of a note, as in
# "(Değişik:RG-28/3/2015-29309)15 Bu Yönetmelik". The number is removed.
_NOTE_WITH_NUMBER = re.compile(rf"({_NOTE.pattern})\d{{1,3}}(?=\s|$)")

# Dates are written day/month/year or day.month.year.
_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")


def find_notes(text: str) -> list[str]:
    """Return the amendment notes in a text, as printed."""
    return _NOTE.findall(text)


def strip_footnote_numbers(text: str) -> str:
    """Remove footnote numbers glued to the end of amendment notes."""
    return _NOTE_WITH_NUMBER.sub(r"\1", text)


def dates_in(text: str) -> list[str]:
    """Return every real date in a text as an ISO string, such as "2011-02-04"."""
    found = []
    for day, month, year in _DATE.findall(text):
        try:
            found.append(date(int(year), int(month), int(day)).isoformat())
        except ValueError:
            pass  # not a real date, such as 31/2/2020
    return found
