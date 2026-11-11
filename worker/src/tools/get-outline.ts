/** The get_outline tool. */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { findDocument, listDocuments, sourceLine, unknownDocumentMessage } from "../documents";
import type { Env } from "../env";
import { normalize } from "../normalize";
import { errorResult, textResult } from "../result";

/** The columns the outline needs, without the article text. */
interface OutlineRow {
  label: string;
  heading: string | null;
  path: string; // JSON array of strings
  repealed: number;
}

export function registerGetOutline(server: McpServer, env: Env): void {
  server.registerTool(
    "get_outline",
    {
      title: "Outline of a document",
      description:
        "Section headings and article headings of one stored document, in order, without article text. " +
        "Read it to find the articles that answer a question asked in plain language, " +
        "then fetch them with get_articles.",
      inputSchema: {
        document: z.string().describe("Short name, number, id or title, for example TBK, 6098 or kanun-6098"),
        section: z
          .string()
          .optional()
          .describe('Only show sections whose heading contains this text, for example "Kira" or "İKİNCİ KISIM"'),
      },
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async ({ document, section }) => {
      const documents = await listDocuments(env.DB);
      const found = findDocument(documents, document);
      if (!found) {
        return errorResult(unknownDocumentMessage(document, documents));
      }

      const query = env.DB.prepare(
        "SELECT label, heading, path, repealed FROM articles WHERE document_id = ? ORDER BY ord",
      ).bind(found.id);
      let rows = (await query.all<OutlineRow>()).results;

      if (section) {
        const wanted = normalize(section);
        rows = rows.filter((row) => normalize((JSON.parse(row.path) as string[]).join(" ")).includes(wanted));
        if (rows.length === 0) {
          return errorResult(
            `${sourceLine(found)}\nNo section heading contains "${section}". Call get_outline without section to see all headings.`,
          );
        }
      }

      return textResult(`${sourceLine(found)}\n\n${buildOutline(rows).join("\n")}`);
    },
  );
}

/**
 * Turn the articles into an indented outline. A section heading is printed
 * once, where the section starts, and its articles follow one level deeper.
 */
function buildOutline(rows: OutlineRow[]): string[] {
  const lines: string[] = [];
  let previous: string[] = [];

  for (const row of rows) {
    const path = JSON.parse(row.path) as string[];

    // Count the headings this article shares with the article before it.
    let shared = 0;
    while (shared < path.length && shared < previous.length && path[shared] === previous[shared]) {
      shared += 1;
    }
    // Print only the headings that are new from that point on.
    for (let depth = shared; depth < path.length; depth += 1) {
      lines.push(`${"  ".repeat(depth)}${path[depth]}`);
    }

    const heading = row.heading ? `  ${row.heading}` : "";
    const repealed = row.repealed ? " [repealed]" : "";
    lines.push(`${"  ".repeat(path.length)}${row.label}${heading}${repealed}`);
    previous = path;
  }

  return lines;
}
