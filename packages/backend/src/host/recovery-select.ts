// SPDX-License-Identifier: MIT
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { RecoveryPort } from '../http/recovery-commands.ts';
import { owned } from '../storage/ownership.ts';
import type { SelectedWriterAuthority } from '../storage/selected-owner.ts';
import { GENERATION_MANIFEST, observeGeneration, selectPreparedGeneration, type HandoffGeneration, type HandoffOptions } from './handoff.ts';

const manifestOf = (root: string) => JSON.parse(readFileSync(owned(root, join(root, GENERATION_MANIFEST)), 'utf8')) as HandoffGeneration;

/** Selection by the selected owner: the closed CURRENT generation is observed from real bytes, the prepared
 * candidate is validated member by member, and the selector is published held, last. */
export function createRecoveryPort(options: { authority: SelectedWriterAuthority; verifyBinaries: HandoffOptions['verifyBinaries'] }): RecoveryPort {
  const { authority } = options;
  return {
    authority: { ownerGeneration: authority.ownerGeneration, authorityEpoch: authority.authorityEpoch, selectorSha256: authority.selectorSha256 },
    select: (request, close) => {
      const generationRoot = owned(authority.profileRoot, resolve(authority.profileRoot, request.generationPath));
      return selectPreparedGeneration({ authority, generationRoot, manifest: manifestOf(generationRoot), rollback: request.rollback,
        verifyBinaries: options.verifyBinaries,
        closeAndSnapshot: async () => {
          const frontierDigest = await close(), current = manifestOf(authority.generationRoot);
          return { ...current, frontierDigest, members: observeGeneration(authority.generationRoot, current) };
        } });
    },
  };
}
