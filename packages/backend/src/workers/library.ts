// SPDX-License-Identifier: MIT
import type { LibraryQueryBridge } from '../domain/learning/callbacks.ts';
import type { WorkerChannel } from './channel.ts';
import { createEngineArtifacts } from './artifacts.ts';
import { exact, integer, reject, text } from '../storage/contracts.ts';
import { parseJson } from '../dispatch/wire.ts';

/** Canonical callbacks supply the current eligible revision set. Worker text is
 * discarded here; the canonical transaction resolves the actual passages.
 */
export function createWorkerLibrary(channel: WorkerChannel, maxChunkBytes: number): LibraryQueryBridge {
  const artifacts = createEngineArtifacts(channel, maxChunkBytes);
  return {
    async query(input) {
      const binding = { operation_id: input.operationId, attempt_id: input.attemptId };
      integer(input.limit, 1, 30);
      if (input.revisionIds.length > 256) reject('library_scope_capacity');
      const output = artifacts.output(256 * 1024, Date.now() + 120_000);
      try {
        const reference = await artifacts.run('library.query', { query: input.query,
          allowed_revision_ids: [...input.revisionIds], limit: input.limit, output }, binding, input.signal);
        const body = await artifacts.read(reference, output.max_bytes, binding, input.signal);
        const value = parseJson(body.toString('utf8'));
        exact(value, ['tag', 'rows']);
        if (value.tag !== 'library_candidates' || !Array.isArray(value.rows) || value.rows.length > input.limit) reject('library_result_invalid');
        return value.rows.map(row => {
          exact(row, ['passage_id', 'revision_id', 'document_id', 'text']);
          text(row.passage_id, 1, 128); text(row.revision_id, 1, 128);
          if (!input.revisionIds.includes(row.revision_id)) reject('library_result_stale');
          return { passage_id: row.passage_id, revision_id: row.revision_id };
        });
      } finally { await artifacts.release(output.artifact_handle, binding); }
    },
  };
}
