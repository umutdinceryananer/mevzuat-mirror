"""Read a raw file into a list of paragraphs, in reading order.

Each file type has its own reader. Plain text works now. The PDF, Word and
HTML readers come after we look at the real sample files.
"""

from pathlib import Path


class UnsupportedFormat(Exception):
    """The converter cannot read this file type yet."""


def read_paragraphs(path: Path) -> list[str]:
    """Return the paragraphs of a raw file."""
    extension = path.suffix.lower().lstrip(".")
    if extension == "txt":
        return _read_text(path)
    raise UnsupportedFormat(f"{path.name}: reading .{extension} files is not written yet")


def _read_text(path: Path) -> list[str]:
    """Text copied from the mevzuat.gov.tr page, one paragraph per line.

    Empty lines are fine, the splitter skips them. "utf-8-sig" also removes
    the invisible byte order mark some editors put at the start of a file.
    """
    return path.read_text(encoding="utf-8-sig").splitlines()
