// SPDX-License-Identifier: MIT
import type { NativeTransport } from '../dispatch/native.ts';
import type { Permit } from '../dispatch/contracts.ts';
import type { HttpPlan as WorkerHttpPlan, TransportPlan, TransportResult } from '../../../contracts/worker.ts';
import type { WorkerChannel } from './channel.ts';
import { canonicalJson } from '../contracts/worker-codec.ts';
import { createHash, randomUUID } from 'node:crypto';
import { createEngineArtifacts } from './artifacts.ts';
import { reject } from '../storage/contracts.ts';

/** Instantiated only by the app authority. Native/model code receives send;
 * it never receives the ability to mint a worker plan or activate credentials.
 */
export function createWorkerTransport(options: {
  channel: WorkerChannel; maxChunkBytes: number; retention: 'saved' | 'temporary';
  registryHash(permit: Readonly<Permit>): Promise<string>;
  checkCurrent(permit: Readonly<Permit>): Promise<void>;
}): NativeTransport {
  const artifacts = createEngineArtifacts(options.channel, options.maxChunkBytes);
  return {
    authority: 'authenticated-worker',
    async send({ permit, route, serialized, proof, signal }) {
      if (!permit.dispatch_allowed || permit.state !== 'dispatched' || permit.payload_hash !== proof.payload_hash) reject('transport_admission_required');
      const registry = await options.registryHash(permit);
      if (!/^[a-f0-9]{64}$/.test(registry)) reject('transport_registry_unbound');
      await options.checkCurrent(permit);
      if (signal.aborted) reject('domain_cancelled');
      const binding = { operation_id: permit.run_id, attempt_id: permit.permit_id };
      const output = artifacts.output(512 * 1024, Date.now() + 120_000);
      let call: ReturnType<WorkerChannel['submitBound']> | undefined;
      let cancelTask: Promise<void> | undefined;
      const cancel = () => { cancelTask ??= (async () => {
        if (!call) return;
        const admitted = await call.admission;
        if (admitted.reply.settlement.state === 'settled') return;
        const control = options.channel.submit('worker.settle', { action: 'cancel', target: {
          identity: admitted.reply.identity, request_sha256: admitted.reply.request_sha256,
          worker_lease: admitted.reply.settlement.worker_lease }, revisions: null, artifact_handle: null }, binding);
        await control.terminal; options.channel.release(control.requestId);
      })(); void cancelTask.catch(() => {}); };
      try {
        call = options.channel.submitBound('transport.execute', (identity, revisions): TransportPlan => ({
          permit_id: permit.permit_id, admission_receipt: permit.permit_id, identity, revisions, retention: options.retention,
          route: { provider_id: route.provider_id, model_id: route.catalog_model_id, wire_model_id: route.wire_model_id,
            endpoint: route.endpoint, protocol: route.protocol, credential_ref: route.credential_ref, credential_revision: route.credential_epoch },
          native_manifest_sha256: proof.input_manifest_sha256, registry_sha256: registry,
          request_sha256: proof.payload_hash, request_bytes: proof.body_bytes,
          envelope_sha256: createHash('sha256').update(canonicalJson(serialized)).digest('hex'),
          max_output_tokens: proof.output_tokens, expires_at_ms: output.expires_at_ms, output,
          serialized_request: { ...serialized, headers: Object.entries(serialized.headers).map(([name, value]) => ({ name, value })) },
        }), binding);
        signal.addEventListener('abort', cancel, { once: true }); if (signal.aborted) cancel();
        const observed = await call.terminal;
        options.channel.release(call.requestId);
        await cancelTask;
        const result = observed.reply.result as TransportResult;
        if (!result || result.tag !== 'transport' || result.admission_receipt !== permit.permit_id ||
          result.request_sha256 !== proof.payload_hash || result.identity.request_id !== call.requestId) reject('transport_reply_mismatch');
        if (result.outcome !== 'committed_reference' || !result.artifact) {
          if (result.effect === 'uncertain') reject('transport_unavailable');
          reject(result.code ?? 'transport_unavailable');
        }
        if (!observed.current || signal.aborted) reject('domain_cancelled');
        const body = await artifacts.read(result.artifact, output.max_bytes, binding, signal);
        await options.checkCurrent(permit);
        if (signal.aborted) reject('domain_cancelled');
        return { status: result.http_status ?? 502, headers: { 'content-type': 'text/event-stream' },
          body_base64: body.toString('base64'), result_reference: result.artifact.artifact_handle };
      } finally {
        signal.removeEventListener('abort', cancel);
        await cancelTask;
        await artifacts.release(output.artifact_handle, binding);
      }
    },
  };
}

/** The part of an admitted capability lease the worker plan reads; callers without a stored lease supply just this. */
export type WorkerHttpRequest = Omit<import('../domain/capabilities/contracts.ts').HttpPlan, 'lease'> & { lease: {
  id: string; state: string; envelope: Pick<import('../domain/capabilities/contracts.ts').CapabilityEnvelope, 'run_id' | 'retention'>;
  grant: Pick<import('../domain/capabilities/contracts.ts').CapabilityGrant, 'expires_at_ms' | 'endpoints'> } };
export function createWorkerHttp(options: {
  channel: WorkerChannel; maxChunkBytes: number; retention: 'saved' | 'temporary';
}): (plan: WorkerHttpRequest, signal: AbortSignal) => ReturnType<import('../domain/capabilities/contracts.ts').CapabilityTransport['http']> {
  const artifacts = createEngineArtifacts(options.channel, options.maxChunkBytes);
  return async (plan, signal) => {
    signal.throwIfAborted();
    const { lease } = plan, envelope = lease.envelope;
    if (lease.id !== plan.lease_id || lease.state !== 'admitted' || envelope.retention !== options.retention)
      reject('capability_lease_invalid');
    const binding = { operation_id: envelope.run_id, attempt_id: lease.id };
    const output = artifacts.output(plan.max_response_bytes, lease.grant.expires_at_ms);
    let call: ReturnType<WorkerChannel['submitBound']> | undefined;
    let cancelTask: Promise<void> | undefined;
    const cancel = () => { cancelTask ??= (async () => {
      if (!call) return;
      const admitted = await call.admission;
      if (admitted.reply.settlement.state === 'settled') return;
      const control = options.channel.submit('worker.settle', { action: 'cancel', target: {
        identity: admitted.reply.identity, request_sha256: admitted.reply.request_sha256,
        worker_lease: admitted.reply.settlement.worker_lease }, revisions: null, artifact_handle: null }, binding);
      await control.terminal; options.channel.release(control.requestId);
    })(); void cancelTask.catch(() => {}); };
    try {
      call = options.channel.submitBound('transport.http', (identity, revisions): WorkerHttpPlan => ({
        permit_id: 'http_' + randomUUID().replaceAll('-', ''), admission_receipt: lease.id,
        identity, revisions, retention: options.retention, expires_at_ms: lease.grant.expires_at_ms, output,
        endpoints: lease.grant.endpoints, method: plan.method as WorkerHttpPlan['method'], url: plan.url,
        headers: Object.entries(plan.headers).map(([name, value]) => ({ name, value })),
        body_base64: plan.body_base64, body_sha256: plan.body_sha256,
        credential: plan.credential_ref ? { ref: plan.credential_ref, revision: plan.credential_revision! } : null,
        max_response_bytes: plan.max_response_bytes,
      }), binding);
      signal.addEventListener('abort', cancel, { once: true }); if (signal.aborted) cancel();
      const observed = await call.terminal;
      options.channel.release(call.requestId);
      await cancelTask;
      const result = observed.reply.result;
      if (observed.reply.outcome !== 'committed_reference')
        reject(result && 'code' in result && result.code ? result.code : 'capability_http_failed');
      if (result.tag !== 'http' || result.admission_receipt !== lease.id || result.identity.request_id !== call.requestId)
        reject('capability_reply_mismatch');
      if (result.outcome !== 'committed_reference' || !result.artifact) reject(result.code ?? 'capability_http_failed');
      if (!observed.current || signal.aborted) reject('capability_stale');
      let body = await artifacts.read(result.artifact, output.max_bytes, binding, signal);
      signal.throwIfAborted();
      let offset = 0, closing: Promise<void> | undefined;
      return { status: result.http_status ?? 502, headers: Object.fromEntries((result.headers ?? []).map(h => [h.name, h.value])),
        async read(readSignal) {
          signal.throwIfAborted(); readSignal.throwIfAborted();
          if (closing || offset >= body.length) return null;
          const chunk = body.subarray(offset, offset + options.maxChunkBytes); offset += chunk.length;
          return chunk;
        },
        close() {
          closing ??= artifacts.release(output.artifact_handle, binding).then(() => { body = Buffer.alloc(0); });
          return closing;
        },
      };
    } catch (error) {
      await artifacts.release(output.artifact_handle, binding);
      throw error;
    } finally {
      signal.removeEventListener('abort', cancel);
      await cancelTask;
    }
  };
}
