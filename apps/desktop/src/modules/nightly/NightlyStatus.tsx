import { useEffect, useRef, useState } from 'react';
import { ApiError, isCancelled } from '../../platform/api';
import { Badge, Button, ErrorState, LoadingState } from '../../ui';
import type { TestSelection } from '../tests/types';
import { cancelNightly } from './api';
import { isActive, nightlyMessage, type NightlyJob } from './types';
import { useNightlyStatus } from './useNightlyStatus';
import './nightly.css';

export interface NightlyStatusProps {
  onPreferences?: () => void;
  onOpenTest?: (selection: TestSelection) => void;
  onReviewJob?: (id: string) => void;
}
const labels = { queued: 'Generating', running: 'Generating', published: 'Ready', needs_review: 'Needs review', failed: 'Failed', cancelled: 'Stopped' } as const;

/** Tests opens the same saved version; progress never renders generated keys. */
export function NightlyStatus({ onPreferences, onOpenTest, onReviewJob }: NightlyStatusProps) {
  const { data, error, refresh } = useNightlyStatus();
  const [busy, setBusy] = useState(false), [cancelError, setCancelError] = useState('');
  const locked = useRef(false);
  const command = useRef<{ id: string; key: string } | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  async function stop(job: NightlyJob) {
    if (locked.current) return;
    locked.current = true; setBusy(true); setCancelError('');
    const receipt = command.current?.id === job.id ? command.current : { id: job.id, key: crypto.randomUUID() };
    command.current = receipt;
    const abort = new AbortController(); controller.current = abort;
    try {
      await cancelNightly(receipt.id, receipt.key, abort.signal);
      if (!abort.signal.aborted) { command.current = null; refresh(); }
    } catch (failure) {
      if (!abort.signal.aborted && !isCancelled(failure)) setCancelError(failure instanceof ApiError ? failure.message : 'Generation could not be stopped. Try again.');
    } finally { locked.current = false; if (!abort.signal.aborted) setBusy(false); }
  }
  if (!data) return error ? <ErrorState title="Nightly status could not be loaded" error={error} onRetry={refresh} /> : <LoadingState label="Loading nightly status" />;
  const job = data.last_job;
  const result = job?.result;
  const blocked = !data.assistance_allowed;
  return <section className="nightly-status" aria-label="Nightly practice">
    <header className="nightly-heading"><h2>Nightly practice</h2>
      <div className="nightly-heading-actions"><Badge tone={data.preferences.enabled ? 'default' : 'neutral'}>{data.preferences.enabled ? 'On' : 'Off'}</Badge>
        {onPreferences && <Button variant="ghost" onClick={onPreferences}>Preferences</Button>}</div>
    </header>
    {!job && <p>{data.preferences.enabled ? 'A saved test will appear here after an eligible night.' : 'Turn on nightly generation in Settings to create a saved test from eligible learning.'}</p>}
    {job && <div className="nightly-job">
      <div className="nightly-job-summary"><Badge tone={job.state === 'failed' ? 'error' : job.state === 'needs_review' ? 'warning' : 'default'}>{labels[job.state]}</Badge>
        <p>{job.state === 'published' ? job.validated_count + ' questions' : job.validated_count + ' of ' + job.requested_count + ' questions validated'}</p>
      </div>
      {isActive(job) && <Button variant="secondary" busy={busy} onClick={() => void stop(job)}>Stop generation</Button>}
      {job.state === 'published' && result?.available && result.test && onOpenTest &&
        <Button disabled={blocked} onClick={() => onOpenTest({ test_id: result.test!.id, version_id: result.version.id })}>Open saved test</Button>}
      {job.state === 'published' && !result?.available && <p>This saved test is unavailable.</p>}
      {(job.state === 'failed' || job.state === 'needs_review') && <p>{nightlyMessage(job.error_code)}</p>}
      {(job.state === 'failed' || job.state === 'needs_review') && onReviewJob &&
        <Button variant="secondary" disabled={blocked} onClick={() => onReviewJob(job.id)}>Review retained work</Button>}
    </div>}
    {data.error_code && <p role="status">{nightlyMessage(data.error_code)}</p>}
    {blocked && <p className="nightly-detail">Nightly generation is paused during your Test. Stop remains available.</p>}
    {data.preferences.enabled && data.next_eligible_at && <p className="nightly-detail">Next eligible time: <time dateTime={data.next_eligible_at}>{new Date(data.next_eligible_at).toLocaleString()}</time>. Renulus must be running.</p>}
    {error != null && <p className="field-error" role="alert">Status could not be refreshed. <Button variant="ghost" onClick={refresh}>Refresh status</Button></p>}
    {cancelError && <p className="field-error" role="alert">{cancelError}</p>}
  </section>;
}
