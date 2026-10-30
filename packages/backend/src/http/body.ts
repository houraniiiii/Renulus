// SPDX-License-Identifier: MIT
import type { IncomingMessage } from "node:http";
import { parseJson } from "../dispatch/wire.ts";

export class RequestBodyError extends Error {
  readonly status: number;
  constructor(status: number) { super("invalid_request"); this.status = status; }
}

/** Strict bounded JSON, shared with exact native request parsing. */
export async function readJsonObject(request: IncomingMessage, limit: number): Promise<Record<string, unknown>> {
  const declared = request.headers["content-length"];
  if (declared !== undefined && (!/^[0-9]{1,16}$/.test(declared) || Number(declared) > limit)) throw new RequestBodyError(413);
  const parts: Buffer[] = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > limit) throw new RequestBodyError(413);
    parts.push(chunk);
  }
  try {
    const value = parseJson(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(parts)));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("object_required");
    return value as Record<string, unknown>;
  } catch { throw new RequestBodyError(422); }
}
