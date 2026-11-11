/** Reading documents from D1 and finding the one a tool call means. */
import { normalize } from "./normalize";

/** A row of the documents table, see worker/schema.sql. */
export interface DocumentRow {
  id: string;
  type: string;
  number: string;
  title: string;
  short_names: string; // JSON array of strings
  source_url: string;
  accepted_at: string | null;
  official_gazette_date: string | null;
  official_gazette_number: string | null;
  downloaded_at: string;
  latest_amendment_seen: string | null;
  converter_version: string;
  article_count: number;
}

export async function listDocuments(db: D1Database): Promise<DocumentRow[]> {
  const { results } = await db.prepare("SELECT * FROM documents ORDER BY title").all<DocumentRow>();
  return results;
}

export function shortNames(document: DocumentRow): string[] {
  return JSON.parse(document.short_names) as string[];
}

/**
 * Find the document someone means by "TBK", "6098", "kanun-6098" or the
 * title. Case and Turkish letters do not matter. Returns null when no
 * document matches, or when more than one does.
 */
export function findDocument(documents: DocumentRow[], reference: string): DocumentRow | null {
  const wanted = normalize(reference);
  if (!wanted) {
    return null;
  }

  const exact = documents.filter((document) =>
    [document.id, document.number, document.title, ...shortNames(document)].some(
      (name) => normalize(name) === wanted,
    ),
  );
  if (exact.length > 0) {
    return exact.length === 1 ? exact[0] : null;
  }

  // "6098 sayılı kanun" names the document by its number among other words.
  const words = wanted.split(" ");
  const byNumber = documents.filter((document) => words.includes(normalize(document.number)));
  return byNumber.length === 1 ? byNumber[0] : null;
}

/** One line that names a document, how old the copy is, and where it came from. */
export function sourceLine(document: DocumentRow): string {
  const names = [document.id, ...shortNames(document)].join(", ");
  const amendment = document.latest_amendment_seen ?? "none found";
  return (
    `${document.title} (${names}). Downloaded ${document.downloaded_at}, ` +
    `latest amendment seen ${amendment}. Source ${document.source_url}`
  );
}

/** Message for a document name that matched nothing, listing the names that work. */
export function unknownDocumentMessage(reference: string, documents: DocumentRow[]): string {
  if (documents.length === 0) {
    return "No documents are stored yet.";
  }
  const known = documents.map(
    (document) => `${document.id} (${[document.title, ...shortNames(document)].join(", ")})`,
  );
  return `No single stored document matches "${reference}". Stored documents are ${known.join("; ")}.`;
}
