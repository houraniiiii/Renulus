// SPDX-License-Identifier: MIT
import { randomUUID } from 'node:crypto';
import type { IncomingMessage } from 'node:http';
import type { CredentialAuthority, CredentialResult } from '../../../contracts/worker.ts';
import type { WorkerChannel } from '../workers/channel.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

type AccountProvider = CredentialAuthority['provider_id'];
/** Only authenticated Settings commands reach this object. Metadata contains refs,
 * never secret material; Go entry is the worker's protected native Windows prompt. */
export function createCredentialCommands(channel: WorkerChannel) {
  async function state(command: 'credential.activate' | 'credential.metadata'): Promise<CredentialResult> {
    const call = channel.submit(command, {}, { operation_id: 'settings_' + randomUUID().replaceAll('-', ''), attempt_id: '1' });
    const observed = await call.terminal; channel.release(call.requestId);
    const result = observed.reply.result;
    if (!observed.current || observed.reply.outcome !== 'committed_reference' || !result || !('credentials' in result)) reject('credential_metadata_unavailable');
    return result;
  }
  return {
    activate: () => state('credential.activate'), metadata: () => state('credential.metadata'),
    async execute(provider: AccountProvider, action: CredentialAuthority['action'], loginId?: string) {
      const metadata = await state('credential.metadata');
      const credential = metadata.credentials.find(c => c.provider_id === provider);
      if (!credential) reject('credential_metadata_unavailable');
      const operation = 'settings_' + randomUUID().replaceAll('-', '');
      const call = channel.submitBound(`credential.${action}`, (identity, revisions) => {
        const authority: CredentialAuthority = { authority_id: 'authority_' + randomUUID().replaceAll('-', ''), source: 'settings',
          action, provider_id: provider, identity, revisions, retention: 'saved', credential_ref: credential.credential_ref,
          credential_revision: credential.credential_revision, expires_at_ms: Date.now() + 120_000 };
        return { provider_id: provider, authority, ...(loginId === undefined ? {} : { login_id: loginId }) };
      }, { operation_id: operation, attempt_id: '1' });
      const observed = await call.terminal; channel.release(call.requestId);
      const result = observed.reply.result;
      if (!observed.current || observed.reply.outcome !== 'committed_reference' || !result || !('credentials' in result)) {
        reject(result && 'code' in result && typeof result.code === 'string' ? result.code : 'credential_operation_failed');
      }
      return result;
    },
  };
}
export type CredentialCommands = ReturnType<typeof createCredentialCommands>;
export async function credentialCommand(request: IncomingMessage, url: URL, credentials?: CredentialCommands) {
  const match = /^\/api\/v1\/settings\/credentials(?:\/(codex|opencode-go)\/(connect|refresh|forget|login-status|login-cancel))?$/.exec(url.pathname);
  if (!match) return undefined;
  if (!credentials) reject('credential_host_unavailable');
  if (!match[1] && request.method === 'GET') return { status: 200, value: await credentials.metadata() };
  if (!match[1] && request.method === 'POST') {
    exact(await readJsonObject(request, 4096), []); return { status: 200, value: await credentials.activate() };
  }
  if (request.method !== 'POST') reject('storage_invalid_command');
  const body = await readJsonObject(request, 4096), login = match[2].startsWith('login-');
  exact(body, login ? ['login_id'] : []);
  if (login && (match[1] !== 'codex' || typeof body.login_id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(body.login_id))) reject('storage_invalid_command');
  return { status: 200, value: await credentials.execute(match[1] as AccountProvider,
    match[2] as CredentialAuthority['action'], login ? body.login_id as string : undefined) };
}
