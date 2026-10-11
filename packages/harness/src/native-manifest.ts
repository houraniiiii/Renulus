// SPDX-License-Identifier: MIT
import { createHash } from "node:crypto";
import { AIError, InvalidRequestError, Media, type LLMRequest } from "@opencode/ai";
import { ProviderShared } from "@opencode/ai/protocols/shared";

export type NativePart = Readonly<
  { type: "text"; text: string } |
  { type: "image"; media_type: "image/png" | "image/jpeg" | "image/webp"; sha256: string;
    bytes: number; detail: null | "auto" | "low" | "high" } |
  { type: "tool-call"; id: string; name: string; arguments_json: string } |
  { type: "tool-result"; id: string; output_text: string }
>;
export interface NativeManifest {
  readonly version: 1;
  readonly system: string;
  readonly messages: readonly Readonly<{ role: "user" | "assistant" | "tool"; content: readonly NativePart[] }>[];
  readonly tools: readonly Readonly<{ name: string; description: string; parameters_json: string }>[];
}

const deny: () => never = () => {
  throw new AIError({ reason: new InvalidRequestError({ message: "Native input cannot be verified for dispatch." }) });
};
const populated = (value: object | undefined) => value !== undefined && Object.keys(value).length !== 0;
function strictJson(value: unknown): string {
  try {
    const visited = new Set<object>();
    const check = (item: unknown, depth = 0): void => {
      if (depth > 100) deny();
      if (item === null || typeof item === "string" || typeof item === "boolean") return;
      if (typeof item === "number") { if (!Number.isFinite(item)) deny(); return; }
      if (typeof item !== "object" || visited.has(item)) deny();
      if (!Array.isArray(item) && ![Object.prototype, null].includes(Object.getPrototypeOf(item))) deny();
      if (Object.getOwnPropertySymbols(item).length) deny();
      visited.add(item);
      if (Array.isArray(item)) {
        if (Object.getPrototypeOf(item) !== Array.prototype) deny();
        const properties = Object.getOwnPropertyDescriptors(item);
        if (Object.keys(properties).length !== item.length + 1) deny();
        for (let i = 0; i < item.length; i++) {
          const property = properties[String(i)];
          if (!property || !Object.hasOwn(property, "value") || !property.enumerable) deny();
          check(property.value, depth + 1);
        }
      } else {
        for (const property of Object.values(Object.getOwnPropertyDescriptors(item))) {
          if (!Object.hasOwn(property, "value")) deny();
          check(property.value, depth + 1);
        }
      }
      visited.delete(item);
    };
    check(value);
    const encoded = JSON.stringify(value);
    return encoded === undefined ? deny() : encoded;
  } catch { return deny(); }
}
function freeze<T>(value: T): T {
  if (value !== null && typeof value === "object") {
    for (const item of Object.values(value)) freeze(item);
    Object.freeze(value);
  }
  return value;
}

/** Capture only the admitted pre-filter native snapshot, never model arguments.
 * Python owns counting, evidence, authority and comparison with exact HTTP bytes. */
export function captureNativeManifest(request: LLMRequest): NativeManifest {
  const calls = new Map<string, string>();
  const seen = new Set<string>();
  const names = new Set<string>();
  const tools = request.tools.map(tool => {
    if (tool.type !== "tool" || tool.native !== undefined || names.has(tool.name) ||
        !tool.inputSchema || typeof tool.inputSchema !== "object" || Array.isArray(tool.inputSchema)) deny();
    names.add(tool.name);
    return { name: tool.name, description: tool.description, parameters_json: strictJson(tool.inputSchema) };
  });
  const messages = request.messages.map(message => {
    if (!["user", "assistant", "tool"].includes(message.role) || message.native !== undefined ||
        populated(message.providerMetadata) || (calls.size && message.role !== "tool")) deny();
    const content: NativePart[] = [];
    for (const part of message.content) {
      if (part.type === "text") {
        if (message.role === "tool" || populated(part.providerMetadata)) deny();
        const previous = content.at(-1);
        if (previous?.type === "text") content[content.length - 1] = { type: "text", text: previous.text + part.text };
        else content.push({ type: "text", text: part.text });
      } else if (part.type === "media") {
        const asset = part.media;
        const source = asset.source;
        if (message.role !== "user" || !["image/png", "image/jpeg", "image/webp"].includes(asset.mediaType) ||
            !["bytes", "base64"].includes(source.type)) deny();
        let bytes: Uint8Array;
        if (source.type === "bytes") bytes = source.data;
        else if (source.type === "base64") {
          bytes = Buffer.from(source.data, "base64");
          if (Buffer.from(bytes).toString("base64") !== source.data) deny();
        } else return deny();
        if (!bytes.length || bytes.length > 8 * 1024 * 1024 || Media.detectMediaType(bytes) !== asset.mediaType) deny();
        const metadata = part.providerMetadata;
        const metadataKey = request.model.route.providerMetadataKey ?? "openresponses";
        let detail: null | "auto" | "low" | "high" = null;
        if (populated(metadata)) {
          const namespace = metadata![metadataKey];
          if (request.model.route.protocol !== "openai-responses" ||
              Object.keys(metadata!).join(",") !== metadataKey || !namespace ||
              Object.keys(namespace).join(",") !== "detail" ||
              !["auto", "low", "high"].includes(namespace.detail as string)) deny();
          detail = namespace.detail as "auto" | "low" | "high";
        }
        content.push({ type: "image", media_type: asset.mediaType as "image/png" | "image/jpeg" | "image/webp",
          sha256: createHash("sha256").update(bytes).digest("hex"), bytes: bytes.length,
          detail: detail as null | "auto" | "low" | "high" });
      } else if (part.type === "tool-call") {
        if (message.role !== "assistant" || part.providerExecuted === true || part.namespace !== undefined ||
            populated(part.providerMetadata) || seen.has(part.id)) deny();
        seen.add(part.id);
        calls.set(part.id, part.name);
        content.push({ type: "tool-call", id: part.id, name: part.name, arguments_json: strictJson(part.input) });
      } else if (part.type === "tool-result") {
        if (message.role !== "tool" || part.providerExecuted === true || part.namespace !== undefined ||
            populated(part.providerMetadata) || calls.get(part.id) !== part.name || part.result.type === "content") deny();
        // Validate structured results before the pinned encoder can coerce them.
        if (part.result.type !== "text") strictJson(part.result.value);
        else if (typeof part.result.value !== "string") deny();
        calls.delete(part.id);
        content.push({ type: "tool-result", id: part.id, output_text: ProviderShared.toolResultText(part) });
      } else deny();
    }
    return { role: message.role as "user" | "assistant" | "tool", content };
  });
  if (calls.size || !messages.length) deny();
  const manifest = { version: 1 as const, system: ProviderShared.joinText(request.system), messages, tools };
  if (Buffer.byteLength(strictJson(manifest)) > 1_048_576) deny();
  return freeze(manifest);
}
