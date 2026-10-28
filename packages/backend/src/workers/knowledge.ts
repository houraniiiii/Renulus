// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import type { ArtifactResult, WorkerCommand, NativeIntent, NativePin } from '../../../contracts/worker.ts';
import type { ImportIntent, KnowledgeNativeIO, ReaderPayload, ReaderRequest, SourcePin } from '../domain/knowledge/contracts.ts';
import type { SpaceMeasurement } from '../storage/generation.ts';
import type { WorkerChannel } from './channel.ts';
import { createEngineArtifacts } from './artifacts.ts';

const MAX = 64 * 1024 * 1024;
type NativeInput = Extract<WorkerCommand, { command: 'native.io' }>['input'];
type CallInput<T = NativeInput> = T extends NativeInput ? Omit<T, 'output' | 'artifact_handle' | 'artifact_revision' | 'offset' | 'length'> : never;
function refused(code: string): never { throw Object.assign(new Error(code), { code }); }
const intent = (i: ImportIntent): NativeIntent => ({ intent_id: i.id, reservation_id: i.reservation_id,
  revision_id: i.revision_id, bytes: i.request.bytes, sha256: i.request.sha256, stamp: i.stamp, media_type: i.request.media_type });
const pin = (p: SourcePin): NativePin => ({ revision_id: p.revision_id, original_handle: p.original_handle,
  bytes: p.bytes, sha256: p.sha256, media_type: p.media_type });
const position = (r: ReaderRequest) => ({ page: r.page ?? 1, sheet: r.sheet ?? null, first_row: r.first_row ?? 1, row_limit: r.row_limit ?? 100 });

/** Budget of the profile's native stores and governed retirement of a discarded candidate generation. */
export interface NativeStorageIO {
  measure(): Promise<SpaceMeasurement>;
  /** Refuses unknown and selected generations; retains the candidate's bytes as cleanup debt, never deleting by pathname. Idempotent. */
  retire(candidateId: string): Promise<{ result: 'retained_as_debt'; debt_bytes: number }>;
}

/** Implements the exact Knowledge port over the existing authenticated worker.
 * Bytes use retained, bounded artifacts; only opaque chooser/original handles
 * and canonical intent/pin metadata enter native command frames.
 */
export function createWorkerKnowledgeIO(channel: WorkerChannel, maxChunkBytes: number): KnowledgeNativeIO & NativeStorageIO {
  const artifacts = createEngineArtifacts(channel, maxChunkBytes);
  async function call(input: CallInput, body?: Uint8Array, signal?: AbortSignal, binary = false): Promise<Buffer> {
    const binding = { operation_id: 'native_' + randomUUID().replaceAll('-', ''), attempt_id: 'attempt_1' };
    const output = artifacts.output(MAX, Date.now() + 120_000);
    let upload: Awaited<ReturnType<typeof artifacts.upload>> | undefined;
    try {
      if (body) upload = await artifacts.upload(body, binding, ['read'], Date.now() + 120_000, signal);
      const range = upload ? { artifact_handle: upload.artifact_handle, artifact_revision: upload.artifact_revision, offset: 0, length: upload.bytes } : {};
      const result = await artifacts.request('native.io', { ...input, ...range, output }, binding, signal);
      if (!result || result.tag !== 'artifact') refused('native_reply_invalid');
      const bytes = await artifacts.read(result as ArtifactResult, output.max_bytes, binding, signal);
      if (!binary && bytes.length > 8 * 1024 * 1024) refused('native_reply_bound');
      return bytes;
    } finally {
      if (upload) await artifacts.release(upload.artifact_handle, binding);
      await artifacts.release(output.artifact_handle, binding);
    }
  }
  async function json(input: Parameters<typeof call>[0], body?: Uint8Array, signal?: AbortSignal) {
    return JSON.parse((await call(input, body, signal)).toString('utf8'));
  }
  function checked(body: Buffer, bytes: number, digest: string) {
    if (body.length !== bytes || createHash('sha256').update(body).digest('hex') !== digest) refused('native_original_integrity');
    return body;
  }
  return {
    async reserve(i) { await json({ action: 'reserve', intent: intent(i) }); },
    async readSelection({ handle, intent: i }, signal) {
      return checked(await call({ action: 'read_selection', handle, intent: intent(i) }, undefined, signal, true), i.request.bytes, i.request.sha256);
    },
    async publish({ intent: i, body }, signal) {
      const result = await json({ action: 'publish', intent: intent(i) }, body, signal);
      if (!result || typeof result.original_handle !== 'string') refused('native_reply_invalid');
      return { original_handle: result.original_handle };
    },
    async settle(i) { await json({ action: 'settle', intent: intent(i), state: i.state }); },
    async read(p, signal) { return checked(await call({ action: 'read', pin: pin(p) }, undefined, signal, true), p.bytes, p.sha256); },
    async payload({ pin: p, request, body }, signal) {
      return await json({ action: 'payload', pin: pin(p), position: position(request) }, body, signal) as ReaderPayload;
    },
    async asset({ pin: p, request, body, asset_id }, signal) {
      return call({ action: 'asset', pin: pin(p), position: position(request), asset_id }, body, signal, true);
    },
    async measure() {
      const value = await json({ action: 'measure' });
      return { allocatedBytes: value.allocated_bytes, freeBytes: value.free_bytes, ceilingBytes: value.ceiling_bytes };
    },
    async retire(candidateId) {
      const value = await json({ action: 'retire', candidate_id: candidateId });
      if (value?.result !== 'retained_as_debt') refused('native_reply_invalid');
      return value;
    },
    async handoff({ pin: p, action, destination_handle }, signal) {
      const value = await json({ action: 'handoff', pin: pin(p), operation: action, destination_handle }, undefined, signal);
      if (value?.handed_off !== true) refused('native_handoff_failed');
      return { handed_off: true };
    },
  };
}
