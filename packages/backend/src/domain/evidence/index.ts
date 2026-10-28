// SPDX-License-Identifier: MIT
import { randomUUID } from 'node:crypto';
import type { HttpResult, EvidencePlan } from '../../../../contracts/worker.ts';
import type { DatedDiscovery, EvidenceConnection, EvidenceDomainOptions, EvidencePassage, EvidenceProvider, EvidenceSearch } from './contracts.ts';
import { createEngineArtifacts } from '../../workers/artifacts.ts';
import { integer, reject, text } from '../../storage/contracts.ts';
export const official = {
  'europe-pmc': 'https://www.ebi.ac.uk/europepmc/webservices/rest',
  pubmed: 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils', brave: 'https://api.search.brave.com/res/v1/web/search',
  tavily: 'https://api.tavily.com/search', exa: 'https://api.exa.ai/search',
};
export function createEvidenceDomain({ storage, worker, check, endpoints = {} }: EvidenceDomainOptions) {
  const artifacts = createEngineArtifacts(worker.channel, worker.maxChunkBytes);
  async function run(operationId: string, signal: AbortSignal, input: Pick<EvidencePlan, 'action'> & Partial<EvidencePlan>,
    settle?: (result: HttpResult | null) => Promise<void>): Promise<Record<string, unknown>> {
    const id = 'evidence_' + randomUUID().replaceAll('-', '');
    const binding = { operation_id: operationId, attempt_id: id };
    const output = artifacts.output(8 * 1024 * 1024, Date.now() + 120_000);
    let settled = false;
    let call: ReturnType<typeof worker.channel.submitBound> | undefined;
    let cancellation: Promise<void> | undefined;
    const cancel = () => { cancellation ??= (async () => {
      if (!call) return;
      const admitted = await call.admission;
      if (admitted.reply.settlement.state === 'settled') return;
      const control = worker.channel.submit('worker.settle', { action: 'cancel', target: { identity: admitted.reply.identity,
        request_sha256: admitted.reply.request_sha256, worker_lease: admitted.reply.settlement.worker_lease }, revisions: null, artifact_handle: null }, binding);
      await control.terminal; worker.channel.release(control.requestId);
    })(); void cancellation.catch(() => {}); };
    try {
      signal.throwIfAborted(); await check(operationId, signal);
      call = worker.channel.submitBound('evidence.run', (identity, revisions) => ({ ...input,
        permit_id: id, admission_receipt: id, identity, revisions, retention: worker.retention, expires_at_ms: output.expires_at_ms, output }), binding);
      signal.addEventListener('abort', cancel, { once: true }); if (signal.aborted) cancel();
      const observed = await call.terminal; worker.channel.release(call.requestId); await cancellation;
      const result = observed.reply.result as HttpResult;
      if (!result || result.tag !== 'http' || result.admission_receipt !== id || result.identity.request_id !== call.requestId) reject('evidence_reply_mismatch');
      await settle?.(result); settled = true;
      if (result.outcome !== 'committed_reference' || !result.artifact) reject(result.code ?? 'evidence_failed');
      if (!observed.current) reject('evidence_stale');
      const body = await artifacts.read(result.artifact, output.max_bytes, binding, signal);
      await check(operationId, signal); signal.throwIfAborted();
      return JSON.parse(body.toString('utf8'));
    } catch (error) {
      if (!settled) await settle?.(call ? null : { requests_started: 0, effect: 'not_sent' } as HttpResult);
      throw error;
    } finally {
      signal.removeEventListener('abort', cancel); await cancellation;
      await artifacts.release(output.artifact_handle, binding);
    }
  }
  async function connections(input: { operationId: string; signal: AbortSignal }): Promise<EvidenceConnection[]> {
    return (await run(input.operationId, input.signal, { action: 'status' })).connections as EvidenceConnection[];
  }
  async function perform(provider: EvidenceProvider, input: EvidenceSearch, action: 'search' | 'fetch', pmcid?: string): Promise<Record<string, unknown> & { usage: DatedDiscovery['usage'] }> {
    const status = (await connections(input)).find(row => row.provider === provider);
    if (!status) reject('retrieval_provider_unknown');
    const keyed = !['europe-pmc','pubmed'].includes(provider);
    if (keyed && (!status.configured || !status.enabled || !status.selected || !status.credential_ref || status.credential_revision === null)) reject('retrieval_tool_disabled');
    const requests = action === 'fetch' ? 2 : provider === 'pubmed' ? 2 : 1, credits = keyed ? 1 : 0;
    if (requests > input.budget.max_requests || credits > input.budget.max_credits) reject('evidence_request_budget');
    const id = 'evidence_reservation_' + randomUUID().replaceAll('-', '');
    await check(input.operationId, input.signal);
    await storage.command({ type: 'evidence.reserve', id, operation_id: input.operationId, provider,
      day: new Date().toISOString().slice(0,10), requests, credits, request_limit: status.daily_request_limit, credit_limit: status.daily_credit_limit });
    const base_url = endpoints[provider]?.base_url ?? official[provider], url = new URL(base_url);
    const endpoint = endpoints[provider] ?? { host: url.hostname, port: 443, private_network: false };
    let usage = { requests, credits, uncertain: true };
    const data = await run(input.operationId, input.signal, { action, provider, query: action === 'search' ? input.query : null,
      pmcid: pmcid ?? null, limit: 5, max_requests: requests, base_url,
      endpoint: { host: endpoint.host, port: endpoint.port, private_network: endpoint.private_network },
      credential: keyed ? { ref: status.credential_ref!, revision: status.credential_revision! } : null }, async result => {
      await storage.command({ type: 'evidence.settle', id, requests_started: result?.requests_started ?? 0, effect: result?.effect ?? 'uncertain' });
      usage = { requests: result?.effect === 'uncertain' || !result ? requests : result.requests_started ?? 0,
        credits: result && result.effect !== 'uncertain' && !result.requests_started ? 0 : credits, uncertain: !result || result.effect === 'uncertain' };
    }).catch(error => { throw Object.assign(error instanceof Error ? error : new Error('evidence_failed'), { usage }); });
    return { ...data, usage };
  }
  async function discoverDated(input: EvidenceSearch): Promise<Partial<Record<EvidenceProvider, DatedDiscovery>>> {
    text(input.query, 1, 240); integer(input.budget.max_requests, 0, 100); integer(input.budget.max_credits, 0, 100);
    if (!Array.isArray(input.providers) || !input.providers.length || new Set(input.providers).size !== input.providers.length || input.providers.some(p => !Object.hasOwn(official, p))) reject('retrieval_provider_unknown');
    const plannedRequests = input.providers.reduce((sum, p) => sum + (p === 'pubmed' ? 2 : 1), 0);
    const plannedCredits = input.providers.filter(p => !['europe-pmc','pubmed'].includes(p)).length;
    if (plannedRequests > input.budget.max_requests || plannedCredits > input.budget.max_credits) reject('evidence_request_budget');
    const result: Partial<Record<EvidenceProvider, DatedDiscovery>> = {};
    for (const provider of input.providers) {
      try {
        const value = await perform(provider, input, 'search');
        result[provider] = { records: value.records as Record<string, unknown>[], queried_at: String(value.queried_at),
          verification: 'discovery-only', passage_evidence: false, usage: value.usage };
      } catch (error) {
        if (input.signal.aborted) throw error;
        result[provider] = { records: [], queried_at: new Date().toISOString(), verification: 'discovery-only', passage_evidence: false,
          usage: error && typeof error === 'object' && 'usage' in error ? error.usage as DatedDiscovery['usage'] : { requests: 0, credits: 0, uncertain: false }, error: error && typeof error === 'object' && 'code' in error ? String(error.code) : 'evidence_failed' };
      }
    }
    return result;
  }
  async function current(stamp: string, signal: AbortSignal) {
    signal.throwIfAborted(); await storage.command({ type: 'evidence.current', stamp });
  }
  return { search: discoverDated, discoverDated, connections, current,
    async fetch(input: { pmcid: string; budget: EvidenceSearch['budget']; operationId: string; signal: AbortSignal }) {
      if (typeof input.pmcid !== 'string' || !/^PMC[1-9][0-9]{0,10}$/.test(input.pmcid)) reject('evidence_pmcid_invalid');
      integer(input.budget.max_requests, 0, 100); integer(input.budget.max_credits, 0, 100);
      const result = await perform('europe-pmc', { ...input, query: input.pmcid, providers: ['europe-pmc'] }, 'fetch', input.pmcid);
      const checked = await storage.command({ type: 'evidence.check', passages: result.passages as EvidencePassage[] });
      await check(input.operationId, input.signal);
      await current(checked.stamp, input.signal);
      return { ...result, passages: checked.passages, source_restrictions_checked: true as const, source_restrictions_revision: checked.stamp };
    } };
}
export type EvidenceDomain = ReturnType<typeof createEvidenceDomain>;
