/** The get_articles tool. */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { fetchArticles, formatArticle, MAX_ARTICLES, parseArticleRefs } from "../articles";
import { findDocument, listDocuments, sourceLine, unknownDocumentMessage } from "../documents";
import type { Env } from "../env";
import { errorResult, textResult } from "../result";

export function registerGetArticles(server: McpServer, env: Env): void {
  server.registerTool(
    "get_articles",
    {
      title: "Read articles",
      description:
        "Return the full text of articles of one stored document, with heading, section and amendment notes. " +
        `At most ${MAX_ARTICLES} articles per call.`,
      inputSchema: {
        document: z.string().describe("Short name, number, id or title, for example TBK, 6098 or kanun-6098"),
        articles: z
          .string()
          .describe('Article references separated by commas, for example "344", "347-352", "geçici 1", "ek 2", "4/A"'),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ document, articles }) => {
      const documents = await listDocuments(env.DB);
      const found = findDocument(documents, document);
      if (!found) {
        return errorResult(unknownDocumentMessage(document, documents));
      }

      const { refs, invalid } = parseArticleRefs(articles);
      if (refs.length === 0) {
        return errorResult(
          `Could not read the article references "${articles}". ` +
            'Use forms such as "344", "347-352", "geçici 1", "ek 2" or "4/A".',
        );
      }

      const result = await fetchArticles(env.DB, found.id, refs);

      const remarks: string[] = [];
      if (invalid.length > 0) {
        remarks.push(`Not understood ${invalid.join(", ")}.`);
      }
      if (result.missing.length > 0) {
        remarks.push(`Not found in ${found.id} ${result.missing.join(", ")}.`);
      }
      if (result.truncated) {
        remarks.push(`Only the first ${MAX_ARTICLES} articles are shown. Ask for a smaller range.`);
      }

      if (result.articles.length === 0) {
        return errorResult([sourceLine(found), ...remarks].join("\n"));
      }

      const parts = [sourceLine(found), ...result.articles.map(formatArticle)];
      if (remarks.length > 0) {
        parts.push(remarks.join("\n"));
      }
      return textResult(parts.join("\n\n---\n\n"));
    },
  );
}
