// SPDX-License-Identifier: MIT
import type { IncomingMessage, ServerResponse } from 'node:http';
import type { StorageClient } from '../storage/index.ts';
import type { SavedLearning } from './learning-commands.ts';
import { readJsonObject } from './body.ts';
import { exact, integer, reject, text } from '../storage/contracts.ts';
import { randomUUID } from 'node:crypto';
import { learningSendIntent } from '../storage/learning.ts';

export function learningEvents(response: ServerResponse) {
  let sequence = 0;
  return (runId: string, type: string, payload: unknown) => {
    if (response.destroyed || response.writableEnded) return;
    if (!response.headersSent) response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-store', 'x-accel-buffering': 'no' });
    const value = { id: randomUUID(), run_id: runId, sequence: ++sequence, type, payload };
    response.write(`id: ${value.id}\nevent: ${type}\ndata: ${JSON.stringify(value)}\n\n`);
  };
}

/** Renderer loss detaches observation. Saved execution remains owned until its
 * native/domain settlement; only the separate cancel command fences that work.
 */
export async function learningStream(request: IncomingMessage, response: ServerResponse, url: URL,
  storage: StorageClient, learning?: SavedLearning): Promise<boolean> {
  const match = /^\/api\/v1\/conversations\/learning\/([A-Za-z0-9_-]{1,120})\/messages$/.exec(url.pathname);
  if (!match || request.method !== 'POST') return false;
  if (!learning) reject('learning_host_unavailable');
  const body = await readJsonObject(request, 24 * 1024 * 1024);
  const intent: Record<string, unknown> = { teaching_style: 'direct', topic_id: null, model: null, freshness: null, content_refs: [], ...body };
  exact(intent, ['expected_revision', 'text', 'request_id', 'teaching_style', 'topic_id', 'model', 'freshness', 'content_refs', ...(Object.hasOwn(intent, 'images') ? ['images'] : [])]);
  integer(intent.expected_revision, 1); text(intent.text, 1, 16000); text(intent.request_id, 1, 120);
  if (!/^[A-Za-z0-9._-]+$/.test(intent.request_id)) reject('storage_invalid_command');
  const key = request.headers['idempotency-key'];
  if (typeof key !== 'string' || key !== intent.request_id) reject('invalid_idempotency_key');
  const validated = learningSendIntent({ expectedRevision: intent.expected_revision as number, text: intent.text as string,
    idempotencyKey: key, intent: intent as never });
  const draft = await storage.command({ type: 'learning.draft.get', threadId: match[1] });
  const event = learningEvents(response);
  let runId: string | undefined;
  try {
    const receipt = await learning.send({ threadId: match[1], expectedRevision: validated.expected_revision,
      expectedDraftRevision: draft.revision, text: validated.text, idempotencyKey: key, intent: validated }, {
      accepted(accepted) { runId = accepted.run_id; event(runId, 'started', { conversation: accepted.conversation }); },
    });
    runId = receipt.run_id;
    event(runId, receipt.state === 'completed' ? 'completed' : receipt.state === 'cancelled' ? 'cancelled' : 'error',
      { ...receipt, ...(receipt.state !== 'completed' && receipt.state !== 'cancelled' ? {
        code: 'response_interrupted', message: 'The response did not finish. Your draft is retained.', retryable: true } : {}) });
    if (!response.destroyed) response.end();
    return true;
  } catch (error) {
    if (!runId || !response.headersSent) throw error;
    const code = error && typeof error === 'object' && 'code' in error && typeof error.code === 'string' ? error.code : 'response_interrupted';
    event(runId, 'error', { code, message: 'The response did not finish. Your draft is retained.', retryable: true });
    if (!response.destroyed) response.end();
    return true;
  }
}
