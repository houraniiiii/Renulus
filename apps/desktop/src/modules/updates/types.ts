export type Filter = 'pending' | 'reviewed' | 'dismissed';
export interface Topic { id: string; title: string }
export interface Evidence { url: string; locator: string; finding: string; checked_on: string; inspected: boolean }
export interface Target { register_id: string; canonical_url?: string; pinned_source_id?: string; doi?: string; pmid?: string; pmcid?: string; edition?: string; original_sha256?: string; topic_ids?: string[]; locators?: string[] }
export interface AcquiredVersion { document_id: string; revision_id: string; title: string; edition: string; original_sha256: string; status: string; canonical_url: string | null; doi: string | null; pmid: string | null; pmcid: string | null }
export interface AcquiredVersionPage { versions: AcquiredVersion[]; limit: number; truncated: boolean }
export interface Changes { publication_status?: string; publication_date?: string; revision_date?: string; review_due?: string; latest_final_verified?: boolean; content_reviewed?: boolean; correction?: string; retracted?: boolean; superseded?: boolean; replaced_topics?: string[]; repository_removed?: boolean; access_changed?: boolean }
export interface Entry {
  id: string; source_id: string; title: string; url: string; kind: string;
  publication_date: string | null; discovered_at: string; reviewed_at: string | null;
  review_state: Filter; summary: string; topic_ids: string[]; read_at: string | null;
  source_metadata: { new_links?: { url: string; label: string }[]; canonical_url?: string; publication_id?: string; reported_publication_status?: string; identifiers?: { doi?: string; pmid?: string; pmcid?: string } };
  review: { id: string; target: Target | null; changes: Changes; evidence: Evidence[]; library_sync_state: string; library_sync_error: string | null } | null;
  library_changes?: { id: string; state: string; error_code: string | null }[];
}
export interface EntryPage { entries: Entry[]; counts: Record<Filter, number>; total: number; offset: number; limit: number; next_offset: number | null }
export interface Source { source_id: string; title: string; url: string; state: string; freshness: string; last_checked_at: string | null; last_success_at: string | null; error_code: string | null; snapshot_status: string }
export interface Publication { id: string; source_id: string; title: string; url: string; state: string; freshness: string; last_checked_at: string | null; last_success_at: string | null; error_code: string | null }
export interface Candidate { url: string; title: string; provenance: string }
export interface LiteratureResult { state: string; discovered: number; max_records_per_topic: number; checks: { state: string; records_checked: number; hit_count?: number; truncated?: boolean }[] }
export function literatureMessage(result: LiteratureResult) {
  const checked = result.checks.reduce((sum, check) => sum + check.records_checked, 0);
  if (result.state === 'failed') return 'The metadata check failed. Earlier successful checks remain dated evidence.';
  const message = result.discovered ? result.discovered + ' publication records are ready to review.' : 'No new records were found within this bounded check.';
  return message + ' Checked ' + checked + ' records.' + (result.state === 'partial' ? ' Some checks failed.' : '') +
    (result.checks.some(check => check.truncated) ? ' Results are limited to ' + result.max_records_per_topic + ' records per topic; more matches exist.' : '');
}
export function today() {
  const now = new Date();
  return now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
}
export const displayDate = (value: string | null | undefined) => value ? new Date(value.length === 10 ? value + 'T12:00:00' : value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : 'Not recorded';

export interface ReviewDraft {
  summary: string; evidenceUrl: string; locator: string; finding: string; inspectedOn: string; inspected: boolean;
  metadata: boolean; targetUrl: string; pinnedSourceId: string; doi: string; pmid: string; pmcid: string;
  edition: string; originalSha256: string;
  publicationStatus: string; publicationDate: string; revisionDate: string; reviewDue: string; latestFinal: boolean; contentReviewed: boolean;
  correction: string; retraction: string; replacement: string; replacementTopics: string[]; accessChanged: string; repositoryRemoved: string;
}
export function reviewDraft(entry: Entry): ReviewDraft {
  const evidence = entry.review?.evidence[0]; const changes = entry.review?.changes; const target = entry.review?.target;
  return { summary: entry.review_state === 'pending' ? '' : entry.summary, evidenceUrl: evidence?.url ?? entry.url,
    locator: evidence?.locator ?? '', finding: evidence?.finding ?? '', inspectedOn: evidence?.checked_on ?? today(), inspected: false,
    metadata: !!target, targetUrl: target?.canonical_url ?? (entry.kind === 'publication-change' || entry.kind === 'research' ? entry.url : ''),
    pinnedSourceId: target?.pinned_source_id ?? '', doi: target?.doi ?? '', pmid: target?.pmid ?? '', pmcid: target?.pmcid ?? '',
    edition: target?.edition ?? '', originalSha256: target?.original_sha256 ?? '',
    publicationStatus: changes?.publication_status ?? '', publicationDate: changes?.publication_date ?? '', revisionDate: changes?.revision_date ?? '',
    reviewDue: changes?.review_due ?? '', latestFinal: changes?.latest_final_verified ?? false, contentReviewed: changes?.content_reviewed ?? false,
    correction: changes?.correction ?? '', retraction: changes?.retracted === undefined ? '' : changes.retracted ? 'yes' : 'no',
    replacement: changes?.replaced_topics?.length ? 'topics' : changes?.superseded === undefined ? '' : changes.superseded ? 'whole' : 'no',
    replacementTopics: changes?.replaced_topics ?? [], accessChanged: changes?.access_changed === undefined ? '' : changes.access_changed ? 'yes' : 'no',
    repositoryRemoved: changes?.repository_removed === undefined ? '' : changes.repository_removed ? 'yes' : 'no' };
}
function publicUrl(value: string) {
  try { const url = new URL(value); return url.protocol === 'https:' && !!url.hostname && !url.username && !url.password && (!url.port || url.port === '443'); }
  catch { return false; }
}
export function reviewProblem(draft: ReviewDraft) {
  if (!draft.summary.trim()) return 'Record the educational implication of your review.';
  if (!publicUrl(draft.evidenceUrl.trim()) || !draft.locator.trim() || !draft.finding.trim() || !draft.inspectedOn) return 'Record the evidence URL, page or section, finding and inspection date.';
  if (draft.inspectedOn > today()) return 'Use the date you inspected the evidence; it cannot be in the future.';
  if (!draft.inspected) return 'Confirm that you inspected the recorded evidence.';
  if (!draft.metadata) return '';
  const edition = draft.edition.trim();
  if (draft.edition && !edition || !!edition !== !!draft.originalSha256) return 'Choose an acquired version, or enter both its edition and original SHA256.';
  if (edition.length > 160 || draft.originalSha256 && !/^[a-f0-9]{64}$/.test(draft.originalSha256)) return 'Use an edition up to 160 characters and a 64-character lowercase SHA256.';
  if (draft.targetUrl.trim() && !publicUrl(draft.targetUrl.trim())) return 'Use the public HTTPS URL for the affected publication.';
  if (!draft.targetUrl.trim() && !draft.pinnedSourceId.trim() && !draft.doi.trim() && !draft.pmid.trim() && !draft.pmcid.trim()) return 'Identify the exact affected publication.';
  const doi = draft.doi.trim().replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, '');
  if (doi && !/^10\.\d{4,9}\/[^\s"<>]+$/.test(doi) || draft.pmid.trim() && !/^\d{1,12}$/.test(draft.pmid.trim()) || draft.pmcid.trim() && !/^PMC\d{1,12}$/i.test(draft.pmcid.trim())) return 'Check the complete original DOI, PMID or PMCID.';
  if (draft.retraction && !doi && !draft.pmid.trim() && !draft.pmcid.trim()) return 'Retraction requires the original article’s exact DOI, PMID or PMCID.';
  if (draft.replacement === 'topics' && !draft.replacementTopics.length) return 'Select the topics or chapters the evidence establishes as replaced.';
  if (draft.latestFinal && (draft.publicationStatus !== 'final' || draft.retraction === 'yes' || draft.replacement === 'whole' || draft.repositoryRemoved === 'yes')) return 'A retracted, replaced or removed publication cannot be verified as latest final.';
  return '';
}
export function reviewPayload(entry: Entry, draft: ReviewDraft, topicIds: string[], state: 'reviewed' | 'dismissed') {
  const base = { summary: draft.summary.trim(), topic_ids: topicIds, reviewer: 'learner', state };
  if (state === 'dismissed') return base;
  const evidence = [{ url: draft.evidenceUrl.trim(), locator: draft.locator.trim(), finding: draft.finding.trim(), checked_on: draft.inspectedOn, inspected: draft.inspected }];
  if (!draft.metadata) return { ...base, evidence };
  const target: Target = { register_id: entry.source_id }; const changes: Changes = {};
  if (draft.targetUrl.trim()) target.canonical_url = draft.targetUrl.trim();
  if (draft.pinnedSourceId.trim()) target.pinned_source_id = draft.pinnedSourceId.trim();
  if (draft.doi.trim()) target.doi = draft.doi.trim();
  if (draft.pmid.trim()) target.pmid = draft.pmid.trim();
  if (draft.pmcid.trim()) target.pmcid = draft.pmcid.trim();
  if (draft.edition.trim()) target.edition = draft.edition.trim();
  if (draft.originalSha256) target.original_sha256 = draft.originalSha256;
  if (draft.publicationStatus) changes.publication_status = draft.publicationStatus;
  if (draft.publicationDate) changes.publication_date = draft.publicationDate;
  if (draft.revisionDate) changes.revision_date = draft.revisionDate;
  if (draft.reviewDue) changes.review_due = draft.reviewDue;
  changes.latest_final_verified = draft.latestFinal;
  changes.content_reviewed = draft.contentReviewed;
  // An unchanged notice stays in the journal. A later exact-copy review is a
  // separate confirmation, rather than publishing the correction again.
  if (draft.correction.trim() && draft.correction.trim() !== entry.review?.changes.correction) changes.correction = draft.correction.trim();
  if (draft.retraction) changes.retracted = draft.retraction === 'yes';
  if (draft.replacement === 'whole') changes.superseded = true;
  if (draft.replacement === 'no') { changes.superseded = false; changes.replaced_topics = []; }
  if (draft.replacement === 'topics') { changes.replaced_topics = draft.replacementTopics; target.topic_ids = draft.replacementTopics; }
  if (draft.accessChanged) changes.access_changed = draft.accessChanged === 'yes';
  if (draft.repositoryRemoved) changes.repository_removed = draft.repositoryRemoved === 'yes';
  return { ...base, evidence, target, changes };
}
