"""Split the paragraphs of a legislation text into articles.

The input is the text as a list of paragraphs in reading order. Reading a
PDF or Word file into paragraphs is a separate step.

The output has three parts.

    preamble   paragraphs before the first section or article, where the
               document header with its dates and numbers lives
    articles   one Article per MADDE, with its heading and section path
    trailer    paragraphs after the articles, such as the list of amending
               legislation at the end of mevzuat.gov.tr files

These rules are a first version and will change after we see real files.
"""

import re
from dataclasses import dataclass, field

from .normalize import normalize
from .patterns import is_repealed, match_article_label, match_section_heading

# Heading lines printed between two articles. At most this many are moved
# from the end of one article to the heading of the next.
_MAX_HEADING_LINES = 3

# Headings are short. Longer paragraphs are always article text.
_MAX_HEADING_LENGTH = 150

# Word files sometimes hold an invisible soft hyphen, as in "MADDE 464" plus
# a soft hyphen plus "-". It is removed from every paragraph.
_SOFT_HYPHEN = chr(0x00AD)

# A paragraph whose normalized text contains both of these starts the list
# of amending legislation at the end of a file. Everything from there on
# goes to the trailer.
_TRAILER_MARKERS = ("degisiklik getiren mevzuatin", "liste")


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

    # Section headings above the current position, outermost first. Each
    # item is (level, text), such as ("kisim", "İKİNCİ KISIM Özel Borç İlişkileri").
    path: list[tuple[str, str]] = []

    current: Article | None = None    # the article that receives new paragraphs
    pending_headings: list[str] = []  # heading lines before the first article of a section
    waiting_for_title = False         # True right after a section label printed without a title
    started = False                   # True after the first section heading or article label
    in_trailer = False

    for raw in paragraphs:
        # Drop soft hyphens, then collapse line breaks and repeated spaces.
        paragraph = " ".join(raw.replace(_SOFT_HYPHEN, "").split())
        if not paragraph:
            continue

        if in_trailer or (started and _is_trailer_start(paragraph)):
            in_trailer = True
            trailer.append(paragraph)
            continue

        section = match_section_heading(paragraph)
        if section is not None:
            started = True
            current = None
            pending_headings = []
            path = _enter_section(path, section.level, section.label, section.title)
            waiting_for_title = section.title is None
            continue

        label = match_article_label(paragraph)
        if label is not None:
            started = True
            waiting_for_title = False
            if current is None:
                heading_lines = pending_headings
            else:
                heading_lines = _take_trailing_headings(current)
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

    return SplitResult(preamble=preamble, articles=articles, trailer=trailer)


def _is_trailer_start(paragraph: str) -> bool:
    normalized = normalize(paragraph)
    return all(marker in normalized for marker in _TRAILER_MARKERS)


def _enter_section(path: list[tuple[str, str]], level: str, label: str, title: str | None) -> list[tuple[str, str]]:
    """Return the path after a new section heading.

    A heading closes the open section of the same level and everything
    inside it, so "İKİNCİ BÖLÜM" replaces "BİRİNCİ BÖLÜM" and drops its
    AYIRIM. A level that is not in the path yet opens inside the current one.
    """
    levels = [item_level for item_level, _text in path]
    if level in levels:
        path = path[: levels.index(level)]
    text = label if title is None else f"{label} {title}"
    return path + [(level, text)]


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
