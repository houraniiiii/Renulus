// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import type { EvidenceDomain } from '../evidence/index.ts';
import type { UpdatesNativePort } from './contracts.ts';
import { reject } from '../../storage/contracts.ts';
import { canonical } from '../../storage/schema.ts';

export function createUpdatesRetrieval(evidence: Pick<EvidenceDomain, 'discoverDated'>): Pick<UpdatesNativePort, 'check'> {
  return { async check(input, signal) {
    const discovered = await evidence.discoverDated({ query: String(input.target.query ?? input.target.title ?? input.target.url ?? input.route.id).slice(0, 240),
      providers: ['europe-pmc'], budget: { max_requests: 1, max_credits: 0 }, operationId: input.token, signal });
    const result = discovered['europe-pmc'];
    if (!result || result.error) reject(result?.error ?? 'evidence_failed');
    const metadata = { provider: 'europe-pmc', queried_at: result.queried_at, verification: 'discovery-only', passage_evidence: false };
    const entries = result.records.map(record => ({ external_id: String(record.id), title: String(record.title), url: String(record.url),
      publication_date: typeof record.publication_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(record.publication_date) ? record.publication_date : null,
      metadata: { ...record, ...metadata } }));
    return { digest: createHash('sha256').update(canonical(result.records)).digest('hex'),
      links: entries.map(e => ({ url: e.url, label: e.title })), entries, metadata };
  } };
}
