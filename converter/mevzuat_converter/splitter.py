"""Split the paragraphs of a legislation text into articles.

The input is the text as a list of paragraphs in reading order. Reading a
PDF or Word file into paragraphs is a separate step.

The output has three parts.

    preamble   paragraphs before the first section or article, where the
               document header with its dates and numbers lives
    articles   one Article per MADDE, with its heading and section path
    trailer    paragraphs after the articles, such as the list of amending
               legislation at the end of mevzuat.gov.tr files

The rules come from the 18 documents downloaded in November 2026. The forms
they handle are listed in docs/data-format.md.
"""

import re
from dataclasses import dataclass, field

from .normalize import normalize
from .patterns import find_notes, is_repealed, match_article_label, match_section_heading

# Heading lines printed between two articles. At most this many are moved
# from the end of one article to the heading of the next.
_MAX_HEADING_LINES = 3

# Headings are short. Longer paragraphs are always article text.
_MAX_HEADING_LENGTH = 150

# Word files sometimes hold an invisible soft hyphen, as in "MADDE 464" plus
# a soft hyphen plus "-". It is removed from every paragraph.
_SOFT_HYPHEN = chr(0x00AD)

# Letters of symbol fonts land in the Unicode private use area, such as a
# stray U+F074 at the end of a law. They carry no text and are removed.
_PRIVATE_USE = range(0xE000, 0xF900)

# A line of underscores. In Word files the footnotes of a page, or of the
# whole document, follow it.
_UNDERLINE = re.compile(r"_{3,}")

# A footnote after the underline, such as "(1) 12/12/2019 tarihli ve 30976
# sayılı Resmî Gazete’de yayımlanan ..." or "(3) Bu değişiklik yayımı
# tarihinden 1 ay sonra yürürlüğe girer.".
_FOOTNOTE = re.compile(
    r"^\(\d+\).*(?:tarihli|Resm[iî] Gazete|yürürlüğe gir|maddesiyle|değiştiril|eklen|kaldırıl|ibare|teselsül)"
)

# Page numbers of a transcribed print, such as 5995, 5996, ... in the
# Ticaret Sicili Yönetmeliği. A run of at least this many paragraphs that
# hold only a three to five digit number, each one or two more than the
# last, counts as page numbers.
_PAGE_RUN = 5

# Paragraphs that end the articles. The first one found starts the trailer,
# and everything after it goes there too. See END OF ARTICLES in
# docs/data-format.md.

# Titles written in capitals, matched on normalized text. The first one heads
# the list of amending legislation, as in "6098 SAYILI KANUNA EK VE DEĞİŞİKLİK
# GETİREN MEVZUATIN ...". The second heads provisions of amending laws that
# could not be worked into the text, as in "... KANUNA İŞLENEMEYEN HÜKÜMLER".
_CAPITAL_TRAILER_TITLES = ("ek ve degisiklik getiren", "islenemeyen hukumler")

# A title in capitals that names a table, schedule or list, such as "...
# PARA CEZASI MİKTARLARI İLE İLGİLİ TABLO", matched on normalized text.
_CAPITAL_TABLE_TITLE = re.compile(r"\b(?:tablo|tablosu|cetvel|cetveli|liste|listesi)\b")

# An annexed schedule or list, such as "(I) SAYILI CETVEL", "I Sayılı Cetvel"
# or "(1) SAYILI LİSTE", matched on normalized text.
_SCHEDULE_TITLE = re.compile(r"^(?:[ivx]+|\d+) sayili (?:cetvel|liste)\b")

# The table of Resmi Gazete issues at the end of a regulation, as in
# "Yönetmeliğin Yayımlandığı Resmî Gazete'nin", matched on normalized text.
_GAZETTE_TABLE = re.compile(r"^\w+ yayimlandigi resmi gazete")

# An annex title on its own line, such as "EK", "EK-5" or "EK-1 (Değişik: ...)".
_ANNEX = re.compile(
    r"\(?\s*(?:EK|EKLER)(?:\s*[-" + chr(0x2013) + r"]?\s*\d+)?\s*\)?(?:\s*\(.*\))?"
)

# A link text copied from the web page, never part of the law.
_WEB_LINK_TEXT = re.compile(r"^ek(?:i|leri) icin tiklayiniz$")


@dataclass
class Article:
    """One article and the paragraphs of its body."""

    order: int            # position in the document, starting at 1
    kind: str             # see patterns.ArticleLabel
    number: str
    label: str
    heading: str | None   # heading lines above the label, joined with " / "
    path: list[str]       # section headings above the article, outermost first
    repealed: bool
    paragraphs: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The article body, paragraphs separated by one blank line."""
        return "\n\n".join(self.paragraphs)


@dataclass
class SplitResult:
    preamble: list[str]
    articles: list[Article]
    trailer: list[str]
    footnotes: list[str] = field(default_factory=list)  # taken out of the article text


def looks_like_heading(paragraph: str) -> bool:
    """Guess whether a paragraph is a heading rather than article text.

    A heading such as "Kira bedelinin belirlenmesi" is short and does not
    end like a sentence. Article text usually ends with ".", ":", ";" or ","
    and often starts with a paragraph number such as "(2)" or a list mark
    such as "a)". Amendment notes start with "(" too.
    """
    if len(paragraph) > _MAX_HEADING_LENGTH:
        return False
    if paragraph.endswith((".", ":", ";", ",")):
        return False
    if paragraph.startswith("("):
        return False
    if re.match(r"^[a-zçğıöşü]{1,2}\)", paragraph):
        return False
    return True


def split_articles(paragraphs: list[str]) -> SplitResult:
    """Split paragraphs into preamble, articles and trailer."""
    preamble: list[str] = []
    articles: list[Article] = []
    trailer: list[str] = []
    footnotes: list[str] = []
    page_numbers = _page_number_positions(paragraphs)
    in_footnotes = False  # True after a line of underscores, while footnotes follow

    # Section headings above the current position, outermost first. Each
    # item is (level, text), such as ("kisim", "İKİNCİ KISIM Özel Borç İlişkileri").
    path: list[tuple[str, str]] = []

    current: Article | None = None    # the article that receives new paragraphs
    pending_headings: list[str] = []  # heading lines before the first article of a section
    waiting_for_title = False         # True right after a section label printed without a title
    started = False                   # True after the first section heading or article label
    in_trailer = False

    for position, raw in enumerate(paragraphs):
        paragraph = _clean(raw)
        if not paragraph or position in page_numbers or _WEB_LINK_TEXT.match(normalize(paragraph)):
            continue

        if in_trailer or (started and _is_trailer_start(paragraph)):
            if not in_trailer and current is not None:
                # The first lines of a title in capitals, or a note about the
                # annex, may have landed in the last article already.
                trailer.extend(_take_trailing_titles(current))
            in_trailer = True
            trailer.append(paragraph)
            continue

        if started and _UNDERLINE.fullmatch(paragraph):
            in_footnotes = True
            continue
        if in_footnotes:
            if _FOOTNOTE.match(paragraph):
                footnotes.append(paragraph)
                continue
            in_footnotes = False

        section = match_section_heading(paragraph)
        if section is not None:
            started = True
            current = None
            pending_headings = []
            path = _enter_section(path, section.level, section.label, section.title)
            # BAŞLANGIÇ has no title line. Other headings may have one next.
            waiting_for_title = section.title is None and section.level != "baslangic"
            continue

        label = match_article_label(paragraph)
        if label is not None:
            if current is not None:
                heading_lines = _take_trailing_headings(current)
            elif started:
                heading_lines = pending_headings
            else:
                # The first article of a text without sections. Its heading
                # is at the end of the preamble, after the header lines.
                heading_lines = _take_preamble_headings(preamble)
            started = True
            waiting_for_title = False
            pending_headings = []

            current = Article(
                order=len(articles) + 1,
                kind=label.kind,
                number=label.number,
                label=label.label,
                heading=" / ".join(heading_lines) or None,
                path=[text for _level, text in path],
                repealed=is_repealed(label.rest),
            )
            if label.rest:
                current.paragraphs.append(label.rest)
            articles.append(current)
            continue

        if not started:
            preamble.append(paragraph)
        elif waiting_for_title:
            # The line right after "BİRİNCİ KISIM" is the title of that section.
            level, text = path[-1]
            path[-1] = (level, f"{text} {paragraph}")
            waiting_for_title = False
        elif current is None:
            pending_headings.append(paragraph)
        else:
            current.paragraphs.append(paragraph)

    return SplitResult(preamble=preamble, articles=articles, trailer=trailer, footnotes=footnotes)


def _clean(raw: str) -> str:
    """Drop soft hyphens and private use letters, then collapse all whitespace."""
    kept = (ch for ch in raw if ch != _SOFT_HYPHEN and ord(ch) not in _PRIVATE_USE)
    return " ".join("".join(kept).split())


def _page_number_positions(paragraphs: list[str]) -> set[int]:
    """Return the positions of paragraphs that are page numbers. See _PAGE_RUN."""
    found: set[int] = set()
    run: list[int] = []
    last_value = None
    for position, paragraph in enumerate(paragraphs):
        text = paragraph.strip()
        if not (text.isdigit() and 3 <= len(text) <= 5):
            continue
        value = int(text)
        if last_value is not None and value - last_value in (1, 2):
            run.append(position)
        else:
            if len(run) >= _PAGE_RUN:
                found.update(run)
            run = [position]
        last_value = value
    if len(run) >= _PAGE_RUN:
        found.update(run)
    return found


def _is_trailer_start(paragraph: str) -> bool:
    """True when a paragraph ends the articles of a document."""
    normalized = normalize(paragraph)
    if _written_in_capitals(paragraph):
        if any(title in normalized for title in _CAPITAL_TRAILER_TITLES):
            return True
        if len(paragraph) < 200 and _CAPITAL_TABLE_TITLE.search(normalized):
            return True
    if _ANNEX.fullmatch(paragraph):
        return True
    if len(paragraph) < 80 and _SCHEDULE_TITLE.match(normalized):
        return True
    return len(paragraph) < 120 and _GAZETTE_TABLE.match(normalized) is not None


def _written_in_capitals(paragraph: str) -> bool:
    """True when a paragraph has letters and none of them is lowercase."""
    return any(ch.isalpha() for ch in paragraph) and not any(ch.islower() for ch in paragraph)


def _take_trailing_titles(article: Article) -> list[str]:
    """Remove the start of a closing part from the end of an article.

    A title in capitals can take two lines, and only the second one may be
    recognized. A note such as "(Değişik: ...)" can stand right before an
    annex. Up to three such lines move to the trailer. The first paragraph
    of the article never moves.
    """
    taken: list[str] = []
    while len(article.paragraphs) > 1 and len(taken) < 3:
        last = article.paragraphs[-1]
        if not (_written_in_capitals(last) or find_notes(last) == [last]):
            break
        taken.append(article.paragraphs.pop())
    taken.reverse()
    return taken


def _enter_section(path: list[tuple[str, str]], level: str, label: str, title: str | None) -> list[tuple[str, str]]:
    """Return the path after a new section heading.

    A heading closes the open section of the same level and everything
    inside it, so "İKİNCİ BÖLÜM" replaces "BİRİNCİ BÖLÜM" and drops its
    AYIRIM. A level that is not in the path yet opens inside the current one.
    """
    # BAŞLANGIÇ holds only the opening articles. Any other section ends it.
    path = [item for item in path if item[0] != "baslangic"]
    levels = [item_level for item_level, _text in path]
    if level in levels:
        path = path[: levels.index(level)]
    text = label if title is None else f"{label} {title}"
    return path + [(level, text)]


def _take_preamble_headings(preamble: list[str]) -> list[str]:
    """Remove the heading of the first article from the end of the preamble.

    Header lines such as "Kabul Tarihi : 11/1/2011" have a colon, and the
    title of the law is in capitals, so neither is taken.
    """
    taken: list[str] = []
    while preamble and len(taken) < _MAX_HEADING_LINES:
        last = preamble[-1]
        if not looks_like_heading(last) or ":" in last or _written_in_capitals(last):
            break
        taken.append(preamble.pop())
    taken.reverse()
    return taken


def _take_trailing_headings(article: Article) -> list[str]:
    """Remove heading lines from the end of an article and return them.

    The heading of the next article is printed right after the body of this
    one, so it first lands here. The first paragraph is never taken, because
    it is the start of the body.
    """
    taken: list[str] = []
    while (
        len(article.paragraphs) > 1
        and len(taken) < _MAX_HEADING_LINES
        and looks_like_heading(article.paragraphs[-1])
    ):
        taken.append(article.paragraphs.pop())
    taken.reverse()
    return taken
