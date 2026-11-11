/**
 * Builds the MCP server and registers its tools.
 *
 * The tools are described in docs/architecture.md, under MCP TOOLS.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { CfWorkerJsonSchemaValidator } from "@modelcontextprotocol/sdk/validation/cfworker";
import type { Env } from "./env";

// Sent to Claude when it connects. It explains what the data is and how
// old it can be, so answers name their source and date.
const INSTRUCTIONS = [
  "Turkish legislation copied by hand from mevzuat.gov.tr and stored here.",
  "The stored copy can be older than the live site. Every result shows the download date",
  "and the newest amendment date found in the text.",
  "When quoting, name the law and the article and mention the download date.",
  "For anything that may have changed recently, tell the user to check the source link.",
  "Use list_documents to see what is stored, get_outline to find articles for a question",
  "in plain language, search for keywords, and get_articles to read the full text.",
].join(" ");

export function createServer(env: Env): McpServer {
  const server = new McpServer(
    { name: "mevzuat-mirror", version: "0.1.0" },
    {
      instructions: INSTRUCTIONS,
      // The default validator builds code at run time, which Workers do not allow.
      jsonSchemaValidator: new CfWorkerJsonSchemaValidator(),
    },
  );

  // The tools are registered in later commits.
  void env;

  return server;
}
