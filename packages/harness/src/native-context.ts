// SPDX-License-Identifier: MIT
import type { Message, ToolCallPart, ToolResultPart } from "@opencode/ai";

export type NativeContextDescriptor = Readonly<{
  id: string;
  role: Exclude<Message["role"], "system">;
}>;

export class NativeContextError extends Error {
  readonly code = "native_context_unverifiable";

  constructor(reason: string) {
    super(reason);
    this.name = "NativeContextError";
  }
}

function nativeOrigins(messages: readonly Message[]): (string | undefined)[] {
  const calls = new Map<string, { nativeId: string; call: ToolCallPart }>();
  const nativeIds = new Set<string>();
  const resultIds = new Set<string>();
  const resolveResult = (part: ToolResultPart): string => {
    const resolved = calls.get(part.id);
    if (resolved === undefined) throw new NativeContextError("Tool result has no preceding native origin");
    if (part.name !== resolved.call.name || part.namespace !== resolved.call.namespace ||
        (part.providerExecuted === true) !== (resolved.call.providerExecuted === true)) {
      throw new NativeContextError("Tool result conflicts with its declared call identity");
    }
    if (resultIds.has(part.id)) throw new NativeContextError("Duplicate tool result");
    resultIds.add(part.id);
    return resolved.nativeId;
  };
  return messages.map(message => {
    if (message.role === "system") return undefined;
    if (message.role === "tool") {
      let origin: string | undefined;
      for (const part of message.content) {
        if (part.type !== "tool-result") {
          throw new NativeContextError("Tool message includes content without a tool origin");
        }
        const resolved = resolveResult(part);
        if (origin !== undefined && origin !== resolved) {
          throw new NativeContextError("Tool message combines different native origins");
        }
        origin = resolved;
      }
      if (origin === undefined) throw new NativeContextError("Tool result has no preceding native origin");
      if (message.id !== undefined && message.id !== origin) {
        throw new NativeContextError("Tool message ID conflicts with its native origin");
      }
      return origin;
    }
    if ((message.role !== "assistant" && message.role !== "user") ||
        message.id === undefined || message.id.trim().length === 0) {
      throw new NativeContextError("Non-system message has no native ID");
    }
    if (nativeIds.has(message.id)) throw new NativeContextError("Duplicate native message ID");
    nativeIds.add(message.id);
    if (message.role === "user" && message.content.some(part => part.type === "tool-call" || part.type === "tool-result")) {
      throw new NativeContextError("User message cannot establish a tool origin");
    }
    if (message.role === "assistant") {
      for (const part of message.content) {
        if (part.type === "tool-call") {
          if (calls.has(part.id)) throw new NativeContextError("Duplicate tool-call origin");
          calls.set(part.id, { nativeId: message.id, call: part });
        } else if (part.type === "tool-result") {
          if (resolveResult(part) !== message.id || part.providerExecuted !== true) {
            throw new NativeContextError("Inline result has no provider call in its own native assistant");
          }
        }
      }
    }
    return message.id;
  });
}

/**
 * Describe non-system messages for authenticated native-context admission.
 * OpenCode 4b6fea28's to-llm-message.ts retains user/assistant IDs but emits
 * ordinary results through Message.tool without an ID; hosted results remain
 * inline. Resolve exact preceding call IDs without inventing message IDs.
 *
 * The caller supplies trusted system messages separately. Mixed-origin tool
 * batches, duplicate identities and unverified origins throw NativeContextError.
 */
export function describeNativeContext(messages: readonly Message[]): readonly NativeContextDescriptor[] {
  const origins = nativeOrigins(messages);
  return Object.freeze(messages.flatMap((message, index) => message.role === "system" ? [] : [Object.freeze({
    id: origins[index]!, role: message.role,
  })]));
}

/**
 * Validate the complete window, then select whole native-origin groups.
 * Systems stay in chronological order regardless of admission. The frozen
 * result contains original messages/content; caller data is never rewritten
 * or frozen. Unknown allowed IDs fail closed, including independent call IDs.
 */
export function selectNativeContext(
  messages: readonly Message[],
  allowedNativeIds: ReadonlySet<string> | readonly string[],
): readonly Message[] {
  const origins = nativeOrigins(messages);
  const allowed = new Set(allowedNativeIds);
  const known = new Set(origins.filter((id): id is string => id !== undefined));
  for (const id of allowed) {
    if (!known.has(id)) throw new NativeContextError("Selection includes an unknown native ID");
  }
  return Object.freeze(messages.filter((message, index) => message.role === "system" || allowed.has(origins[index]!)));
}
