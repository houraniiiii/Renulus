// SPDX-License-Identifier: MIT
import { Effect } from 'effect';
import type { Plugin } from '@opencode/plugin/effect/plugin';
import { Tool } from '@opencode/schema/tool';
import { reject, text } from '../../storage/contracts.ts';
import type { EvidenceDomain } from './index.ts';
import type { EvidenceProvider } from './contracts.ts';
export interface EvidenceToolAuthority { operationId: string; attemptId: string; sessionId: string; grants: readonly string[] }
export interface EvidenceToolDependencies {
  evidence: EvidenceDomain;
  resolve(context: { sessionID: string; id: string }, signal: AbortSignal): Promise<EvidenceToolAuthority>;
  check(authority: EvidenceToolAuthority, signal: AbortSignal): Promise<void>;
}
export function createEvidenceTools(deps: EvidenceToolDependencies) {
  async function execute(action: 'search' | 'fetch', args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
    signal.throwIfAborted(); const authority = await deps.resolve(context, signal);
    if (authority.sessionId !== context.sessionID || !authority.operationId || !authority.attemptId) reject('evidence_tool_authority_invalid');
    if (!authority.grants.includes('renulus.evidence.' + action)) reject('evidence_tool_grant_denied');
    await deps.check(authority, signal);
    if (!args || typeof args !== 'object' || Array.isArray(args)) reject('evidence_tool_arguments_invalid');
    const input = args as { query?: string; providers?: EvidenceProvider[]; pmcid?: string };
    if (Object.keys(input).some(k => !(action === 'search' ? ['query','providers'] : ['pmcid']).includes(k))) reject('evidence_tool_arguments_invalid');
    const binding = { operationId: authority.operationId, signal, budget: { max_requests: 4, max_credits: 1 } };
    let value;
    if (action === 'search') {
      text(input.query, 1, 240);
      value = await deps.evidence.search({ ...binding, query: input.query, providers: input.providers ?? ['europe-pmc'] });
    } else {
      text(input.pmcid, 4, 14);
      value = await deps.evidence.fetch({ ...binding, pmcid: input.pmcid });
    }
    await deps.check(authority, signal);
    const current = await deps.resolve(context, signal);
    if (current.operationId !== authority.operationId || current.attemptId !== authority.attemptId || !current.grants.includes('renulus.evidence.' + action)) reject('evidence_tool_grant_denied');
    signal.throwIfAborted(); return value;
  }
  return { search: (args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) => execute('search', args, context, signal),
    fetch: (args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) => execute('fetch', args, context, signal),
    websearch(args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
      if (!args || typeof args !== 'object' || Object.keys(args).some(k => k !== 'query')) reject('evidence_tool_arguments_invalid');
      return execute('search', args, context, signal);
    },
    webfetch(args: unknown, context: { sessionID: string; id: string }, signal: AbortSignal) {
      if (!args || typeof args !== 'object' || Object.keys(args).some(k => !['url','format'].includes(k))) reject('evidence_tool_arguments_invalid');
      const input = args as { url: string; format?: string };
      text(input.url, 1, 2048);
      if (input.format !== undefined && !['text','markdown','html'].includes(input.format)) reject('evidence_tool_arguments_invalid');
      let url: URL; try { url = new URL(input.url); } catch { reject('evidence_url_denied'); }
      if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search || url.hash) reject('evidence_url_denied');
      const pattern = url.hostname === 'europepmc.org' ? /^\/articles\/(PMC[1-9][0-9]{0,10})\/?$/i :
        url.hostname === 'pmc.ncbi.nlm.nih.gov' ? /^\/articles\/(PMC[1-9][0-9]{0,10})\/?$/i :
        url.hostname === 'ncbi.nlm.nih.gov' ? /^\/pmc\/articles\/(PMC[1-9][0-9]{0,10})\/?$/i : null;
      const pmcid = pattern?.exec(url.pathname)?.[1]?.toUpperCase();
      if (!pmcid) reject('evidence_url_denied');
      return execute('fetch', { pmcid }, context, signal);
    } };
}
export function createEvidencePlugin(deps: EvidenceToolDependencies): Plugin {
  const bridge = createEvidenceTools(deps);
  return { id: 'renulus-evidence', effect: context => context.tool.transform(editor => {
    for (const action of ['search','fetch'] as const) editor.add({ name: 'renulus_evidence_' + action,
      description: action === 'search' ? 'Discover dated literature records using explicitly selected evidence providers. Discovery is not passage evidence.' : 'Fetch dated, licensed PMC passages. Canonical reviewed-source restrictions must still be applied before use as evidence.',
      input: (action === 'search' ? { type: 'object', additionalProperties: false, required: ['query'], properties: {
        query: { type: 'string', minLength: 1, maxLength: 240 }, providers: { type: 'array', minItems: 1, uniqueItems: true,
          items: { enum: ['europe-pmc','pubmed','brave','tavily','exa'] } } } } : { type: 'object', additionalProperties: false,
        required: ['pmcid'], properties: { pmcid: { type: 'string', pattern: '^PMC[1-9][0-9]{0,10}$' } } }) as never,
      options: { codemode: false, permission: 'renulus.evidence.' + action },
      execute: (args, ctx) => Effect.suspend(() => {
        let pending: Promise<Tool.Result> | undefined;
        return Effect.tryPromise({ try: signal => { pending = bridge[action](args, ctx, signal).then(value => ({ content: JSON.stringify(value) })); return pending; },
          catch: () => new Tool.Error({ message: 'Evidence retrieval failed. No fallback provider was called.', metadata: { code: 'evidence_tool_failed' } })
        }).pipe(Effect.onInterrupt(() => Effect.promise(async () => { await pending?.catch(() => {}); })));
      }) });
  }).pipe(Effect.asVoid) };
}
