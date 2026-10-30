// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { BackendSelector } from '../host/handoff.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

export interface SelectRequest { generationPath: string; rollback: boolean }
/** The selected owner's identity: a request must name exactly the owner and epoch it expects. */
export interface RecoveryPort {
  authority: { ownerGeneration: string; authorityEpoch: number; selectorSha256: string | null };
  /** `close` closes admission, drains admitted work, then settles the canonical writer; it returns the closed frontier digest. */
  select(request: SelectRequest, close: () => Promise<string>): Promise<BackendSelector>;
}
export const RECOVERY_SELECT = '/api/v1/runtime/recovery/select';
/** Publishes a prepared candidate generation as held. Validation happens before anything is closed. */
export async function recoveryCommand(request: IncomingMessage, port: RecoveryPort, close: () => Promise<string>): Promise<{ status: number; value: unknown }> {
  const body = await readJsonObject(request, 4096);
  const { rollback = false, ...required } = body;
  exact(required, ['generation_path', 'expected_owner_generation', 'expected_authority_epoch', 'expected_selector_sha256']);
  if (typeof rollback !== 'boolean' || typeof required.generation_path !== 'string' ||
      !/^generations\/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(required.generation_path)) reject('invalid_request');
  const { authority } = port;
  if (required.expected_owner_generation !== authority.ownerGeneration || required.expected_authority_epoch !== authority.authorityEpoch ||
      required.expected_selector_sha256 !== authority.selectorSha256) reject('recovery_owner_stale');
  const selector = await port.select({ generationPath: required.generation_path, rollback }, close);
  return { status: 200, value: { state: selector.state, writer: selector.writer, generation: selector.generation,
    authority_epoch: selector.authorityEpoch, generation_path: selector.generationPath, manifest_sha256: selector.manifestSha256 } };
}
