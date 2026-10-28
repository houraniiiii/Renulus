// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import type { EvidenceDomain } from '../evidence/index.ts';
import type { CheckInput, Observation, UpdatesNativePort } from './contracts.ts';
import { reject } from '../../storage/contracts.ts';
import { canonical } from '../../storage/schema.ts';

const sourcePageBytes = 2_000_000;
const publicationMedia = ['text/html', 'application/xhtml+xml', 'text/plain', 'application/xml', 'text/xml', 'application/pdf', 'application/json'];
const sha256 = (value: string | Uint8Array) => createHash('sha256').update(value).digest('hex');
const entities: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
const decode = (value: string) => value.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (match, name: string) =>
  name[0] === '#' ? String.fromCodePoint(name[1].toLowerCase() === 'x' ? parseInt(name.slice(2), 16) : Number(name.slice(1))) : entities[name.toLowerCase()] ?? match);
/** Publication links of an official page, as `runtime/renulus/updates/service.py` selects them: https PDFs or guideline/correction/draft/retraction notices. */
function publicationLinks(html: string, base: string) {
  const links: { url: string; label: string }[] = [];
  for (const [, attributes, inner] of html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)) {
    const href = /\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/i.exec(attributes);
    if (!href) continue;
    let url: URL;
    try { url = new URL(decode(href[1] ?? href[2] ?? href[3]), base); } catch { continue; }
    const label = decode(inner.replace(/<[^>]*>/g, '\0')).split('\0').map(part => part.trim()).filter(Boolean).join(' ').slice(0, 500);
    if (url.protocol === 'https:' && (url.href.toLowerCase().includes('.pdf') || ['guideline', 'corrigend', 'correction', 'draft', 'retract'].some(word => label.toLowerCase().includes(word))))
      links.push({ url: url.href, label });
  }
  return links.sort((a, b) => a.url < b.url ? -1 : a.url > b.url ? 1 : a.label < b.label ? -1 : a.label > b.label ? 1 : 0);
}
/** The sorted links in Python's `json.dumps(sort_keys=True)` form, so a profile moved from the Python writer keeps its fingerprints. */
const linksFingerprint = (links: { url: string; label: string }[]) => sha256('[' + links.map(link => '{"label": ' + pythonString(link.label) + ', "url": ' + pythonString(link.url) + '}').join(', ') + ']');
const pythonString = (value: string) => JSON.stringify(value).replace(/[\u007f-￿]/g, char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));

export function createUpdatesRetrieval(evidence: Pick<EvidenceDomain, 'discoverDated' | 'page'>): Pick<UpdatesNativePort, 'check'> {
  async function discover(input: CheckInput, signal: AbortSignal): Promise<Observation> {
    const discovered = await evidence.discoverDated({ query: String(input.target.query ?? input.target.title ?? input.target.url ?? input.route.id).slice(0, 240),
      providers: ['europe-pmc'], budget: { max_requests: 1, max_credits: 0 }, operationId: input.token, signal });
    const result = discovered['europe-pmc'];
    if (!result || result.error) reject(result?.error ?? 'evidence_failed');
    const metadata = { provider: 'europe-pmc', queried_at: result.queried_at, verification: 'discovery-only', passage_evidence: false };
    const entries = result.records.map(record => ({ external_id: String(record.id), title: String(record.title), url: String(record.url),
      publication_date: typeof record.publication_date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(record.publication_date) ? record.publication_date : null,
      metadata: { ...record, ...metadata } }));
    return { digest: sha256(canonical(result.records)), links: entries.map(e => ({ url: e.url, label: e.title })), entries, metadata };
  }
  return { async check(input, signal) {
    if (input.route.kind === 'literature') return discover(input, signal);
    const { target } = input, publication = input.route.kind === 'publication';
    const page = await evidence.page({ url: String(target.url), hosts: target.hosts, maxBytes: publication ? Number(target.max_bytes) : sourcePageBytes, operationId: input.token, signal });
    if (!publication) {
      const links = publicationLinks(page.body.toString('utf8'), page.final_url);
      return { digest: linksFingerprint(links), links, entries: [], metadata: { final_url: page.final_url } };
    }
    const media_type = (page.headers['content-type'] ?? '').split(';')[0].trim().toLowerCase();
    if (new URL(String(target.url)).pathname.toLowerCase().endsWith('.pdf')) { if (!page.body.subarray(0, 5).equals(Buffer.from('%PDF-'))) reject('publication_format_changed'); }
    else if (!publicationMedia.includes(media_type)) reject('publication_format_unsupported');
    const digest = sha256(page.body);
    return { digest, links: [], entries: [], metadata: { sha256: digest, bytes: page.body.length, media_type, final_url: page.final_url } };
  } };
}
