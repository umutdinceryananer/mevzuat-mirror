/** Bindings and secrets the worker gets from Cloudflare, see wrangler.jsonc. */
export interface Env {
  /** The D1 database built from build/d1.sql. */
  DB: D1Database;

  /**
   * Random path segment that hides the MCP endpoint. Set it with
   * `npx wrangler secret put MCP_PATH_SECRET`, or in .dev.vars for local runs.
   */
  MCP_PATH_SECRET?: string;
}
