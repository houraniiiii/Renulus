// SPDX-License-Identifier: MIT
import type { IncomingMessage, ServerResponse } from 'node:http';
import { randomUUID } from 'node:crypto';
import type { ConnectedTarget } from '../host/composition.ts';
import type { StorageClient } from '../storage/index.ts';
import { canonical } from '../storage/schema.ts';
import { exact, integer, reject, text } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
import { learningEvents } from './learning-stream.ts';
import { nativeText, type NativeMessage } from '../domain/learning/history.ts';

type Temporary = NonNullable<ConnectedTarget['temporary']>;
export function temporaryLearning(storage: StorageClient, temporary?: Temporary) {
  const families = new Map<string, { family: Awaited<ReturnType<Temporary['open']>>;
    summary: { identity: { type: string; id: string }; kind: string; title: string; retention: string; lifecycle: string; revision: number; project_id: null; created_at: string; updated_at: string };
    busy: boolean; saveKey?: string }>();
  const creations = new Map<string, { intent: string; summary: unknown }>();
  return async (request: IncomingMessage, response: ServerResponse, url: URL) => {
    const send = (status: number, value: unknown) => {
      if (!response.destroyed) { response.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' }); response.end(JSON.stringify(value)); }
      return true;
    };
    const key = request.headers['idempotency-key'];
    if (url.pathname === '/api/v1/conversations' && request.method === 'POST') {
      const body = { kind: 'learning', title: 'New chat', temporary: false, project_id: null, topic_id: null,
        teaching_style: 'direct', text: '', teaching_case_id: null, ...await readJsonObject(request, 65536) };
      if (!body.temporary) return send(201, await storage.command({ type: 'learning.create', request: body as never, idempotencyKey: typeof key === 'string' ? key : null }));
      exact(body, ['kind', 'title', 'temporary', 'project_id', 'topic_id', 'teaching_style', 'text', 'teaching_case_id']);
      if (!temporary) reject('learning_host_unavailable');
      if (!['learning', 'case'].includes(body.kind) || body.temporary !== true || body.project_id !== null || body.text || body.teaching_case_id || body.topic_id !== null || !['direct', 'guided'].includes(body.teaching_style)) reject('storage_invalid_command');
      text(body.title, 1, 120);
      const intent = canonical(body), previous = typeof key === 'string' ? creations.get(key) : undefined;
      if (previous) { if (previous.intent !== intent) reject('idempotency_conflict'); return send(201, previous.summary); }
      const family = await temporary.open(body.kind === 'case' ? 'case-discuss' : 'explain');
      const id = 'temporary_' + randomUUID().replaceAll('-', ''), created = new Date().toISOString();
      const summary = { identity: { type: body.kind === 'case' ? 'case' : 'learn_thread', id }, kind: body.kind, title: body.title,
        retention: 'temporary', lifecycle: 'active', revision: 1, project_id: null, created_at: created, updated_at: created };
      families.set(id, { family, summary, busy: false });
      if (typeof key === 'string') creations.set(key, { intent, summary: structuredClone(summary) });
      return send(201, summary);
    }
    const match = /^\/api\/v1\/conversations\/(learning|case)\/([A-Za-z0-9_-]{1,120})(?:\/(messages|save))?$/.exec(url.pathname);
    if (!match) return false;
    const entry = families.get(match[2]); if (!entry || entry.summary.kind !== match[1]) return false;
    const { family, summary } = entry;
    if (!match[3] && request.method === 'DELETE') {
      const revision = Number(url.searchParams.get('expected_revision')); integer(revision, 1);
      if (revision !== summary.revision) reject('conversation_revision_conflict');
      await family.disconnect(); return send(200, { deleted: true, identity: summary.identity });
    }
    if (match[3] === 'save' && request.method === 'POST') {
      const body = await readJsonObject(request, 4096); exact(body, ['expected_revision']); integer(body.expected_revision, 1);
      text(key, 8, 128);
      if (!family.status().saved && body.expected_revision !== summary.revision) reject('conversation_revision_conflict');
      if (entry.saveKey && entry.saveKey !== key) reject('idempotency_conflict');
      entry.saveKey = key;
      const saved = await family.save(summary.title, key);
      return send(200, await storage.command({ type: 'learning.get', threadId: saved.threadId }));
    }
    if (match[3] !== 'messages' || request.method !== 'POST') return false;
    const body: Record<string, unknown> = { teaching_style: 'direct', topic_id: null, model: null, freshness: null, content_refs: [], ...await readJsonObject(request, 128 * 1024) };
    exact(body, ['expected_revision', 'text', 'request_id', 'teaching_style', 'topic_id', 'model', 'freshness', 'content_refs']);
    integer(body.expected_revision, 1); text(body.text, 1, 16000); text(body.request_id, 1, 120);
    if (body.expected_revision !== summary.revision) reject('conversation_revision_conflict');
    if (key !== body.request_id) reject('invalid_idempotency_key');
    if (!Array.isArray(body.content_refs) || body.content_refs.length) reject('temporary_content_unavailable');
    if (body.model !== null || body.freshness || body.topic_id !== null || body.teaching_style !== 'direct') reject('learning_model_intent_unavailable');
    if (entry.busy) reject('conversation_busy'); entry.busy = true;
    const event = learningEvents(response), runId = 'run_' + randomUUID().replaceAll('-', '');
    let ended = false, disconnected: Promise<unknown> | undefined;
    const disconnect = () => { if (!ended) { disconnected ??= family.disconnect(); void disconnected.catch(() => {}); } };
    request.once('close', () => { if (request.aborted) disconnect(); });
    response.once('close', disconnect);
    try {
      summary.revision++; summary.updated_at = new Date().toISOString();
      event(runId, 'started', { conversation: summary });
      event(runId, 'progress', { stage: 'generating', conversation: summary });
      const result = await family.send({ text: body.text });
      if (disconnected) { await disconnected; return true; }
      const page = await family.range({ limit: 200, order: 'asc' });
      const messages = page.messages as unknown as NativeMessage[];
      const boundary = messages.findIndex(m => m.id === result.inputId);
      const answer = messages.slice(boundary + 1).filter(m => m.type === 'assistant').map(nativeText).join('');
      event(runId, 'sources', { sources: [], conversation: summary });
      event(runId, 'delta', { text: answer, conversation: summary });
      summary.revision++; summary.updated_at = new Date().toISOString();
      event(runId, 'completed', { run_id: runId, state: 'completed', conversation: summary });
    } catch (error) {
      event(runId, 'error', { code: error && typeof error === 'object' && 'code' in error ? error.code : 'conversation_failed', message: 'The response could not finish. Your draft is retained.', retryable: true });
    } finally {
      entry.busy = false; ended = true; response.off('close', disconnect);
      if (!response.destroyed) response.end();
      await disconnected;
    }
    return true;
  };
}
