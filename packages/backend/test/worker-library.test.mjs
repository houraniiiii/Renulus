// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { openEngineWorker } from '../src/workers/process.ts';
import { createEngineArtifacts } from '../src/workers/artifacts.ts';
import { createWorkerLibrary } from '../src/workers/library.ts';

test('real Node Library bridge stages, prefilters, queries and tombstones selected Lance engine', {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON || !process.env.RENULUS_WORKER_TEST_HELPERS, timeout: 180_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-worker-library-'));
  const repository = fileURLToPath(new URL('../../..', import.meta.url));
  const revisions = { configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 };
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON,
    sourceRoot: repository, launchRoot: path.join(root, 'launch'), retention: 'saved',
    identity: { profile_id: 'synthetic-profile', domain_store_id: 'synthetic-domain', runtime_store_id: 'synthetic-native',
      authority_epoch: 1, process_generation: 'synthetic-library' }, current: () => revisions,
    helpers: { helpers_root: process.env.RENULUS_WORKER_TEST_HELPERS, cache_root: path.join(root, 'cache'), source_root: repository },
    derived: { root: path.join(root, 'derived'), namespace: 'synthetic-library', library_tombstones: [], memory_tombstones: [] } });
  const artifacts = createEngineArtifacts(worker.channel, worker.ready.capacity.max_chunk_bytes);
  const library = createWorkerLibrary(worker.channel, worker.ready.capacity.max_chunk_bytes);
  const binding = { operation_id: 'synthetic-library-stage', attempt_id: 'attempt-1' };
  const signal = new AbortController().signal;
  try {
    for (const [revision, phrase] of [['revision_aki', 'AKI volume assessment and kidney injury.'],
      ['revision_transplant', 'Transplant rejection biopsy assessment.']]) {
      const input = await artifacts.upload(Buffer.from(JSON.stringify({ passages: [{ passage_id: 'passage_' + revision, text: phrase }] })),
        binding, ['read'], Date.now() + 120_000);
      const output = artifacts.output(16384, Date.now() + 120_000);
      try {
        const reference = await artifacts.run('library.stage', { artifact_handle: input.artifact_handle,
          artifact_revision: input.artifact_revision, offset: 0, length: input.bytes,
          document_id: 'document_synthetic', revision_id: revision, output }, binding);
        const staged = JSON.parse((await artifacts.read(reference, 16384, binding)).toString());
        assert.equal(staged.eligible, false);
      } finally {
        await artifacts.release(input.artifact_handle, binding);
        await artifacts.release(output.artifact_handle, binding);
      }
    }
    const query = revisionIds => library.query({ query: 'AKI volume', limit: 8, revisionIds,
      operationId: binding.operation_id, attemptId: binding.attempt_id, signal });
    assert.deepEqual(await query([]), []);
    assert.deepEqual(await query(['revision_aki']), [{ passage_id: 'passage_revision_aki', revision_id: 'revision_aki' }]);
    const output = artifacts.output(16384, Date.now() + 120_000);
    try { await artifacts.run('library.remove', { revision_ids: ['revision_aki'], output }, binding); }
    finally { await artifacts.release(output.artifact_handle, binding); }
    assert.deepEqual(await query(['revision_aki']), []);
    assert.equal(worker.channel.state().unsettled, 0);
  } finally { await worker.close(); }
});
