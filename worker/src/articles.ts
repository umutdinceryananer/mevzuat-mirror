/**
 * Reading articles from D1, and reading article references such as
 * "344", "347-352", "geçici 1", "ek 2" or "4/A".
 */
import { normalize } from "./normalize";

/** A row of the articles table, see worker/schema.sql. */
export interface ArticleRow {
  document_id: string;
  ord: number;
  kind: string;
  number: string;
  label: string;
  heading: string | null;
  path: string; // JSON array of strings
  repealed: number; // 0 or 1
  text: string;
  notes: string; // JSON array of strings
}

/** One understood piece of an article reference. */
export interface ArticleRef {
  source: string; // the piece as written, for messages
  kind: string; // madde, ek_madde, gecici_madde, ek_gecici_madde or mukerrer_madde
  from: number; // first article number
  to: number; // last article number, equal to from for a single article
  suffix: string | null; // "A" in 4/A
}

/** At most this many articles come back from one call. */
export const MAX_ARTICLES = 40;

// Words that give the kind of an article, after normalize(). Longer ones first.
const KIND_WORDS: [string, string][] = [
  ["ek gecici", "ek_gecici_madde"],
  ["gecici", "gecici_madde"],
  ["mukerrer", "mukerrer_madde"],
  ["ek", "ek_madde"],
];

// Words that add nothing to a reference, such as "madde" in "geçici madde 1".
const FILLER_WORDS = new Set(["madde", "maddesi", "maddeler", "maddeleri", "md"]);

/**
 * Read a list of references separated by commas. Returns the pieces that
 * were understood and the pieces that were not.
 */
export function parseArticleRefs(input: string): { refs: ArticleRef[]; invalid: string[] } {
  const refs: ArticleRef[] = [];
  const invalid: string[] = [];
  for (const piece of input.split(/[,;]/)) {
    const source = piece.trim();
    if (!source) {
      continue;
    }
    const ref = parseOneRef(source);
    if (ref) {
      refs.push(ref);
    } else {
      invalid.push(source);
    }
  }
  return { refs, invalid };
}

function parseOneRef(source: string): ArticleRef | null {
  // After normalize(), "Geçici Madde 1" is "gecici madde 1", "347-352" is
  // "347 352" and "4/A" is "4 a". Filler words are then removed.
  const words = normalize(source)
    .split(" ")
    .filter((word) => word && !FILLER_WORDS.has(word));
  let rest = words.join(" ");

  let kind = "madde";
  for (const [prefix, prefixKind] of KIND_WORDS) {
    if (rest.startsWith(prefix + " ")) {
      kind = prefixKind;
      rest = rest.slice(prefix.length + 1);
      break;
    }
  }

  const range = rest.match(/^(\d+) (\d+)$/);
  if (range) {
    const from = Number(range[1]);
    const to = Number(range[2]);
    return from <= to ? { source, kind, from, to, suffix: null } : null;
  }

  const single = rest.match(/^(\d+)(?: ([a-z]))?$/);
  if (single) {
    const number = Number(single[1]);
    const suffix = single[2] ? single[2].toUpperCase() : null;
    return { source, kind, from: number, to: number, suffix };
  }

  return null;
}

/**
 * Fetch the articles the references point at. Each reference keeps the
 * document order, and an article asked for twice comes back once.
 */
export async function fetchArticles(
  db: D1Database,
  documentId: string,
  refs: ArticleRef[],
): Promise<{ articles: ArticleRow[]; missing: string[]; truncated: boolean }> {
  const seen = new Set<number>();
  const articles: ArticleRow[] = [];
  const missing: string[] = [];
  let truncated = false;

  for (const ref of refs) {
    let rows: ArticleRow[];
    if (ref.from === ref.to) {
      const number = ref.suffix ? `${ref.from}/${ref.suffix}` : String(ref.from);
      const query = db
        .prepare("SELECT * FROM articles WHERE document_id = ? AND kind = ? AND number = ? ORDER BY ord")
        .bind(documentId, ref.kind, number);
      rows = (await query.all<ArticleRow>()).results;
    } else {
      // CAST reads the leading digits, so a range also takes inserted
      // articles such as 4/A.
      const query = db
        .prepare(
          "SELECT * FROM articles WHERE document_id = ? AND kind = ? " +
            "AND CAST(number AS INTEGER) BETWEEN ? AND ? ORDER BY ord",
        )
        .bind(documentId, ref.kind, ref.from, ref.to);
      rows = (await query.all<ArticleRow>()).results;
    }

    if (rows.length === 0) {
      missing.push(ref.source);
    }
    for (const row of rows) {
      if (seen.has(row.ord)) {
        continue;
      }
      if (articles.length === MAX_ARTICLES) {
        truncated = true;
        break;
      }
      seen.add(row.ord);
      articles.push(row);
    }
  }

  return { articles, missing, truncated };
}

/** The label, heading and section path of an article, on one or two lines. */
export function articleTitle(article: ArticleRow): string {
  const title = article.heading ? `${article.label}, ${article.heading}` : article.label;
  const repealed = article.repealed ? " [repealed]" : "";
  const path = (JSON.parse(article.path) as string[]).join(" > ");
  return path ? `${title}${repealed}\nSection ${path}` : `${title}${repealed}`;
}

/** An article with its title and full text. */
export function formatArticle(article: ArticleRow): string {
  return `${articleTitle(article)}\n\n${article.text}`;
}
