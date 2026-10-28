// SPDX-License-Identifier: MIT
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical, digest } from '../../storage/schema.ts';
import type { FindScope, LearningStorage, ReadView } from './contracts.ts';

/** Read-only owning-host port; no SQLite handle or native-store pathname escapes. */
export interface NativeMessage {
  id: string; type: string; text?: string; content?: readonly { type: string; text?: string }[];
  metadata?: Readonly<Record<string, unknown>>; time?: { completed?: unknown }; error?: unknown;
}
export interface NativePage {
  session: { id: string; outcome?: string; metadata?: Readonly<Record<string, unknown>> };
  execution: 'active' | 'held' | 'settled'; messages: readonly NativeMessage[];
  cursor: { next?: string | null; [key: string]: unknown };
}
export interface NativeReader {
  observe(sessionId: string, page: { limit: number; order?: 'asc'; cursor?: string }): Promise<NativePage>;
}
function owned(view: ReadView, page: NativePage) {
  if (page.session.id !== view.mapping?.runtime.session_id ||
    page.session.metadata?.renulusProfile !== view.mapping.runtime.profile_id ||
    page.session.metadata?.renulusStore !== view.mapping.runtime.store_id) reject('learning_native_identity_conflict');
  if (Buffer.byteLength(JSON.stringify(page)) > 512 * 1024) reject('learning_native_page_limit');
}
export function nativeText(message: NativeMessage) {
  if (message.type === 'user') return message.text ?? '';
  return (message.content ?? []).filter(p => p.type === 'text').map(p => p.text ?? '').join('');
}
function allowed(view: ReadView) {
  return new Map<string, string>([...(view.legacyReferences ?? []).map(r => [r.id, r.role] as const),
    ...view.references.flatMap(({ reference }) => [[reference.input_id, 'user'] as const,
    ...reference.message_ids.map(id => [id, 'assistant'] as const)])]);
}
interface FindCursor {
  version: 1; queryHash: string; scopeHash: string; epoch: string; after: string | null;
  threadId: string | null; nativeCursor: string | null; viewStamp: string | null;
}
const encode = (cursor: FindCursor) => Buffer.from(canonical(cursor)).toString('base64url');
function decode(value: string): FindCursor {
  text(value, 1, 8192);
  try {
    const c = JSON.parse(Buffer.from(value, 'base64url').toString('utf8')) as FindCursor;
    exact(c, ['version', 'queryHash', 'scopeHash', 'epoch', 'after', 'threadId', 'nativeCursor', 'viewStamp']);
    if (c.version !== 1 || [c.queryHash, c.scopeHash, c.epoch].some(s => !/^[a-f0-9]{64}$/.test(s)) ||
      [c.after, c.threadId, c.nativeCursor, c.viewStamp].some(s => s !== null && (typeof s !== 'string' || !s || s.length > 2048)) ||
      (c.threadId === null && (c.nativeCursor !== null || c.viewStamp !== null))) reject('learning_cursor_invalid');
    return c;
  } catch { return reject('learning_cursor_invalid'); }
}
export function createLearningHistory(storage: LearningStorage, native: NativeReader) {
  const check = (view: ReadView) => storage.command({ type: 'learning.read.check', threadId: view.conversation.identity.id, stamp: view.stamp });
  return {
    /** One bounded native page and exact canonical recheck. Reopen never submits input. */
    async range(threadId: string, input: { limit?: number; cursor?: string } = {}) {
      const limit = input.limit ?? 100; integer(limit, 1, 200);
      const view = await storage.command({ type: 'learning.view', threadId });
      if (!view.mapping) return { conversation: view.conversation, messages: [], cursor: null };
      let raw: string | undefined;
      if (input.cursor !== undefined) {
        const c = decode(input.cursor);
        if (c.threadId !== threadId || c.viewStamp !== view.stamp || c.queryHash !== digest('range') || c.scopeHash !== digest(threadId) || !c.nativeCursor) reject('learning_cursor_stale');
        raw = c.nativeCursor;
      }
      const page = await native.observe(view.mapping.runtime.session_id, { limit, ...(raw ? { cursor: raw } : { order: 'asc' as const }) });
      owned(view, page); await check(view);
      const ids = allowed(view), messages = page.messages.filter(m => ids.get(m.id) === m.type);
      return { conversation: view.conversation, messages, cursor: page.cursor.next ? encode({ version: 1, queryHash: digest('range'), scopeHash: digest(threadId), epoch: view.stamp,
        after: null, threadId, nativeCursor: page.cursor.next, viewStamp: view.stamp }) : null };
    },
    /** Exact literal (case-sensitive) text; one native page per call, no search projection.
     * Cursor pins filter/policy/context and exact canonical references of the open range. */
    async find(input: { query: string; scope: FindScope; cursor?: string; ignoreCase?: boolean }) {
      text(input.query, 1, 240);
      const fold = input.ignoreCase === true, queryHash = digest(fold ? 'ignore-case:' + input.query : input.query), scopeHash = digest(canonical(input.scope));
      const cursor = input.cursor ? decode(input.cursor) : null;
      if (cursor && (cursor.queryHash !== queryHash || cursor.scopeHash !== scopeHash)) reject('learning_cursor_stale');
      const scan = await storage.command({ type: 'learning.scan', scope: input.scope, after: cursor?.after ?? null, limit: 1, epoch: cursor?.epoch ?? null });
      const view = cursor?.threadId ? await storage.command({ type: 'learning.view', threadId: cursor.threadId }) : scan.views[0];
      if (!view) return { items: [], next_cursor: null, scanned: null };
      if (cursor?.threadId && cursor.viewStamp !== view.stamp) reject('learning_cursor_stale');
      if ((input.scope.lifecycle !== 'all' && view.conversation.lifecycle !== input.scope.lifecycle) ||
        (input.scope.projectId !== null && view.conversation.project_id !== input.scope.projectId)) reject('learning_cursor_stale');
      const base: FindCursor = { version: 1, queryHash, scopeHash, epoch: scan.epoch,
        after: view.conversation.identity.id, threadId: null, nativeCursor: null, viewStamp: null };
      let items: { conversation: ReadView['conversation']; session_id: string; message_id: string;
        role: string; start: number; end: number; snippet: string }[] = [];
      let next: string | null = scan.next ? encode(base) : null;
      if (view.mapping) {
        const page = await native.observe(view.mapping.runtime.session_id, { limit: 100,
          ...(cursor?.nativeCursor ? { cursor: cursor.nativeCursor } : { order: 'asc' as const }) });
        owned(view, page);
        const ids = allowed(view);
        items = page.messages.flatMap(message => {
          if (ids.get(message.id) !== message.type) return [];
          const value = nativeText(message), lower = value.toLowerCase(), needle = input.query.toLowerCase();
          // Case folding is used only where it preserves exact character offsets.
          const folded = fold && lower.length === value.length && needle.length === input.query.length, start = (folded ? lower : value).indexOf(folded ? needle : input.query);
          if (start < 0) return [];
          return [{ conversation: view.conversation, session_id: page.session.id, message_id: message.id, role: message.type,
            start, end: start + input.query.length, snippet: value.slice(Math.max(0, start - 60), start + input.query.length + 100) }];
        });
        if (page.cursor.next) next = encode({ ...base, after: cursor?.after ?? null, threadId: view.conversation.identity.id,
          nativeCursor: page.cursor.next, viewStamp: view.stamp });
      }
      await check(view);
      await storage.command({ type: 'learning.scan', scope: input.scope, after: null, limit: 1, epoch: scan.epoch });
      return { items, next_cursor: next, scanned: { conversation: view.conversation, first: !cursor?.nativeCursor } };
    },
  };
}
