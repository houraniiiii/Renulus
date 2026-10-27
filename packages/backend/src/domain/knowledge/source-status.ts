// SPDX-License-Identifier: MIT
// Port of knowledge/source_status.py identity/version/scope projection. No acquisition or network.
import type { DatabaseSync } from 'node:sqlite';
import { canonical, digest, rows } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';
import type { Json, Metadata } from './contracts.ts';

type Event = { source_id: string; identity: Record<string, Json>; changes: Record<string, Json>;
  scope?: { topic_ids?: string[]; locators?: string[] } };
const changeFields = new Set(['publication_status', 'publication_date', 'revision_date', 'latest_final_verified', 'content_reviewed', 'review_due',
  'correction', 'retracted', 'superseded', 'repository_removed', 'access_changed', 'supersedes', 'replaced_topics', 'excluded_pages']);
function articleIds(input: Record<string, unknown>) {
  const result: Record<string, string> = {};
  for (const key of ['doi', 'pmid', 'pmcid']) {
    if (!input[key]) continue; let value = String(input[key]).trim();
    if (key === 'doi') value = value.replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, '').toLowerCase();
    if (key === 'pmcid') value = value.toUpperCase();
    if (!(key === 'doi' ? /^10\.\d{4,9}\/[^\s"<>]+$/ : key === 'pmcid' ? /^PMC[1-9]\d{0,11}$/ : /^[1-9]\d{0,11}$/).test(value)) reject('source_status_invalid');
    result[key] = value;
  }
  return result;
}
function urlIds(value: unknown) {
  let url: URL; try { url = new URL(String(value)); } catch { return {}; }
  const path = decodeURIComponent(url.pathname).replace(/^\/+|\/+$/g, ''), host = url.hostname.toLowerCase();
  if (['doi.org', 'dx.doi.org'].includes(host)) return articleIds({ doi: path });
  if (host === 'pubmed.ncbi.nlm.nih.gov' && /^\d+$/.test(path)) return articleIds({ pmid: path });
  const epmc = /^article\/(MED|PMC)\/([A-Za-z0-9]+)$/i.exec(path);
  if (['europepmc.org', 'www.europepmc.org'].includes(host) && epmc) return articleIds({ [epmc[1].toUpperCase() === 'MED' ? 'pmid' : 'pmcid']: epmc[2] });
  const pmc = /(?:^|\/)articles\/(PMC\d+)(?:\/|$)/i.exec(path);
  return ['pmc.ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov'].includes(host) && pmc ? articleIds({ pmcid: pmc[1] }) : {};
}
function samePublication(metadata: Metadata, event: Event) {
  if (metadata.source_id !== event.source_id) return false;
  const wanted = { ...urlIds(event.identity.canonical_url), ...articleIds(event.identity) }, actual = { ...urlIds(metadata.canonical_url), ...articleIds(metadata) };
  if (Object.keys(wanted).length) return !Object.entries(wanted).some(([key, value]) => actual[key] && actual[key] !== value) && Object.entries(wanted).some(([key, value]) => actual[key] === value);
  return !!event.identity.canonical_url && String(event.identity.canonical_url).split('#')[0] === String(metadata.canonical_url ?? '').split('#')[0];
}
function acquiredDigest(metadata: Metadata) {
  if (metadata.original_sha256) return metadata.original_sha256;
  for (const note of metadata.notes as string[] ?? []) {
    if (!note.startsWith('renulus-acquired-v1:')) continue;
    try { const v = JSON.parse(note.slice(20)); if (v.adapter === 'pmc-acquired-jats-v1' && v.article_version === metadata.edition && /^[a-f0-9]{64}$/.test(v.original_sha256)) return v.original_sha256; } catch { /* Keep immutable provenance; malformed legacy note grants no identity. */ }
  }
  return null;
}
function changes(metadata: Metadata, event: Event) {
  if (!samePublication(metadata, event)) return {};
  const { identity, changes, scope = {} } = event, acquired = metadata.asset_role?.includes('acquired-jats');
  const bound = 'edition' in identity && 'original_sha256' in identity;
  const exact = bound && metadata.edition === identity.edition && acquiredDigest(metadata) === identity.original_sha256;
  const scoped = !(scope.topic_ids?.length && (metadata.topic_ids as string[] | undefined)?.length && !scope.topic_ids.some(id => (metadata.topic_ids as string[]).includes(id))) &&
    !(scope.locators?.length && !scope.locators.some(id => id === metadata.collection_chapter || id === metadata.collection_section));
  if (scoped && (exact || !acquired && !bound)) return changes;
  const result: Record<string, Json> = {};
  for (const [key, value] of Object.entries(changes)) {
    if (acquired && ['retracted', 'repository_removed', 'access_changed'].includes(key) && value === true) result[key] = value;
    if (scoped && acquired && (['latest_final_verified', 'content_reviewed'].includes(key) && value === false || key === 'publication_status' && value !== 'final' || key === 'superseded' && value === true && !bound || key === 'correction' && typeof value === 'string' && !!value.trim())) result[key] = value;
  }
  return result;
}
export function effectiveKnowledgeMetadata(db: DatabaseSync, metadata: Metadata): Metadata {
  let value = { ...metadata };
  for (const row of rows(db, 'SELECT id,request_hash,payload_json FROM knowledge_source_status_events WHERE source_id=? ORDER BY created_at,rowid', metadata.source_id)) {
    let event: Event;
    try { event = JSON.parse(String(row.payload_json)); } catch { reject('source_status_invalid'); }
    if (!event.identity || !event.changes || Array.isArray(event.identity) || Array.isArray(event.changes) || Object.keys(event.changes).some(key => !changeFields.has(key)) || digest(canonical(event)) !== row.request_hash) reject('source_status_invalid');
    const update = changes(value, event);
    if (Object.keys(update).length) { value = { ...value, ...update };
      if (value.publication_status !== 'final' || value.retracted || value.superseded || value.repository_removed) value.latest_final_verified = false;
    }
  }
  return value;
}
/** Call after appending a validated event in the integrator's current transaction.
 * Canonical metadata, context invalidation and memory-support reconciliation can
 * then commit atomically; an unrelated publication receives no restrictions.
 */
export function projectKnowledgeSourceStatus(db: DatabaseSync, sourceId: string) {
  let count = 0;
  for (const row of rows(db, 'SELECT r.id,r.metadata_json FROM knowledge_revisions r JOIN knowledge_documents d ON d.id=r.document_id WHERE d.source_id=? AND d.deleted_at IS NULL', sourceId)) {
    const prior = JSON.parse(String(row.metadata_json)), next = effectiveKnowledgeMetadata(db, prior);
    if (canonical(prior) !== canonical(next)) { db.prepare('UPDATE knowledge_revisions SET metadata_json=? WHERE id=?').run(JSON.stringify(next), row.id); count++; }
  }
  return count;
}
