// SPDX-License-Identifier: MIT
import { LLMRequest, type Message } from '@opencode/ai';
import { describeNativeContext } from '../../../../harness/src/native-context.ts';
import { reject } from '../../storage/contracts.ts';
import { digest } from '../../storage/schema.ts';

export const DECIMAL_PROFILES = [128000, 256000] as const;
const LEGACY = new Map<number, number>([[131072, 128000], [262144, 256000]]);

/** Read-only preview of a legacy `requested_window_tokens`; larger custom values are never expanded automatically. */
export function legacyContextPreview(value: number) {
  const mapped = LEGACY.get(value);
  if (mapped) return { status: 'mapped' as const, requested_decimal_tokens: mapped };
  if (value < DECIMAL_PROFILES[0]) return { status: 'preserved' as const, requested_decimal_tokens: value };
  return { status: 'needs_validation' as const, legacy_tokens: value };
}
export const effectiveCapacity = (requested: number, verified: number) => Math.min(requested, verified);
/** The 256K profile is refused, never silently shrunk, when the verified route cannot carry it. */
export function requireProfile(requested: number, verified: number) {
  if (requested === 256000 && verified < 256000) reject('context_window_unsupported');
}

export interface ContextCompaction {
  count(request: LLMRequest): Promise<number>;
  capacity(): Promise<number>;
  summarise(input: { transcript: string; coveredMessageIds: readonly string[] }): Promise<string>;
  /** False when the run's pins changed while the summary was produced. */
  isCurrent(): Promise<boolean>;
}
export interface ContextPins { history: readonly { runId: string; publicationDigest: string }[]; memory: readonly unknown[]; consumed: readonly unknown[] }
const SUMMARY = 'renulus-context-summary/1';
const marker = (message: Message): Message => ({ ...message, content: message.content.map(part => part.type === 'media'
  ? { type: 'text', text: '[earlier image or file omitted]' } : part) } as Message);
function transcript(messages: readonly Message[]) {
  return messages.map(m => m.role + ': ' + m.content.map(p => p.type === 'text' ? p.text : p.type === 'media' ? '[media]'
    : p.type === 'tool-call' ? `[tool call ${p.name}]` : p.type === 'tool-result' ? `[tool result ${p.name}]` : '').join(' ')).join('\n');
}
/** Whole native-origin groups: the last exchange (with any unresolved tool call) is always kept, then complete older groups
 * while the counted request fits; the rest becomes one validated summary. Exact older text stays in renulus_history_range. */
export async function compactContext(request: LLMRequest, context: ContextCompaction, pins: ContextPins): Promise<LLMRequest> {
  const capacity = await context.capacity();
  if (!Number.isInteger(capacity) || capacity <= 0) reject('context_window_unavailable');
  if (await context.count(request) <= capacity) return request;
  const described = describeNativeContext(request.messages), groups: { id: string | null; messages: Message[] }[] = [];
  let at = 0;
  for (const message of request.messages) {
    const id = message.role === 'system' ? null : described[at++]!.id, last = groups.at(-1);
    if (id !== null && last?.id === id) last.messages.push(message); else groups.push({ id, messages: [message] });
  }
  const tail = Math.max(groups.findLastIndex(g => g.messages[0]!.role === 'user'), 0);
  const build = (from: number, summary?: string) => LLMRequest.update(request, {
    system: summary ? [...request.system, { type: 'text', text: summary }] : request.system,
    messages: groups.slice(from).flatMap((g, i) => from + i < tail ? g.messages.map(marker) : g.messages) });
  let from = tail;
  while (from > 0 && await context.count(build(from - 1, 'x'.repeat(2048))) <= capacity) from--;
  const covered = groups.slice(0, from).flatMap(g => g.id === null ? [] : [g]);
  if (!covered.length) return await context.count(build(from)) <= capacity ? build(from) : reject('context_compaction_blocked');
  const coveredMessageIds = covered.map(g => g.id!);
  let body = '';
  try { body = (await context.summarise({ transcript: transcript(covered.flatMap(g => g.messages)), coveredMessageIds })).trim(); } catch { /* blocked below */ }
  if (!body || !await context.isCurrent()) return reject('context_compaction_blocked');
  const receipt = { version: SUMMARY, covered_message_ids: coveredMessageIds, digest: digest(body),
    source_revisions: pins.history.map(h => h.publicationDigest), fact_revisions: pins.memory.length + pins.consumed.length };
  const candidate = build(from, `Earlier conversation summary (not independent evidence; exact text via renulus_history_range). ${JSON.stringify(receipt)}
${body}`);
  return await context.count(candidate) <= capacity ? candidate : reject('context_compaction_blocked');
}
