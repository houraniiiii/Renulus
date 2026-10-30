// SPDX-License-Identifier: MIT
/** Global literal Finder over canonical metadata plus the owning host's native messages.
 * It owns no index and no transcript copy: chats are searched through `history.find`
 * (one native page per step), projects and Library files/notes through canonical commands.
 * Every cursor pins the query, filter and the epoch of the phase it continues. */
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical, digest } from '../../storage/schema.ts';
import type { ConversationSummary } from '../../storage/contracts.ts';
import type { FindScope } from '../learning/contracts.ts';
import type { KnowledgeResults, KnowledgeStorage } from '../knowledge/contracts.ts';
import type { ProjectResults, ProjectStorage } from '../projects/contracts.ts';

export interface FindHistory {
  find(input: { query: string; scope: FindScope; cursor?: string; ignoreCase?: boolean }): Promise<{
    items: { conversation: ConversationSummary; message_id: string; role: string; start: number; end: number; snippet: string }[];
    next_cursor: string | null; scanned: { conversation: ConversationSummary; first: boolean } | null }>;
}
export interface FindOptions { storage: KnowledgeStorage & ProjectStorage; history: FindHistory }
export interface FindResult { key: string; group: 'chats' | 'projects' | 'files' | 'notes'; title: string; snippet: string; [field: string]: unknown }

const STEPS = 40, BATCH = 100;
type State = { phase: 'chats'; chat: string | null } | { phase: 'projects' | 'files'; after: string | null; epoch: string | null };
interface Cursor { v: 1; q: string; s: string; state: State }
const encode = (c: Cursor) => Buffer.from(canonical(c)).toString('base64url');
function decode(value: string): Cursor {
  text(value, 1, 8192);
  try {
    const c = JSON.parse(Buffer.from(value, 'base64url').toString('utf8')) as Cursor;
    exact(c, ['v', 'q', 's', 'state']);
    if (c.v !== 1 || !/^[a-f0-9]{64}$/.test(c.q) || !/^[a-f0-9]{64}$/.test(c.s)) reject('search_cursor_changed');
    if (c.state.phase === 'chats') exact(c.state, ['phase', 'chat']);
    else { exact(c.state, ['phase', 'after', 'epoch']); if (!['projects', 'files'].includes(c.state.phase)) reject('search_cursor_changed'); }
    return c;
  } catch { return reject('search_cursor_changed'); }
}
/** Same bounded excerpt as the retained Python Finder. */
export function snippet(value: string, query: string) {
  const flat = value.split(/\s+/).filter(Boolean).join(' '), at = flat.toLowerCase().indexOf(query.toLowerCase()), start = Math.max(0, at - 80);
  return (start ? '…' : '') + flat.slice(start, start + 280) + (flat.length > start + 280 ? '…' : '');
}
/** Canonical Knowledge physical page or stable text item pin; nothing invented. */
export function location(raw: string) {
  try {
    for (const value of JSON.parse(raw) as Record<string, unknown>[]) {
      if (Number.isInteger(value.page) && (value.page as number) > 0) return { kind: 'pdf', physical_page: value.page };
      const span = value.char_span;
      if (typeof value.item_ref === 'string' && Array.isArray(span) && span.length === 2 && span.every(Number.isInteger) && span[0] >= 0 && span[0] <= span[1])
        return { kind: 'text', item_ref: value.item_ref, start: span[0], end: span[1] };
    }
  } catch { /* no precise location */ }
  return null;
}
export function createFindDomain({ storage, history }: FindOptions) {
  return {
    /** One bounded response; follow `next_cursor` until null (a page may be empty). */
    async find(input: { query: string; scope: FindScope; cursor?: string | null; limit?: number }) {
      const query = input.query.trim(), limit = input.limit ?? 30; integer(limit, 1, 50);
      if (!query) return { items: [] as FindResult[], next_cursor: null };
      text(query, 1, 240);
      const q = digest(query), s = digest(canonical(input.scope)), cursor = input.cursor ? decode(input.cursor) : null;
      if (cursor && (cursor.q !== q || cursor.s !== s)) reject('search_cursor_changed');
      let state: State | null = cursor?.state ?? { phase: 'chats', chat: null };
      const items: FindResult[] = [], needle = query.toLowerCase();
      for (let step = 0; state && step < STEPS && items.length < limit; step++) {
        if (state.phase === 'chats') {
          const page: Awaited<ReturnType<FindHistory['find']>> = await history.find({ query, scope: input.scope, ignoreCase: true, ...(state.chat ? { cursor: state.chat } : {}) });
          const c = page.scanned?.conversation, base = c && { title: c.title, lifecycle: c.lifecycle, project_id: c.project_id, identity: c.identity };
          if (c && page.scanned!.first && c.title.toLowerCase().includes(needle)) items.push({ key: 'chat:learning:' + c.identity.id, group: 'chats', snippet: '', ...base! });
          for (const hit of page.items) items.push({ key: 'message:' + hit.conversation.identity.id + ':' + hit.message_id, group: 'chats', snippet: snippet(hit.snippet, query),
            ...base!, message: { id: hit.message_id, role: hit.role, start: hit.start, end: hit.end } });
          state = page.next_cursor ? { phase: 'chats', chat: page.next_cursor } : { phase: 'projects', after: null, epoch: null };
        } else if (state.phase === 'projects') {
          const page: ProjectResults['project.find'] = await storage.command({ type: 'project.find', query, lifecycle: input.scope.lifecycle, projectId: input.scope.projectId, after: state.after, limit: BATCH, epoch: state.epoch });
          for (const p of page.items) items.push({ key: 'project:' + p.id, group: 'projects', title: p.title, snippet: '', lifecycle: p.lifecycle, project_id: p.id });
          state = page.next ? { phase: 'projects', after: page.next, epoch: page.epoch } : { phase: 'files', after: null, epoch: null };
        } else {
          // Files and notes have no Archive lifecycle; an archived-only filter excludes them.
          if (input.scope.lifecycle === 'archived') { state = null; break; }
          const page: KnowledgeResults['knowledge.find'] = await storage.command({ type: 'knowledge.find', query, projectId: input.scope.projectId, after: state.after, limit: BATCH, epoch: state.epoch });
          for (const f of page.items) {
            const reference: Record<string, unknown> = { target: { type: f.note ? 'note_revision' : 'library_revision', id: f.revision_id } };
            const located = f.locators_json ? location(f.locators_json) : null; if (located) reference.locator = located;
            items.push({ key: 'file:' + f.revision_id, group: f.note ? 'notes' : 'files', title: f.title, snippet: snippet(f.text ?? '', query), status: f.status, reference });
          }
          state = page.next ? { phase: 'files', after: page.next, epoch: page.epoch } : null;
        }
      }
      return { items, next_cursor: state ? encode({ v: 1, q, s, state }) : null };
    },
  };
}
export type FindDomain = ReturnType<typeof createFindDomain>;
