import { useEffect, useRef, useState } from 'react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Button, ErrorState, LoadingState, Notice } from '../../ui';
import type { ImportResult, LibraryDocument } from './types';

const pendingStates = new Set(['queued', 'processing']);
const labels: Record<string, string> = { queued: 'Queued', processing: 'Processing', ready: 'Available', failed: 'Import failed', cancelled: 'Cancelled' };
const phases: Record<string, string> = { resuming: 'Resuming after a restart', extraction: 'Reading the original', embedding: 'Preparing passage search' };

async function loadStatus(document: LibraryDocument, signal: AbortSignal) {
  const path = '/library/documents/' + encodeURIComponent(document.id);
  const [result, current] = await Promise.all([
    api<ImportResult>(path + '/import-status', { signal }),
    api<LibraryDocument>(path, { signal }),
  ]);
  if (result.document_id !== document.id || current.id !== document.id ||
      result.revision_id !== current.latest_revision || result.revision_id !== document.latest_revision ||
      !result.job?.id || result.job.revision_id !== result.revision_id ||
      !Object.hasOwn(labels, result.job.state) || result.status !== result.job.state ||
      typeof result.job.phase !== 'string' ||
      result.job.error_code !== null && typeof result.job.error_code !== 'string' ||
      result.job.error_message !== null && typeof result.job.error_message !== 'string') {
    throw new ApiError('The import changed while its status was loading. Refresh the document before trying again.', 0, 'import_status_mismatch', true);
  }
  if (current.status !== result.job.state) {
    throw new ApiError('The import is changing state. Checking its latest status again.', 0, 'import_state_changing', true);
  }
  return { result, document: current };
}

/** Inspect the canonical latest job; retry means deliberate replacement input. */
export default function ImportStatus({ document, disabled, onDocument, onLibraryChange, onReimport }: {
  document: LibraryDocument; disabled: boolean;
  onDocument(document: LibraryDocument): void; onLibraryChange(): void; onReimport(document: LibraryDocument): void;
}) {
  const { resource, retry } = useResource(signal => loadStatus(document, signal));
  const [snapshot, setSnapshot] = useState<Awaited<ReturnType<typeof loadStatus>>>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const pending = useRef<AbortController | null>(null);
  const callbacks = useRef({ onDocument, onLibraryChange });
  callbacks.current = { onDocument, onLibraryChange };
  useEffect(() => () => pending.current?.abort(), []);
  useEffect(() => {
    if (resource.status !== 'ready') return;
    setSnapshot(resource.data);
    callbacks.current.onDocument(resource.data.document);
    if (!pendingStates.has(resource.data.result.job.state)) callbacks.current.onLibraryChange();
  }, [resource]);
  useEffect(() => {
    const changing = resource.status === 'error' && resource.error instanceof ApiError && resource.error.code === 'import_state_changing';
    if (!changing && (resource.status !== 'ready' || !pendingStates.has(resource.data.result.job.state))) return;
    const timer = window.setTimeout(retry, changing ? 1000 : 3000);
    return () => window.clearTimeout(timer);
  }, [resource, retry]);

  const status = resource.status === 'ready' ? resource.data : snapshot;
  const job = status?.result.job;
  async function cancel() {
    if (!job || disabled || pending.current || resource.status !== 'ready' || !pendingStates.has(job.state)) return;
    const controller = new AbortController(); pending.current = controller;
    setBusy(true); setError(undefined);
    try {
      await api('/library/jobs/' + encodeURIComponent(job.id) + '/cancel', { method: 'POST', signal: controller.signal });
      // Publication may have won. Read the resulting state rather than assuming cancellation.
      if (!controller.signal.aborted) { retry(); callbacks.current.onLibraryChange(); }
    } catch (caught) { if (!controller.signal.aborted && !isCancelled(caught)) setError(caught); }
    finally { pending.current = null; if (!controller.signal.aborted) setBusy(false); }
  }
  return <section className="library-import-status" aria-label="Document import status">
    <h3>Import status</h3>
    {resource.status === 'loading' && !status ? <LoadingState label="Loading document import status" /> : job && <>
      <p role="status">{resource.status === 'ready' ? labels[job.state] : 'Last reported: ' + labels[job.state]}{phases[job.phase] ? ' · ' + phases[job.phase] : ''}</p>
      {job.state === 'queued' && <p className="muted">This import is waiting for document processing. Its passages are not searchable yet.</p>}
      {job.state === 'processing' && <p className="muted">The original is being processed locally. Passages become searchable after the revision is available.</p>}
      {job.state === 'failed' && <Notice tone="warning"><p>{job.error_message || 'Document processing did not finish. Choose the original again or paste the study note to retry.'}</p>{job.error_code && <p className="muted">Reason: {job.error_code}</p>}</Notice>}
      {(job.state === 'failed' || job.state === 'cancelled') && <><p className="muted">Retry with the original file or study note. The source details and permissions will be retained.</p><Button variant="secondary" disabled={disabled || busy || resource.status !== 'ready'} onClick={() => onReimport(status!.document)}>Retry import</Button></>}
      {pendingStates.has(job.state) && <Button variant="ghost" busy={busy} disabled={disabled || resource.status !== 'ready'} onClick={() => void cancel()}>Cancel this import</Button>}
    </>}
    {resource.status === 'error' && <ErrorState title="Import status could not be loaded" error={resource.error} onRetry={retry} />}
    {error !== undefined && <ErrorState title="The import could not be cancelled" error={error} onRetry={() => void cancel()} />}
  </section>;
}
