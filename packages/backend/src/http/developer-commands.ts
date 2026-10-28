// SPDX-License-Identifier: MIT
import { randomUUID } from 'node:crypto';
import type { IncomingMessage } from 'node:http';
import type { DeveloperOptions, OwnedWorktree } from '../../../harness/src/developer-plugin.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

export interface DeveloperCommands {
  approvals: ReturnType<typeof createWorktreeApprovals>;
  authority: { renew(leaseId: string): Promise<unknown> };
}
/** Supplies `approveWorktreeRemoval`: a removal waits for a direct user answer and is refused on abort. */
export function createWorktreeApprovals() {
  const pending = new Map<string, { worktree: OwnedWorktree & { force: boolean }; answer(approved: boolean): void }>();
  const approve: NonNullable<DeveloperOptions['approveWorktreeRemoval']> = (worktree, signal) => new Promise<boolean>(resolve => {
    const id = randomUUID(), done = (approved: boolean) => { pending.delete(id); signal.removeEventListener('abort', cancel); resolve(approved); };
    const cancel = () => done(false);
    pending.set(id, { worktree, answer: done }); signal.addEventListener('abort', cancel, { once: true }); if (signal.aborted) cancel();
  });
  return { approve, pending: () => [...pending].map(([id, item]) => ({ id, ...item.worktree })),
    answer(id: string, approved: boolean) { (pending.get(id) ?? reject('developer_approval_stale')).answer(approved); } };
}

/** Authenticated user commands only; the model catalogue never reaches these routes. */
export async function developerCommand(request: IncomingMessage, url: URL, developer?: DeveloperCommands): Promise<{ status: number; value: unknown } | undefined> {
  const match = /^\/api\/v1\/developer\/(?:(worktree-removals)(?:\/([A-Za-z0-9-]{1,64}))?|leases\/([A-Za-z0-9_-]{1,128})\/(renew))$/.exec(url.pathname);
  if (!match) return undefined;
  if (!developer) reject('developer_host_unavailable');
  if (match[1] && !match[2] && request.method === 'GET') return { status: 200, value: developer.approvals.pending() };
  if (request.method !== 'POST') reject('storage_invalid_command');
  if (match[2]) {
    const body = await readJsonObject(request, 1024); exact(body, ['approve']);
    if (typeof body.approve !== 'boolean') reject('storage_invalid_command');
    developer.approvals.answer(match[2], body.approve); return { status: 200, value: { answered: match[2] } };
  }
  if (match[4]) { exact(await readJsonObject(request, 1024), []); return { status: 200, value: await developer.authority.renew(match[3]) }; }
  reject('storage_invalid_command');
}
