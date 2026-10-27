// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import type { ArtifactGrant, ArtifactResult, Identity, OutputGrant, WorkerCommand } from '../../../contracts/worker.ts';
import { WorkerChannel } from './channel.ts';

type Binding = Pick<Identity, 'operation_id' | 'attempt_id'>;
type ArtifactCommand = Extract<WorkerCommand, { command: 'library.query' | 'library.stage' | 'library.remove' |
  'library.maintain' | 'memory.extract' | 'memory.recall' | 'memory.reconcile' | 'memory.purge' |
  'document.extract' | 'document.chunk' | 'embedding.embed' }>;
const sha = (body: Uint8Array) => createHash('sha256').update(body).digest('hex');
const opaque = (prefix: string) => prefix + randomUUID().replaceAll('-', '');
function refused(code: string): never { throw Object.assign(new Error(code), { code }); }

/** RAM transfer for an already admitted operation. This owns no domain authority.
 * Caller cancellation requests engine cancellation and still waits for settlement.
 */
export function createEngineArtifacts(channel: WorkerChannel, maxChunkBytes: number) {
  if (!Number.isSafeInteger(maxChunkBytes) || maxChunkBytes < 1 || maxChunkBytes > 256 * 1024) refused('worker_chunk_bound');
  async function request(command: WorkerCommand['command'], input: unknown, binding: Binding, signal?: AbortSignal) {
    if (signal?.aborted) refused('engine_cancelled');
    const call = channel.submit(command, input, binding);
    let cancellation: Promise<void> | undefined;
    const cancel = () => { cancellation ??= (async () => {
      const admission = await call.admission;
      if (admission.reply.settlement.state === 'settled') return;
      const control = channel.submit('worker.settle', { action: 'cancel', target: {
        identity: admission.reply.identity, request_sha256: admission.reply.request_sha256,
        worker_lease: admission.reply.settlement.worker_lease }, revisions: null, artifact_handle: null }, binding);
      await control.terminal; channel.release(control.requestId);
    })(); void cancellation.catch(() => {}); };
    signal?.addEventListener('abort', cancel, { once: true });
    if (signal?.aborted) cancel();
    try {
      const observed = await call.terminal;
      channel.release(call.requestId);
      await cancellation;
      if (signal?.aborted || !observed.current) refused('engine_result_stale');
      if (observed.reply.outcome !== 'committed_reference') {
        const result = observed.reply.result;
        refused(result && 'code' in result && typeof result.code === 'string' ? result.code : 'engine_operation_failed');
      }
      return observed.reply.result;
    } finally { signal?.removeEventListener('abort', cancel); }
  }
  async function release(handle: string, binding: Binding) {
    const call = channel.submit('worker.settle', { action: 'release', target: null, revisions: null, artifact_handle: handle }, binding);
    const result = await call.terminal; channel.release(call.requestId);
    if (result.reply.result && 'code' in result.reply.result && result.reply.result.code === 'artifact_denied') return;
    if (!['committed_reference', 'accepted_pending'].includes(result.reply.outcome)) refused('artifact_release_held');
  }
  return {
    request, release,
    output(maxBytes: number, expiresAt: number): OutputGrant {
      if (!Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 64 * 1024 * 1024 || expiresAt <= Date.now()) refused('artifact_bound');
      return { artifact_handle: opaque('artifact_'), artifact_revision: 1, max_bytes: maxBytes,
        expires_at_ms: expiresAt, reservation_id: opaque('reservation_'), intent_id: opaque('intent_') };
    },
    async upload(body: Uint8Array, binding: Binding, rights: ArtifactGrant['rights'], expiresAt: number, signal?: AbortSignal): Promise<ArtifactGrant> {
      if (!body.byteLength || body.byteLength > 64 * 1024 * 1024) refused('artifact_bound');
      const grant: ArtifactGrant = { artifact_handle: opaque('artifact_'), artifact_revision: 1,
        artifact_sha256: sha(body), bytes: body.byteLength, expires_at_ms: expiresAt, rights,
        permitted_ranges: [{ offset: 0, length: body.byteLength }], reservation_id: opaque('reservation_'), intent_id: opaque('intent_') };
      try {
        for (let offset = 0; offset < body.byteLength; offset += maxChunkBytes) {
          const chunk = body.subarray(offset, offset + maxChunkBytes);
          const result = await request('artifact.upload', { artifact: grant, offset,
            data_base64: Buffer.from(chunk).toString('base64'), final: offset + chunk.byteLength === body.byteLength }, binding, signal);
          if (!result || !('artifact_handle' in result) || result.artifact_handle !== grant.artifact_handle) refused('artifact_reply_mismatch');
        }
        return grant;
      } catch (error) { await release(grant.artifact_handle, binding); throw error; }
    },
    async read(reference: ArtifactResult, maxBytes: number, binding: Binding, signal?: AbortSignal): Promise<Buffer> {
      if (reference.bytes > maxBytes || reference.bytes < 0 || !Number.isSafeInteger(reference.bytes)) refused('artifact_bound');
      const chunks: Buffer[] = [];
      for (let offset = 0; offset < reference.bytes; offset += maxChunkBytes) {
        const length = Math.min(maxChunkBytes, reference.bytes - offset);
        const result = await request('artifact.read', { artifact_handle: reference.artifact_handle,
          artifact_revision: reference.artifact_revision, offset, length }, binding, signal);
        if (!result || !('data_base64' in result)) refused('artifact_reply_mismatch');
        const chunk = Buffer.from(result.data_base64, 'base64');
        if (chunk.byteLength !== length || result.offset !== offset || result.artifact.artifact_handle !== reference.artifact_handle ||
          result.artifact.artifact_revision !== reference.artifact_revision || result.artifact.artifact_sha256 !== reference.artifact_sha256 ||
          result.artifact.bytes !== reference.bytes) refused('artifact_reply_mismatch');
        chunks.push(chunk);
      }
      const body = Buffer.concat(chunks);
      if (sha(body) !== reference.artifact_sha256) refused('artifact_digest_mismatch');
      return body;
    },
    async run<C extends ArtifactCommand>(command: C['command'], input: C['input'], binding: Binding, signal?: AbortSignal): Promise<ArtifactResult> {
      const result = await request(command, input, binding, signal);
      if (!result || result.tag !== 'artifact') refused('artifact_reply_mismatch');
      return result;
    },
  };
}
