"""Read a raw file into a list of paragraphs, in reading order.

    .txt          read as it is, one paragraph per line
    .doc .docx    converted to text by LibreOffice
    .html         converted to text by LibreOffice
    .pdf          converted by pdftotext, then lines are joined into paragraphs

LibreOffice (soffice) and pdftotext (poppler-utils) are outside programs.
docs/converter.md says how to install them.
"""

import re
import subprocess
import tempfile
from pathlib import Path


class ReadError(Exception):
    """The converter could not read a raw file. The message says why."""


# Files that start with one of these bytes are UTF-16 text. On mevzuat.gov.tr
# that means HTML saved under a .doc name.
_UTF16_MARKS = (b"\xff\xfe", b"\xfe\xff")

# The longest one conversion may take, in seconds.
_TIMEOUT = 600

# Some mevzuat.gov.tr Word files hold cross references whose target is gone.
# LibreOffice prints its own error text in their place, sometimes followed by
# a footnote number, as in "II. BelirlenmesiError: Reference source not
# found34" for the heading of TBK 344. The reference only marked a footnote,
# so the error text and the number are removed. The Turkish wording appears
# when LibreOffice runs in Turkish.
_BROKEN_REFERENCE = re.compile(
    r"(?:Error: Reference source not found|Hata[:!] Başvuru kaynağı bulunamadı\.?)\d{0,3}"
)

# A line that is only a small number starts the footnotes at the bottom of
# a PDF page, when the line after it talks about an amendment.
_FOOTNOTE_NUMBER = re.compile(r"^\s*\d{1,3}\s*$")
_FOOTNOTE_TEXT = re.compile(
    r"tarihli|Resm[iî] Gazete|değiştirilmiş|eklenmiş|yürürlükten kaldırılmış|mülga",
    re.IGNORECASE,
)


def read_paragraphs(path: Path) -> list[str]:
    """Return the paragraphs of a raw file."""
    extension = path.suffix.lower().lstrip(".")
    if extension == "txt":
        return _read_text(path)
    if extension in ("doc", "docx", "html"):
        return _read_with_libreoffice(path)
    if extension == "pdf":
        return _read_pdf(path)
    raise ReadError(f"{path.name}: .{extension} files are not supported")


# ---------------------------------------------------------------------------
# Plain text
# ---------------------------------------------------------------------------


def _read_text(path: Path) -> list[str]:
    """Text copied from the mevzuat.gov.tr page, one paragraph per line.

    Empty lines are fine, the splitter skips them. "utf-8-sig" also removes
    the invisible byte order mark some editors put at the start of a file.
    """
    return path.read_text(encoding="utf-8-sig").splitlines()


# ---------------------------------------------------------------------------
# Word and HTML, through LibreOffice
# ---------------------------------------------------------------------------


def _read_with_libreoffice(path: Path) -> list[str]:
    """Convert a Word or HTML file to text with LibreOffice.

    The .doc files of mevzuat.gov.tr come in three kinds.

        real Word files       LibreOffice reads them as they are
        UTF-16 HTML           HTML text saved as UTF-16 under a .doc name
        double encoded HTML   UTF-16 HTML whose bytes were read as Windows-1254
                              text and saved as UTF-16 a second time

    UTF-16 files are decoded here and given to LibreOffice as UTF-8 HTML,
    which handles the last two kinds the same way.
    """
    raw = path.read_bytes()
    with tempfile.TemporaryDirectory() as folder:
        work = Path(folder)
        source = path
        if raw.startswith(_UTF16_MARKS):
            source = work / f"{path.stem}.html"
            source.write_text(_decode_utf16_html(raw, path.name), encoding="utf-8")
        text = _libreoffice_to_text(source, work)
    return _BROKEN_REFERENCE.sub("", text).splitlines()


def _decode_utf16_html(raw: bytes, name: str) -> str:
    """Decode UTF-16 HTML, and undo the double encoding when it is there."""
    text = raw.decode("utf-16")
    # A double encoded file starts with the byte order mark written as two
    # Windows-1254 letters, "ÿş" for little endian and "şÿ" for big endian.
    if text.startswith(("ÿş", "şÿ")):
        original = b"".join(_windows_1254_byte(ch, name) for ch in text)
        text = original.decode("utf-16")
    # The file names its old encoding in a meta tag. From here on it is UTF-8.
    return re.sub(r"charset=[\w-]+", "charset=utf-8", text, count=1)


def _windows_1254_byte(ch: str, name: str) -> bytes:
    """Return the byte that Windows-1254 shows as this character."""
    try:
        return ch.encode("cp1254")
    except UnicodeEncodeError:
        # A few byte values have no Windows-1254 letter. They come through
        # as the control character with the same number.
        if ord(ch) < 256:
            return bytes([ord(ch)])
        raise ReadError(f"{name}: looks double encoded, but cannot be decoded")


def _libreoffice_to_text(source: Path, work: Path) -> str:
    """Run LibreOffice on one file and return the text it writes."""
    out_dir = work / "out"
    command = [
        "soffice",
        "--headless",
        "--norestore",
        # A private profile, so a second LibreOffice never waits for this one.
        f"-env:UserInstallation={(work / 'profile').as_uri()}",
        "--convert-to",
        "txt:Text (encoded):UTF8",
        "--outdir",
        str(out_dir),
        str(source),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=_TIMEOUT)
    except FileNotFoundError:
        raise ReadError("LibreOffice (soffice) is not installed, see docs/converter.md")
    except subprocess.SubprocessError as error:
        raise ReadError(f"{source.name}: LibreOffice failed ({error})")

    output = out_dir / f"{source.stem}.txt"
    if not output.exists():
        raise ReadError(f"{source.name}: LibreOffice wrote no text")
    return output.read_text(encoding="utf-8-sig")


# ---------------------------------------------------------------------------
# PDF, through pdftotext
# ---------------------------------------------------------------------------


def _read_pdf(path: Path) -> list[str]:
    """Convert a PDF with pdftotext and rebuild its paragraphs.

    -layout keeps the indentation, which is how paragraphs are found. The
    footnotes at the bottom of each page are dropped. Their content is in
    the amendment notes of the text as well.
    """
    command = ["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"]
    try:
        result = subprocess.run(command, check=True, capture_output=True, timeout=_TIMEOUT)
    except FileNotFoundError:
        raise ReadError("pdftotext is not installed, see docs/converter.md")
    except subprocess.SubprocessError as error:
        raise ReadError(f"{path.name}: pdftotext failed ({error})")

    lines: list[str] = []
    for page in result.stdout.decode("utf-8").split("\f"):
        page_lines = _drop_footnotes(page.split("\n"))
        # Empty lines at the edges of a page are not paragraph breaks, because
        # a paragraph can go on from the bottom of one page to the next.
        while page_lines and not page_lines[0].strip():
            page_lines.pop(0)
        while page_lines and not page_lines[-1].strip():
            page_lines.pop()
        lines.extend(page_lines)
    return _join_lines(lines)


def _drop_footnotes(lines: list[str]) -> list[str]:
    """Remove the footnote block at the bottom of a page, if there is one."""
    for index, line in enumerate(lines[:-1]):
        if _FOOTNOTE_NUMBER.match(line) and _FOOTNOTE_TEXT.search(lines[index + 1]):
            return lines[:index]
    return lines


def _join_lines(lines: list[str]) -> list[str]:
    """Join PDF lines into paragraphs.

    In the layout text the first line of a paragraph is indented, and the
    lines that continue it start at the left edge. An empty line also ends
    a paragraph.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line.strip():
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line[0].isspace() and current:
            paragraphs.append(" ".join(current))
            current = []
        current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs
