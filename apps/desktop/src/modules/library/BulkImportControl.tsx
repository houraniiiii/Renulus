import { useEffect, useRef, useState } from 'react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { Button, ErrorState, Notice } from '../../ui';

interface Batch {
  attempted: number; accepted: number; newly_queued: number; rejected: number;
  rejections: Record<string, number>; remaining: number; next_cursor: string | null;
  done: boolean; cancelled: boolean;
}
interface Progress { checked: number; added: number; rejected: number; remaining: number | null; batches: number; rejections: Record<string, number> }
const emptyProgress = (): Progress => ({ checked: 0, added: 0, rejected: 0, remaining: null, batches: 0, rejections: Object.create(null) as Record<string, number> });
const number = (value: number) => value.toLocaleString('en-GB');
const rejectionNames: Record<string, string> = {
  article_permission_required: 'Processing permission needs review', article_exclusion_required: 'Material exclusions need review',
  article_status_unavailable: 'A source restriction prevents adoption', article_receipt_missing: 'The acquired file receipt needs refreshing',
  catalogue_receipt_changed: 'The file receipt changed', article_metadata_conflict: 'Matching metadata needs review',
};
function readBatch(value: unknown): Batch {
  if (!value || typeof value !== 'object') throw new ApiError('The article batch returned an incomplete result. Refresh the catalogue and try again.', 0, 'invalid_bulk_result');
  const result = value as Batch;
  const finiteCount = (count: unknown) => typeof count === 'number' && Number.isSafeInteger(count) && count >= 0;
  if (![result.attempted, result.accepted, result.newly_queued, result.rejected, result.remaining].every(finiteCount) ||
      result.attempted > 250 || result.accepted > result.attempted || result.newly_queued > result.accepted || result.rejected > result.attempted ||
      typeof result.done !== 'boolean' || typeof result.cancelled !== 'boolean' ||
      result.next_cursor !== null && (typeof result.next_cursor !== 'string' || !result.next_cursor || result.next_cursor.length > 1000) ||
      result.done !== (result.remaining === 0) || result.done !== (result.next_cursor === null) ||
      !result.rejections || typeof result.rejections !== 'object' || Array.isArray(result.rejections) ||
      Object.entries(result.rejections).some(([code, count]) => !/^[a-z0-9_]{1,100}$/.test(code) || !finiteCount(count)) ||
      Object.values(result.rejections).reduce((sum, count) => sum + count, 0) !== result.rejected) {
    throw new ApiError('The article batch returned an incomplete result. Refresh the catalogue and try again.', 0, 'invalid_bulk_result');
  }
  return result;
}

/** Explicit catalogue adoption; ordinary durable jobs own CPU conversion. */
export default function BulkImportControl({ query, disabled, onBusyChange, onBatch }: {
  query: string; disabled: boolean; onBusyChange(busy: boolean): void; onBatch(): void;
}) {
  const [state, setState] = useState<'idle' | 'running' | 'paused' | 'complete' | 'error'>('idle');
  const [progress, setProgress] = useState<Progress>(emptyProgress);
  const [error, setError] = useState<unknown>();
  const pending = useRef<AbortController | null>(null);
  const cursor = useRef<string | null>(null);
  const reported = useRef<Progress>(emptyProgress());
  const mounted = useRef(true);
  const callbacks = useRef({ onBusyChange, onBatch }); callbacks.current = { onBusyChange, onBatch };
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current?.abort(); callbacks.current.onBusyChange(false); };
  }, []);
  async function run() {
    if (disabled || pending.current) return;
    if (state === 'complete') { cursor.current = null; reported.current = emptyProgress(); setProgress(reported.current); }
    const controller = new AbortController(); pending.current = controller;
    setState('running'); setError(undefined); callbacks.current.onBusyChange(true);
    try {
      while (!controller.signal.aborted) {
        const previous = cursor.current;
        const value = await api<unknown>('/library/collection/import-next', {
          method: 'POST', body: { source_id: 'L02', query, limit: 100, cursor: previous, scope: { kind: 'personal-library' } },
          signal: controller.signal, timeoutMs: 120_000,
        });
        if (controller.signal.aborted || !mounted.current) return;
        const batch = readBatch(value);
        if (!batch.done && !batch.cancelled && (batch.attempted === 0 || previous === batch.next_cursor)) {
          throw new ApiError('Article checks made no further progress. Refresh the catalogue and retry.', 0, 'bulk_no_progress', true);
        }
        cursor.current = batch.next_cursor;
        const rejections = Object.assign(Object.create(null) as Record<string, number>, reported.current.rejections);
        for (const [code, count] of Object.entries(batch.rejections)) rejections[code] = (rejections[code] ?? 0) + count;
        reported.current = { checked: reported.current.checked + batch.attempted,
          added: reported.current.added + batch.newly_queued, rejected: reported.current.rejected + batch.rejected,
          remaining: batch.remaining, batches: reported.current.batches + 1, rejections };
        setProgress(reported.current); callbacks.current.onBatch();
        if (batch.done || batch.cancelled) { setState(batch.done ? 'complete' : 'paused'); return; }
      }
    } catch (caught) {
      if (mounted.current && !controller.signal.aborted && !isCancelled(caught)) { setError(caught); setState('error'); }
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        if (mounted.current) { callbacks.current.onBusyChange(false); if (controller.signal.aborted) setState('paused'); }
      }
    }
  }
  function pause() { pending.current?.abort(); }
  return <section className="section" aria-label="Add collected PMC articles">
    <details open={state !== 'idle'}>
      <summary>Check remaining PMC articles</summary>
      <p>Check eligible articles and candidates matching the source and title filter. Each version is inspected for licence, file integrity and source restrictions before it is saved.</p>
      <p className="muted">Already added articles are reused. Closing this view stops new checks; accepted imports continue processing in your library.</p>
      <div className="actions">
        <Button variant="secondary" busy={state === 'running'} disabled={disabled || state === 'running'} onClick={() => void run()}>{state === 'complete' ? 'Start another article scan' : state === 'paused' ? 'Resume article checks' : state === 'error' ? 'Retry article checks' : 'Check and queue matching articles'}</Button>
        {state === 'running' && <Button variant="ghost" onClick={pause}>Pause article checks</Button>}
      </div>
      {progress.batches > 0 && <p role="status">Reported batches: {number(progress.checked)} articles checked · {number(progress.added)} added for processing · {number(progress.rejected)} need attention{progress.remaining !== null ? ' · ' + number(progress.remaining) + ' remaining' : ''}.</p>}
      {state === 'paused' && <Notice><p>Article checks paused. Already queued imports continue processing. The last batch may have committed before the pause; refresh your library to see its current totals.</p></Notice>}
      {state === 'complete' && <Notice><p>All matching pending articles in this scan were checked. Added articles appear in passage search after processing completes.</p></Notice>}
      {error !== undefined && <ErrorState title="Article checks stopped" error={error} onRetry={disabled ? undefined : () => void run()} />}
      {Object.keys(progress.rejections).length > 0 && <details><summary>Articles needing attention</summary><ul>{Object.entries(progress.rejections).map(([code, count]) => <li key={code}>{number(count)} · {Object.hasOwn(rejectionNames, code) ? rejectionNames[code] : 'Inspection needs review (' + code + ')'}</li>)}</ul><p className="muted">These entries remain in Collected sources. No permission or currentness is inferred from an acquisition receipt.</p></details>}
    </details>
  </section>;
}
