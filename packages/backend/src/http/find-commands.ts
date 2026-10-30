// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import { reject } from '../storage/contracts.ts';
import { commandNumber } from './project-commands.ts';
import type { FindDomain } from '../domain/find/index.ts';

/** Authenticated literal global search/navigation. `/search` keeps the retained `archived` flag; `/find` takes the explicit lifecycle. */
export async function findCommand(request: IncomingMessage, url: URL, find?: FindDomain): Promise<{ status: number; value: unknown } | undefined> {
  if (!find || request.method !== 'GET' || !['/api/v1/search', '/api/v1/find'].includes(url.pathname)) return undefined;
  const query = url.searchParams, lifecycle = url.pathname.endsWith('/search') ? query.get('archived') === 'true' ? 'all' : 'active' : query.get('lifecycle') ?? 'active';
  if (!['active', 'archived', 'all'].includes(lifecycle)) reject('storage_invalid_command');
  return { status: 200, value: await find.find({ query: query.get('q') ?? '', scope: { lifecycle: lifecycle as 'active' | 'archived' | 'all', projectId: query.get('project_id') },
    cursor: query.get('cursor'), limit: commandNumber(url, 'limit', 30) }) };
}
