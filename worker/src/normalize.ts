/**
 * Normalize text for search and for matching names.
 *
 * Same steps as converter/mevzuat_converter/normalize.py, see NORMALIZATION
 * in docs/data-format.md. A change here needs the same change there.
 */
export function normalize(text: string): string {
  return (
    text
      // 1. Split each letter into its base letter and its marks, then drop
      //    the marks. "ş" becomes "s", "İ" becomes "I", "â" becomes "a".
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      // 2. The dotless "ı" has no mark to drop, so it is replaced by hand.
      .replace(/ı/g, "i")
      .toLowerCase()
      // 3. Everything that is not a-z or 0-9 becomes a single space.
      .replace(/[^a-z0-9]+/g, " ")
      .trim()
  );
}
