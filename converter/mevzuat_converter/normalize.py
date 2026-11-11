"""Normalize text for search.

The steps are described in docs/data-format.md, under NORMALIZATION.
The worker runs the same steps on search queries, so a change here
needs the same change in the worker.
"""

import re
import unicodedata

# Any run of characters that are not a-z or 0-9.
_NOT_LETTER_OR_DIGIT = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Return text in the form used for search.

    normalize("KİRACI") returns "kiraci", and so do "kiracı" and "kiraci".
    normalize("Kira bedelinin belirlenmesi") returns "kira bedelinin belirlenmesi".
    """
    # 1. Split each letter into its base letter and its marks, then drop
    #    the marks. "ş" becomes "s", "İ" becomes "I", "â" becomes "a".
    decomposed = unicodedata.normalize("NFD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))

    # 2. The dotless "ı" has no mark to drop, so it is replaced by hand.
    #    Then everything is lowercased, which also turns "I" into "i".
    lowered = without_marks.replace("ı", "i").lower()

    # 3. Everything that is not a-z or 0-9 becomes a single space.
    return _NOT_LETTER_OR_DIGIT.sub(" ", lowered).strip()
