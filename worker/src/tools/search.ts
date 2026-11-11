/** The search tool. */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import {
  findDocument,
  listDocuments,
  shortNames,
  sourceLine,
  unknownDocumentMessage,
  type DocumentRow,
} from "../documents";
import type { Env } from "../env";
import { normalize } from "../normalize";
import { errorResult, textResult } from "../result";

const DEFAULT_LIMIT = 10;
const MAX_LIMIT = 25;

/** One search hit with the columns the result needs. */
interface SearchRow {
  document_id: string;
  label: string;
  heading: string | null;
  path: string; // JSON array of strings
  repealed: number;
  excerpt: string;
}

export function registerSearch(server: McpServer, env: Env): void {
  server.registerTool(
    "search",
    {
      title: "Keyword search",
      description:
        "Find articles whose heading or text contains all the given words, in every stored document or in one. " +
        "Each word also matches longer words that start with it, so kiracı finds kiracının. " +
        "Case and Turkish letters do not matter. Results are ranked, with heading matches first. " +
        "Read the full text of a hit with get_articles.",
      inputSchema: {
        query: z.string().describe("Words to find, for example kira artış"),
        document: z.string().optional().describe("Search only this document, for example TBK"),
        limit: z
          .number()
          .int()
          .min(1)
          .max(MAX_LIMIT)
          .optional()
          .describe(`Number of results, ${DEFAULT_LIMIT} when not given`),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ query, document, limit }) => {
      const documents = await listDocuments(env.DB);

      let only: DocumentRow | null = null;
      if (document) {
        only = findDocument(documents, document);
        if (!only) {
          return errorResult(unknownDocumentMessage(document, documents));
        }
      }

      const words = normalize(query).split(" ").filter((word) => word.length > 0);
      if (words.length === 0) {
        return errorResult(`The query "${query}" has no letters or digits to search for.`);
      }

      // Each word becomes a prefix query such as kiraci*, and FTS5 joins
      // the words with AND. Normalized words hold only a-z and 0-9, so they
      // cannot be read as FTS5 operators.
      const match = words.map((word) => `${word}*`).join(" ");
      const filter = only ? "AND articles_fts.document_id = ?" : "";
      const sql =
        "SELECT a.document_id, a.label, a.heading, a.path, a.repealed, " +
        "snippet(articles_fts, 3, '[', ']', ' ... ', 16) AS excerpt " +
        "FROM articles_fts " +
        "JOIN articles a ON a.document_id = articles_fts.document_id AND a.ord = articles_fts.ord " +
        `WHERE articles_fts MATCH ? ${filter} ` +
        // Columns are document_id, ord, heading and text. Heading hits weigh three times more.
        "ORDER BY bm25(articles_fts, 0.0, 0.0, 3.0, 1.0) " +
        "LIMIT ?";
      const values: (string | number)[] = only
        ? [match, only.id, limit ?? DEFAULT_LIMIT]
        : [match, limit ?? DEFAULT_LIMIT];
      const rows = (await env.DB.prepare(sql).bind(...values).all<SearchRow>()).results;

      if (rows.length === 0) {
        return textResult(
          `No article contains all of these words (${words.join(" ")}). ` +
            "Try fewer words, or another form of a word whose ending changes, such as kitap and kitabı.",
        );
      }

      const byId = new Map(documents.map((item) => [item.id, item]));
      const hits = rows.map((row, index) => describeHit(row, index + 1, byId.get(row.document_id)));
      const usedDocuments = [...new Set(rows.map((row) => row.document_id))]
        .map((id) => byId.get(id))
        .filter((item): item is DocumentRow => item !== undefined)
        .map(sourceLine);

      return textResult(
        [
          `${rows.length} result(s) for "${query}", best first. ` +
            "Excerpts show the search form of the text, without Turkish letters.",
          hits.join("\n\n"),
          `Documents\n${usedDocuments.join("\n")}`,
        ].join("\n\n"),
      );
    },
  );
}

function describeHit(row: SearchRow, position: number, document: DocumentRow | undefined): string {
  const name = document ? (shortNames(document)[0] ?? document.id) : row.document_id;
  const heading = row.heading ? `, ${row.heading}` : "";
  const repealed = row.repealed ? " [repealed]" : "";
  const path = (JSON.parse(row.path) as string[]).join(" > ");
  const lines = [`${position}. ${name} ${row.label}${heading}${repealed}`];
  if (path) {
    lines.push(`   Section ${path}`);
  }
  lines.push(`   ${row.excerpt}`);
  return lines.join("\n");
}
