// SPDX-License-Identifier: MIT
import { exact, integer, reject, text } from '../../storage/contracts.ts';
import type { SourceTarget, Review, ObjectValue, Observation, CheckRoute } from './contracts.ts';
export function hash(value: unknown) { if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) reject('updates_invalid'); }
export function date(value: unknown) { text(value, 10, 10); if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || new Date(value + 'T00:00:00Z').toISOString().slice(0, 10) !== value) reject('updates_invalid'); }
export function https(value: unknown) { text(value, 1, 2000); let url: URL; try { url = new URL(value); } catch { reject('updates_invalid'); } if (url.protocol !== 'https:' || !url.hostname || url.username || url.password || url.port && url.port !== '443') reject('updates_invalid'); return url; }
export function strings(value: unknown, maximum = 100) { if (!Array.isArray(value) || value.length > maximum) reject('updates_invalid'); for (const item of value) text(item, 1, 1000); }
export function route(value: CheckRoute) { exact(value, ['kind', 'id']); if (!['source', 'publication', 'literature'].includes(value.kind)) reject('updates_invalid'); text(value.id, 1, 200); }
export function article(input: ObjectValue) {
  const result: Record<string, string> = {};
  for (const key of ['doi', 'pmid', 'pmcid']) if (input[key]) {
    text(input[key], 1, 500); let value = input[key].trim();
    if (key === 'doi') value = value.replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, '').toLowerCase();
    if (key === 'pmcid') value = value.toUpperCase();
    if (!(key === 'doi' ? /^10\.\d{4,9}\/[^\s"<>]+$/ : key === 'pmcid' ? /^PMC\d{1,12}$/ : /^\d{1,12}$/).test(value)) reject('review_identity_invalid'); result[key] = value;
  }
  return result;
}
export function urlArticle(value: unknown): ObjectValue {
  if (!value) return {}; const url = https(value), path = decodeURIComponent(url.pathname).replace(/^\/+|\/+$/g, '');
  if (['doi.org', 'dx.doi.org'].includes(url.hostname)) return article({ doi: path });
  if (url.hostname === 'pubmed.ncbi.nlm.nih.gov' && /^\d+$/.test(path)) return article({ pmid: path });
  const epmc = /^article\/(MED|PMC)\/([A-Za-z0-9]+)$/i.exec(path);
  if (['europepmc.org', 'www.europepmc.org'].includes(url.hostname) && epmc) return article({ [epmc[1].toUpperCase() === 'MED' ? 'pmid' : 'pmcid']: epmc[2] });
  const pmc = /(?:^|\/)articles\/(PMC\d+)(?:\/|$)/i.exec(path);
  return ['pmc.ncbi.nlm.nih.gov', 'www.ncbi.nlm.nih.gov'].includes(url.hostname) && pmc ? article({ pmcid: pmc[1] }) : {};
}
export function matches(source: ObjectValue, target: SourceTarget) {
  if ((source.register_id ?? source.source_id) !== target.register_id || target.pinned_source_id && (source.id ?? source.pinned_source_id) !== target.pinned_source_id) return false;
  const wanted = article(target), actual = { ...urlArticle(source.url ?? source.canonical_url), ...article(source) };
  if (Object.keys(wanted).length) return !Object.entries(wanted).some(([k, v]) => actual[k] && actual[k] !== v) && Object.entries(wanted).some(([k, v]) => actual[k] === v);
  return target.canonical_url ? String(source.url ?? source.canonical_url ?? '').split('#')[0] === target.canonical_url.split('#')[0] : !!target.pinned_source_id;
}
const changes = ['publication_status', 'publication_date', 'revision_date', 'latest_final_verified', 'content_reviewed', 'review_due', 'correction', 'retracted', 'superseded', 'repository_removed', 'access_changed', 'supersedes', 'replaced_topics', 'excluded_pages'];
export function validateReview(value: Review) {
  exact(value, ['summary', 'topic_ids', 'reviewer', 'state', 'evidence', 'target', 'changes']); text(value.summary, 0, 8000); strings(value.topic_ids);
  if (!['learner', 'assistant'].includes(value.reviewer) || !['reviewed', 'dismissed'].includes(value.state)) reject('updates_invalid');
  if (!Array.isArray(value.evidence) || value.evidence.length > 20) reject('updates_invalid');
  for (const e of value.evidence) { exact(e, ['url', 'locator', 'finding', 'checked_on', 'inspected', ...('sha256' in e ? ['sha256'] : [])]); https(e.url); text(e.locator, 1, 1000); text(e.finding, 1, 4000); if (!e.locator.trim() || !e.finding.trim() || e.inspected !== true) reject('review_evidence_invalid'); date(e.checked_on); if (e.checked_on > new Date().toISOString().slice(0, 10)) reject('review_evidence_invalid'); if (e.sha256 !== undefined && e.sha256 !== null) hash(e.sha256); }
  if (value.state === 'reviewed' && (!value.summary.trim() || !value.evidence.length)) reject('review_evidence_required');
  const patch: ObjectValue = value.changes; exact(patch, Object.keys(patch).filter(k => changes.includes(k)));
  if (Object.keys(patch).length && !value.target) reject('review_target_required');
  if (value.state === 'dismissed' && (value.target || Object.keys(patch).length)) reject('dismissed_status_change');
  for (const k of ['latest_final_verified', 'content_reviewed', 'retracted', 'superseded', 'repository_removed', 'access_changed']) if (k in patch && typeof patch[k] !== 'boolean') reject('updates_invalid');
  for (const k of ['publication_date', 'revision_date', 'review_due']) if (k in patch && patch[k] !== null) date(patch[k]);
  for (const k of ['supersedes', 'replaced_topics']) if (k in patch) strings(patch[k]);
  if ('excluded_pages' in patch) { if (!Array.isArray(patch.excluded_pages) || patch.excluded_pages.length > 2000) reject('updates_invalid'); for (const p of patch.excluded_pages) integer(p, 1); }
  if ('correction' in patch && patch.correction !== null) { text(patch.correction, 1, 4000); if (!patch.correction.trim()) reject('updates_invalid'); }
  if ('publication_status' in patch && !['unknown', 'final', 'draft', 'preprint', 'commentary'].includes(String(patch.publication_status))) reject('updates_invalid');
  if (patch.latest_final_verified && (patch.publication_status !== 'final' || patch.retracted || patch.superseded || patch.repository_removed)) reject('updates_invalid');
  const t = value.target; if (!t) return;
  const keys = ['register_id', 'canonical_url', 'pinned_source_id', 'doi', 'pmid', 'pmcid', 'edition', 'original_sha256', 'topic_ids', 'locators']; exact(t, Object.keys(t).filter(k => keys.includes(k)));
  if (!/^[A-Z]\d{2}$/.test(t.register_id)) reject('review_target_required');
  const identities = article(t), inferred = urlArticle(t.canonical_url); if (Object.entries(inferred).some(([k, v]) => identities[k] && identities[k] !== v)) reject('review_identity_conflict');
  if (!t.canonical_url && !t.pinned_source_id && !Object.keys(identities).length) reject('review_target_required');
  if (t.pinned_source_id) text(t.pinned_source_id, 1, 120);
  if (t.edition !== undefined) { text(t.edition, 1, 160); if (!t.edition.trim()) reject('updates_invalid'); hash(t.original_sha256); } else if (t.original_sha256 !== undefined) reject('updates_invalid');
  if (t.topic_ids !== undefined) strings(t.topic_ids); if (t.locators !== undefined) strings(t.locators);
  if ('retracted' in patch && !Object.keys({ ...inferred, ...identities }).length) reject('retraction_identity_required');
  if (Array.isArray(patch.replaced_topics) && patch.replaced_topics.length && t.topic_ids?.some(id => !(patch.replaced_topics as string[]).includes(id))) reject('replacement_scope_mismatch');
}
export function observation(value: Observation) {
  exact(value, ['digest', 'links', 'entries', 'metadata']); hash(value.digest);
  if (!Array.isArray(value.links) || value.links.length > 2000 || !Array.isArray(value.entries) || value.entries.length > 250) reject('updates_invalid');
  for (const l of value.links) { exact(l, ['url', 'label']); https(l.url); text(l.label, 0, 1000); }
  for (const e of value.entries) { exact(e, ['external_id', 'title', 'url', 'publication_date', 'metadata']); text(e.external_id, 1, 1000); text(e.title, 1, 1000); https(e.url); if (e.publication_date !== null) date(e.publication_date); if (!e.metadata || Array.isArray(e.metadata) || typeof e.metadata !== 'object') reject('updates_invalid'); }
  if (!value.metadata || typeof value.metadata !== 'object' || Array.isArray(value.metadata) || JSON.stringify(value).length > 1_000_000) reject('updates_invalid');
}
