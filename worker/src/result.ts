/** Small helpers that wrap text into an MCP tool result. */

export function textResult(text: string) {
  return { content: [{ type: "text" as const, text }] };
}

/** A result Claude sees as a failed call, so it can fix its input and retry. */
export function errorResult(text: string) {
  return { content: [{ type: "text" as const, text }], isError: true };
}
