import { useEffect, useState } from 'react';
import { api, isCancelled } from '../../platform/api';
import { Button, Input, Select } from '../../ui';
import type { AcquiredVersionPage, ReviewDraft } from './types';

function publicationQuery(sourceId: string, draft: ReviewDraft) {
  const identity = { canonical_url: draft.targetUrl.trim(),
    doi: draft.doi.trim().replace(/^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i, '').toLowerCase(),
    pmid: draft.pmid.trim(), pmcid: draft.pmcid.trim().toUpperCase() };
  if (!Object.values(identity).some(Boolean)) return null;
  if (identity.canonical_url) {
    try {
      const url = new URL(identity.canonical_url);
      if (url.protocol !== 'https:' || !url.hostname || url.username || url.password || url.port && url.port !== '443') return null;
    } catch { return null; }
  }
  if (identity.doi && !/^10\.\d{4,9}\/[^\s"<>]+$/.test(identity.doi) ||
    identity.pmid && !/^[1-9]\d{0,11}$/.test(identity.pmid) ||
    identity.pmcid && !/^PMC[1-9]\d{0,11}$/.test(identity.pmcid)) return null;
  const params = new URLSearchParams({ source_id: sourceId });
  for (const [key, value] of Object.entries(identity)) if (value) params.set(key, value);
  return params.toString();
}

interface Lookup { query: string | null; state: 'loading' | 'ready' | 'failed'; page?: AcquiredVersionPage }

export default function AcquiredVersions({ sourceId, draft, change }: { sourceId: string; draft: ReviewDraft; change: (draft: ReviewDraft) => void }) {
  const query = publicationQuery(sourceId, draft);
  const [lookup, setLookup] = useState<Lookup>({ query: null, state: 'loading' });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!query) return;
    let active = true;
    const controller = new AbortController();
    // Lookup only this publication after typing settles. No Library polling,
    // document bodies or external provider requests belong to this form.
    const timer = setTimeout(() => {
      setLookup({ query, state: 'loading' });
      api<AcquiredVersionPage>('/library/source-versions?' + query, { signal: controller.signal, timeoutMs: 10_000 })
        .then(page => { if (active) setLookup({ query, state: 'ready', page }); })
        .catch(error => { if (active && !isCancelled(error)) setLookup({ query, state: 'failed' }); });
    }, 300);
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [query, retry]);
  const state = lookup.query === query ? lookup.state : 'loading';
  const versions = lookup.query === query && state === 'ready' ? lookup.page?.versions.slice(0, 100) ?? [] : [];
  const selected = versions.find(version => version.edition === draft.edition && version.original_sha256 === draft.originalSha256);
  const bound = !!draft.edition && !!draft.originalSha256;
  return <div className="update-version-picker">
    {!query ? <p className="field-hint">Enter an exact publication URL or article identifier to find acquired versions.</p> :
      state === 'loading' ? <p className="field-hint" role="status">Finding acquired versions in Library…</p> :
        state === 'failed' ? <div className="field-hint" role="status"><p>Acquired versions could not be loaded. Check the publication identity, then retry.</p><Button variant="ghost" onClick={() => setRetry(value => value + 1)}>Retry version lookup</Button></div> :
          versions.length ? <Select label="Acquired version" hint="Choose the Library copy you inspected. Its edition and file fingerprint are recorded together."
            value={selected?.revision_id ?? (bound ? 'recorded' : '')} onChange={event => {
              const version = versions.find(item => item.revision_id === event.target.value);
              if (event.target.value !== 'recorded') change({ ...draft, edition: version?.edition ?? '',
                originalSha256: version?.original_sha256 ?? '', latestFinal: false, contentReviewed: false });
            }}>
            <option value="">Choose a version (optional)</option>
            {bound && !selected && <option value="recorded">Recorded edition: {draft.edition}</option>}
            {versions.map(version => <option key={version.revision_id} value={version.revision_id}>{version.edition} · {version.title} · file {version.original_sha256.slice(0, 8)}</option>)}
          </Select> : <p className="field-hint" role="status">No acquired version is available in Library for this publication. Currency verification waits for an exact acquired version.</p>}
    {query && state === 'ready' && lookup.page?.truncated && <p className="field-hint">Showing up to 100 acquired versions. Narrow the publication identity if the copy you inspected is missing.</p>}
    {bound && <p className="field-hint">Recorded edition: {draft.edition}. {selected ? 'This review is bound to the selected file.' : 'The recorded file binding is retained.'}</p>}
    <p className="field-hint">Retraction, repository removal and loss of access restrict every acquired version of this publication. Clearing a restriction or verifying currency applies only to the exact acquired file.</p>
    <details className="update-version-manual"><summary>Enter version details manually</summary>
      <p className="field-hint">Optional, for a copy reviewed before import. Use its recorded edition and original file hash together.</p>
      <Input label="Acquired edition" value={draft.edition} onChange={event => change({ ...draft, edition: event.target.value, latestFinal: false, contentReviewed: false })} maxLength={160} />
      <Input label="Original SHA256" value={draft.originalSha256} onChange={event => change({ ...draft, originalSha256: event.target.value, latestFinal: false, contentReviewed: false })} maxLength={64} spellCheck={false} autoCapitalize="none" />
    </details>
  </div>;
}
