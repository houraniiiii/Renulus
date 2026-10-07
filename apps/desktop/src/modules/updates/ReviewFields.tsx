import { Input, Select, Textarea } from '../../ui';
import AcquiredVersions from './AcquiredVersions';
import type { ReviewDraft, Topic } from './types';
import { today } from './types';

export default function ReviewFields({ sourceId, draft, topics, change }: { sourceId: string; draft: ReviewDraft; topics: Topic[]; change: (draft: ReviewDraft) => void }) {
  const update = <K extends keyof ReviewDraft>(key: K, value: ReviewDraft[K]) => change({ ...draft, [key]: value });
  const identify = (key: 'targetUrl' | 'pinnedSourceId' | 'doi' | 'pmid' | 'pmcid', value: string) => change({ ...draft, [key]: value,
    edition: '', originalSha256: '', latestFinal: false, contentReviewed: false });
  return <div className="update-review-fields">
    <Textarea label="What changes for your learning?" hint="Keep the educational implication after inspecting the source." rows={4} value={draft.summary} onChange={event => update('summary', event.target.value)} maxLength={8000} />
    <fieldset className="update-evidence"><legend>Evidence you inspected</legend>
      <Input label="Evidence URL" type="url" value={draft.evidenceUrl} onChange={event => update('evidenceUrl', event.target.value)} maxLength={2000} />
      <Input label="Page or section" placeholder="For example: corrigendum, recommendation 2" value={draft.locator} onChange={event => update('locator', event.target.value)} maxLength={1000} />
      <Textarea label="What did the source establish?" rows={2} value={draft.finding} onChange={event => update('finding', event.target.value)} maxLength={4000} />
      <Input label="Date inspected" type="date" value={draft.inspectedOn} max={today()} onChange={event => update('inspectedOn', event.target.value)} />
      <label className="update-checkbox"><input type="checkbox" checked={draft.inspected} onChange={event => update('inspected', event.target.checked)} />I inspected this evidence and its stated publication status.</label>
    </fieldset>
    <details className="update-metadata"><summary>Publication status and affected source</summary>
      <label className="update-checkbox"><input type="checkbox" checked={draft.metadata} onChange={event => update('metadata', event.target.checked)} />Record the source facts established by this evidence</label>
      {draft.metadata && <div className="update-metadata-fields">
        <p className="field-hint">Source family {sourceId}. Identify the original publication; a family alone cannot identify a Library version.</p>
        <Input label="Affected publication URL" hint="For a notice, identify the original publication it changes." type="url" value={draft.targetUrl} onChange={event => identify('targetUrl', event.target.value)} maxLength={2000} />
        <Input label="Pinned source ID (if known)" value={draft.pinnedSourceId} onChange={event => identify('pinnedSourceId', event.target.value)} maxLength={120} />
        <Select label="Publication status" value={draft.publicationStatus} onChange={event => change({ ...draft, publicationStatus: event.target.value, latestFinal: event.target.value === 'final' && draft.latestFinal })}><option value="">Not established by this review</option><option value="final">Published final</option><option value="draft">Public-review draft</option><option value="preprint">Preprint</option><option value="commentary">Commentary</option><option value="unknown">Unknown</option></Select>
        <div className="update-date-fields"><Input label="Publication date" type="date" value={draft.publicationDate} onChange={event => update('publicationDate', event.target.value)} /><Input label="Revision date" type="date" value={draft.revisionDate} onChange={event => update('revisionDate', event.target.value)} /></div>
        {draft.publicationStatus === 'final' && <label className="update-checkbox"><input type="checkbox" checked={draft.latestFinal} onChange={event => update('latestFinal', event.target.checked)} />Verified latest final for this scope</label>}
        <label className="update-checkbox"><input type="checkbox" checked={draft.contentReviewed} onChange={event => update('contentReviewed', event.target.checked)} />Content reviewed for the recorded educational scope</label>
        <Input label="Review due (if established)" type="date" value={draft.reviewDue} onChange={event => update('reviewDue', event.target.value)} />
        <Input label="Correction reference" value={draft.correction} onChange={event => update('correction', event.target.value)} maxLength={4000} />
        <Select label="Retraction" value={draft.retraction} onChange={event => update('retraction', event.target.value)}><option value="">Not established by this review</option><option value="yes">Original article retracted</option><option value="no">Retraction cleared by a notice</option></Select>
        {draft.retraction && <p className="field-hint">Confirm the original article's DOI, PMID or PMCID below. The notice has its own identity.</p>}
        <div className="update-article-ids"><Input label="Original DOI" value={draft.doi} onChange={event => identify('doi', event.target.value)} maxLength={500} /><Input label="Original PMID" value={draft.pmid} onChange={event => identify('pmid', event.target.value)} maxLength={12} /><Input label="Original PMCID" value={draft.pmcid} onChange={event => identify('pmcid', event.target.value)} maxLength={15} /></div>
        <AcquiredVersions sourceId={sourceId} draft={draft} change={change} />
        <Select label="Replacement scope" value={draft.replacement} onChange={event => update('replacement', event.target.value)}><option value="">Not established by this review</option><option value="whole">Whole publication replaced</option><option value="topics">Selected topics or chapters replaced</option><option value="no">Replacement cleared by reviewed evidence</option></Select>
        {draft.replacement === 'topics' && <fieldset className="update-topic-list"><legend>Replaced topics</legend>{topics.map(topic => <label key={topic.id}><input type="checkbox" checked={draft.replacementTopics.includes(topic.id)} onChange={event => update('replacementTopics', event.target.checked ? [...draft.replacementTopics, topic.id] : draft.replacementTopics.filter(id => id !== topic.id))} />{topic.title}</label>)}</fieldset>}
        <div className="update-date-fields"><Select label="Access" value={draft.accessChanged} onChange={event => update('accessChanged', event.target.value)}><option value="">Not established</option><option value="yes">Access changed</option><option value="no">Access rechecked</option></Select><Select label="Repository availability" value={draft.repositoryRemoved} onChange={event => update('repositoryRemoved', event.target.value)}><option value="">Not established</option><option value="yes">Repository record removed</option><option value="no">Repository record restored</option></Select></div>
      </div>}
    </details>
  </div>;
}
