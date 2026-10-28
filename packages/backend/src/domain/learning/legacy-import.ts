// SPDX-License-Identifier: MIT
import type { LearningStorage, RuntimeIdentity } from './contracts.ts';
import type { openLearningHarness } from '../../../../harness/src/learning-host.ts';
import { reject } from '../../storage/contracts.ts';

export async function importLegacyHistory(storage: LearningStorage,
  native: Pick<Awaited<ReturnType<typeof openLearningHarness>>, 'transferCommand'>,
  identity: RuntimeIdentity, threadId: string, expectedRevision: number) {
  const prepared = await storage.command({ type: 'learning.legacy.prepare', threadId, expectedRevision, identity });
  if (!prepared) return;
  const { document, sessionId, sourceDigest, sourceStamp, operationId, messageCount } = prepared;
  const frame = { ...identity, operationId, attemptId: '1' };
  const target = { sessionId, bundleDigest: sourceDigest };
  const bytes = Buffer.from(document), chunks: string[] = [];
  for (let start = 0; start < bytes.length;) {
    let end = Math.min(start + 48 * 1024, bytes.length);
    while (end < bytes.length && (bytes[end]! & 0xc0) === 0x80) end--;
    chunks.push(bytes.subarray(start, end).toString('utf8')); start = end;
  }
  for (let partIndex = 0; partIndex < chunks.length; partIndex++) {
    await native.transferCommand(frame, 'session.import.stage', { ...target, partIndex, partCount: chunks.length,
      totalBytes: Buffer.byteLength(document), chunk: chunks[partIndex] });
  }
  const result = await native.transferCommand(frame, 'session.import', target) as { state: string; sessionId: string; bundleDigest: string; messageCount: number };
  if (result.state !== 'verified' || result.sessionId !== sessionId || result.bundleDigest !== sourceDigest || result.messageCount !== messageCount) reject('learning_migration_readback');
  try {
    await storage.command({ type: 'learning.legacy.activate', threadId, sourceDigest, sourceStamp, identity });
  } catch (error) {
    await storage.command({ type: 'learning.purge.enqueue', identity, sessionId, operationId: operationId + ':purge', attemptId: '1' });
    throw error;
  }
  await native.transferCommand(frame, 'operation.retire', {});
}
