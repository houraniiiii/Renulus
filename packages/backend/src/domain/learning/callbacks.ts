// SPDX-License-Identifier: MIT
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import { canonical } from '../../storage/schema.ts';
import type { NativeDomainReply, NativeDomainRequest } from '../../host/domain-adapter.ts';
import type { LibraryCitation } from '../../../../harness/src/domain-tools.ts';
import type { LearningStorage, RuntimeIdentity, RunSnapshot } from './contracts.ts';

/** App-owned LanceDB/FastEmbed worker query seam. Only ranked IDs cross this boundary.
 * Canonical scope/rights/current revisions are checked before the query and after it settles. */
export interface LibraryQueryBridge {
  query(input: Readonly<{ query: string; limit: number; revisionIds: readonly string[];
    operationId: string; attemptId: string; signal: AbortSignal }>): Promise<readonly { passage_id: string; revision_id: string }[]>;
}
export interface LearningCallbacksOptions {
  storage: LearningStorage; identity: RuntimeIdentity; library: LibraryQueryBridge;
  /** Parent's BF01 callback registry; never a fixture/default transport here. */
  modelCallbacks?: (request: NativeDomainRequest) => Promise<NativeDomainReply>;
}
function code(error: unknown) {
  const value = error && typeof error === 'object' && 'code' in error ? error.code : '';
  return typeof value === 'string' && /^[a-z0-9_-]{1,128}$/.test(value) ? value : 'learning_callback_unavailable';
}
export function createLearningCallbacks(options: LearningCallbacksOptions) {
  const { storage } = options;
  let closed = false;
  async function current(request: NativeDomainRequest, admitting = false): Promise<RunSnapshot> {
    if (closed || request.signal.aborted) reject('learning_cancelled');
    let run = await storage.command({ type: 'learning.current', runId: request.binding.operation_id, binding: admitting ? null : request.binding });
    if (canonical(run.checkpoint.identity) !== canonical(options.identity)) reject('learning_generation_changed');
    if (closed || request.signal.aborted) reject('learning_cancelled');
    if (admitting) run = await storage.command({ type: 'learning.bind', binding: request.binding });
    return run;
  }
  return {
    seal() { closed = true; },
    async handle(request: NativeDomainRequest): Promise<NativeDomainReply> {
      try {
        if (request.command === 'learning.admit_input') exact(request.payload, []);
        const run = await current(request, request.command === 'learning.admit_input');
        const { payload, command, binding, signal } = request;
        if (command.startsWith('model.')) {
          if (!options.modelCallbacks) reject('learning_model_gateway_unavailable');
          const result = await options.modelCallbacks(request);
          await current(request); return result;
        }
        if (['learning.admit_input', 'learning.check', 'learning.authority'].includes(command)) {
          exact(payload, []);
          if (command === 'learning.authority') return { outcome: 'committed_reference', result: {
            sessionId: binding.session_id, operationId: binding.operation_id, attemptId: binding.attempt_id,
            scope: { kind: 'study', entity_id: run.checkpoint.projectId }, revisionIds: run.checkpoint.revisionIds,
            policyRevision: run.checkpoint.policyRevision, contextEpoch: run.checkpoint.contextEpoch,
            cancellationEpoch: run.checkpoint.cancellationEpoch } };
          return { outcome: 'committed_reference', result: command === 'learning.admit_input' ? { admitted: true } : { current: true } };
        }
        if (command === 'learning.context') {
          exact(payload, ['messages']);
          const result = await storage.command({ type: 'learning.context', binding, messages: payload.messages as never });
          await current(request); return { outcome: 'committed_reference', result };
        }
        // The bounded saved-text target does not admit images. BF04 owns decoding/volatile input.
        if (command === 'learning.validate_images') {
          exact(payload, ['images']); if (!Array.isArray(payload.images) || payload.images.length) reject('learning_images_not_admitted');
          return { outcome: 'committed_reference', result: { validated: true } };
        }
        if (!['library.retrieve', 'library.citation'].includes(command)) reject('learning_callback_unknown');
        exact(payload, ['command', 'arguments', 'envelope']);
        if (payload.command !== command) reject('learning_callback_invalid');
        // The returned envelope is observation only. No authority field is read from it.
        const args = payload.arguments as Record<string, unknown>;
        if (command === 'library.retrieve') {
          if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(k => !['query', 'limit'].includes(k))) reject('storage_invalid_command');
          text(args.query, 1, 16000); if (!args.query.trim()) reject('storage_invalid_command');
          const limit = args.limit ?? 5; integer(limit, 1, 8);
          const plan = await storage.command({ type: 'learning.library.plan', binding });
          const hits = plan.revisionIds.length ? await options.library.query({ query: args.query, limit: limit * 3,
            revisionIds: Object.freeze([...plan.revisionIds]), operationId: binding.operation_id, attemptId: binding.attempt_id, signal }) : [];
          // Retain actual worker settlement before checking cancellation and canonical state.
          await current(request);
          if (!Array.isArray(hits) || hits.length > limit * 3 || hits.some(h => !h || typeof h.passage_id !== 'string' || !plan.revisionIds.includes(h.revision_id))) reject('learning_library_result_invalid');
          const selected = [...new Map(hits.map(h => [h.passage_id, h])).values()].slice(0, limit);
          const resolved = await storage.command({ type: 'learning.library.resolve', binding, passageIds: selected.map(h => h.passage_id) });
          if (resolved.passages.some(p => selected.find(h => h.passage_id === p.id)?.revision_id !== p.document_revision)) reject('learning_library_result_invalid');
          await storage.command({ type: 'learning.consume', binding, references: resolved.references });
          await current(request);
          return { outcome: 'committed_reference', result: { status: plan.revisionIds.length ? 'ready' : 'no_eligible_documents', passages: resolved.passages } };
        }
        const keys = ['document_id', 'document_revision', 'passage_id'];
        if (!args || typeof args !== 'object' || Array.isArray(args) || keys.some(k => typeof args[k] !== 'string') ||
          Object.keys(args).some(k => ![...keys, 'page'].includes(k))) reject('storage_invalid_command');
        if (args.page !== undefined) integer(args.page, 1, 300);
        const resolved = await storage.command({ type: 'learning.library.resolve', binding, passageIds: [String(args.passage_id)] });
        const p = resolved.passages[0];
        if (!p || p.document_id !== args.document_id || p.document_revision !== args.document_revision ||
          (args.page !== undefined && !p.locators.some(l => l.page === args.page))) reject('learning_source_changed');
        const citation: LibraryCitation = { ...resolved.references[0], original_url: `/api/v1/library/revisions/${p.document_revision}/original`,
          viewer_url: `/library/${p.document_id}?revision=${p.document_revision}${args.page === undefined ? '' : '&page=' + args.page}&passage_id=${p.id}` };
        await storage.command({ type: 'learning.consume', binding, references: resolved.references });
        await current(request); return { outcome: 'committed_reference', result: { ...citation } };
      } catch (error) {
        return { outcome: request.signal.aborted ? 'cancelled_settled' : 'rejected_before_admission',
          error: { code: code(error), status: 409, retryable: false } };
      }
    },
  };
}
