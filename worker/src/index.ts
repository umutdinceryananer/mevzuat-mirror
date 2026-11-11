/**
 * Entry point of the worker.
 *
 * The MCP endpoint lives at /<MCP_PATH_SECRET>/mcp. Every other path gets
 * 404, so nobody finds the endpoint without the secret.
 */
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import type { Env } from "./env";
import { createServer } from "./server";

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const secret = env.MCP_PATH_SECRET;
    if (!secret) {
      return new Response("Server is not configured.", { status: 503 });
    }

    const { pathname } = new URL(request.url);
    if (pathname !== `/${secret}/mcp`) {
      return new Response("Not found.", { status: 404 });
    }

    // Stateless mode. Every request gets a new server and transport, and
    // nothing is kept between requests. enableJsonResponse answers with
    // plain JSON instead of an event stream, which is enough for these tools.
    const server = createServer(env);
    const transport = new WebStandardStreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    await server.connect(transport);
    return transport.handleRequest(request);
  },
} satisfies ExportedHandler<Env>;
