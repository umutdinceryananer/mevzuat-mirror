/** The list_documents tool. */
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { listDocuments, shortNames, type DocumentRow } from "../documents";
import type { Env } from "../env";
import { textResult } from "../result";

export function registerListDocuments(server: McpServer, env: Env): void {
  server.registerTool(
    "list_documents",
    {
      title: "List stored legislation",
      description:
        "List every stored document with its names, Resmi Gazete date, download date, " +
        "newest amendment date found in the text, article count and mevzuat.gov.tr link.",
      annotations: { readOnlyHint: true, openWorldHint: false },
    },
    async () => {
      const documents = await listDocuments(env.DB);
      if (documents.length === 0) {
        return textResult("No documents are stored yet.");
      }
      const blocks = documents.map(describeDocument);
      return textResult(`${documents.length} stored document(s).\n\n${blocks.join("\n\n")}`);
    },
  );
}

function describeDocument(document: DocumentRow): string {
  const gazette = document.official_gazette_date
    ? `, Resmi Gazete ${document.official_gazette_date} issue ${document.official_gazette_number ?? "unknown"}`
    : "";
  return [
    document.title,
    `  names ${[document.id, ...shortNames(document)].join(", ")}`,
    `  ${document.type} ${document.number}${gazette}`,
    `  downloaded ${document.downloaded_at}, latest amendment seen ${document.latest_amendment_seen ?? "none found"}, ` +
      `${document.article_count} articles`,
    `  source ${document.source_url}`,
  ].join("\n");
}
