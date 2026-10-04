import { api, apiPath, ApiError } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { ErrorState, LoadingState, Notice } from '../../ui';
import OriginalViewer from './OriginalViewer';
import type { Citation, LibraryDocument } from './types';

export interface SourceLocation { revisionId: string | null; page: number | null }
export function isPhysicalPage(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

async function loadCitation(documentId: string, location: SourceLocation, signal: AbortSignal) {
  if (!location.revisionId) return { citation: null, pageMissing: false };
  const path = '/library/revisions/' + encodeURIComponent(location.revisionId);
  function validate(value: Citation, requestedPage: number | null) {
    if (value.document_id !== documentId || value.document_revision !== location.revisionId ||
        !Array.isArray(value.locators) || value.page !== null && !isPhysicalPage(value.page) ||
        requestedPage !== null && (value.page !== requestedPage || !value.locators.some(locator => locator.page === requestedPage)) ||
        apiPath(value.original_url) !== apiPath(path + '/original')) {
      throw new ApiError('The citation does not match this source revision and page. Try again.', 0, 'invalid_citation', true);
    }
    return value;
  }
  try {
    const citation = validate(await api<Citation>(path + '/citation' + (location.page !== null ? '?page=' + location.page : ''), { signal }), location.page);
    return { citation, pageMissing: false };
  } catch (error) {
    // A missing extracted page does not make a different revision authoritative.
    // Only this known page error permits opening the same revision as a whole.
    if (!(error instanceof ApiError) || error.status !== 404 || error.code !== 'page_missing' || location.page === null) throw error;
    const citation = validate(await api<Citation>(path + '/citation', { signal }), null);
    return { citation: { ...citation, page: null }, pageMissing: true };
  }
}

export default function SourceInspector({ document, location }: { document: LibraryDocument; location: SourceLocation }) {
  const { resource, retry } = useResource(signal => loadCitation(document.id, location, signal));
  const revision = document.revisions.find(value => value.id === location.revisionId);
  const result = resource.status === 'ready' ? resource.data : null;
  return <>
    {revision && <dl>
      <div><dt>Edition and publication</dt><dd>{revision.metadata.edition ?? 'Edition unverified'}{revision.metadata.publication_date ? ' · ' + revision.metadata.publication_date : ''}</dd></div>
      <div><dt>Source currentness</dt><dd>{revision.metadata.latest_final_verified && revision.metadata.content_reviewed ? 'Latest final verified and content reviewed' : 'Not verified as current guidance'}</dd></div>
      <div><dt>Original terms</dt><dd>{revision.rights.licence}</dd></div>
      <div><dt>Extracted passages</dt><dd>{revision.passage_count}</dd></div>
    </dl>}
    {!location.revisionId ? <p className="muted">No indexed revision is available to open yet.</p> :
      resource.status === 'loading' ? <LoadingState label="Loading cited source location" /> :
        resource.status === 'error' ? <ErrorState title="The cited source could not be opened" error={resource.error} onRetry={retry} /> :
          result?.citation && <>
            {result.pageMissing ? <Notice tone="warning"><p>Cited page {location.page} is unavailable. You can still open this original without a page jump.</p></Notice> :
              result.citation.page === null ? <p className="muted">Physical page is unknown. The original opens without a page jump.</p> :
                <p className="muted">Physical page {result.citation.page} · counted from the start of the original, not its printed page label.</p>}
            <OriginalViewer key={result.citation.document_revision + ':' + result.citation.page} citation={result.citation} wholeOriginal={result.pageMissing} />
            <p className="muted">{result.citation.locators.length} extracted source location{result.citation.locators.length === 1 ? '' : 's'} {result.citation.page === null ? 'in this revision' : 'on this page'}. Exact passage highlighting is unavailable.</p>
          </>}
  </>;
}
