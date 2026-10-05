import { useEffect, useRef, useState } from 'react';
import { api } from '../../platform/api';
import { Button, ErrorState, Select } from '../../ui';

type RouteKind = 'source' | 'publication' | 'literature';
type Action = 'save' | 'check' | 'cancel' | 'reload';
type Selection = { kind: RouteKind; id: string };
type Option = Selection & { source_id: string; title: string; route: string };
type Job = { kind: RouteKind; target_id: string; title: string; available: boolean; state: string;
  next_due_at: string; last_attempt_at: string | null; last_success_at: string | null;
  retry_count: number; failure_count: number; error_code: string | null };
export type Schedule = { enabled: boolean; cadence_hours: number; selection: Selection[]; options: Option[];
  jobs: Job[]; running: boolean; next_due_at: string | null; max_batch: number; max_selection: number; max_retries: number;
  last_run: { id: string; trigger: string; started_at: string; finished_at: string | null; state: string;
    checked: number; failed: number; error_code: string | null } | null };

const key = (item: Selection) => item.kind + ':' + item.id;
const date = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Not yet';
const groups: { kind: RouteKind; label: string }[] = [
  { kind: 'source', label: 'Public source catalogues' },
  { kind: 'publication', label: 'Tracked public publications' },
  { kind: 'literature', label: 'Europe PMC research topics' },
];

export default function AutomaticChecks({ onComplete }: { onComplete: () => void }) {
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [cadence, setCadence] = useState(24);
  const [selection, setSelection] = useState<Selection[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ cause: unknown; action: Action } | null>(null);
  const [message, setMessage] = useState('');
  const completed = useRef(onComplete); completed.current = onComplete;
  const observedRun = useRef<string | null>(null);

  function accept(result: Schedule, reset = false) {
    setSchedule(result);
    if (reset) {
      setEnabled(result.enabled); setCadence(result.cadence_hours); setSelection(result.selection);
      observedRun.current = result.last_run?.finished_at ? result.last_run.id + ':' + result.last_run.finished_at : null;
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    api<Schedule>('/updates/schedule', { signal: controller.signal }).then(result => accept(result, true))
      .catch(cause => { if (!controller.signal.aborted) setError({ cause, action: 'reload' }); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!schedule?.enabled && !schedule?.running) return;
    const controller = new AbortController();
    let inFlight = false;
    const timer = window.setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const result = await api<Schedule>('/updates/schedule', { signal: controller.signal });
        setSchedule(result); setError(previous => previous?.action === 'reload' ? null : previous);
        const run = result.last_run;
        const token = run?.finished_at ? run.id + ':' + run.finished_at : null;
        if (token && token !== observedRun.current) { observedRun.current = token; completed.current(); }
      } catch (cause) {
        if (!controller.signal.aborted) setError(previous => previous && previous.action !== 'reload' ? previous : { cause, action: 'reload' });
      }
      finally { inFlight = false; }
    }, schedule?.running ? 1000 : 15_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [schedule?.enabled, schedule?.running]);

  async function action(kind: Action) {
    setBusy(true); setError(null); setMessage('');
    try {
      const result = await api<Schedule>('/updates/schedule' + (kind === 'check' || kind === 'cancel' ? '/' + kind : ''),
        kind === 'save' ? { method: 'PUT', body: { enabled, cadence_hours: cadence, selection } } :
          kind === 'reload' ? {} : { method: 'POST' });
      accept(result, kind === 'save' || kind === 'reload' && !schedule);
      if (kind === 'save') setMessage(result.enabled ? 'Automatic checks saved. Discoveries will wait for your review.' : 'Automatic checks are off. Your source selection is saved.');
      if (kind === 'cancel') {
        observedRun.current = result.last_run?.finished_at ? result.last_run.id + ':' + result.last_run.finished_at : null;
        setMessage('Checks stopped. Completed observations are retained.'); completed.current();
      }
    } catch (cause) { setError({ cause, action: kind }); } finally { setBusy(false); }
  }
  function toggle(option: Option) {
    setSelection(previous => previous.some(item => key(item) === key(option)) ? previous.filter(item => key(item) !== key(option)) :
      [...previous, { kind: option.kind, id: option.id }]);
  }
  const dirty = !!schedule && (enabled !== schedule.enabled || cadence !== schedule.cadence_hours ||
    selection.length !== schedule.selection.length || selection.some(item => !schedule.selection.some(saved => key(saved) === key(item))));
  const last = schedule?.last_run;
  const failed = last && ['failed', 'partial', 'interrupted', 'cancelled'].includes(last.state);
  const summary = schedule?.running ? 'Checking selected sources…' : schedule?.enabled ? 'On' : 'Off';

  return <details className="updates-automatic">
    <summary>Automatic checks <span>{summary}{failed && !schedule?.running ? ' · ' + last.state : ''}</span></summary>
    <p className="updates-automatic-help">Check selected public sources while Renulus is open. New discoveries wait for your review.</p>
    {error !== null && <ErrorState error={error.cause} title="Source check settings could not be confirmed" onRetry={busy ? undefined : () => void action(error.action)} />}
    {!schedule && error === null && <p role="status">Loading automatic check settings…</p>}
    {schedule && <>
      <div className="updates-automatic-controls">
        <label className="update-checkbox"><input type="checkbox" checked={enabled} disabled={busy || schedule.running} onChange={event => setEnabled(event.target.checked)} />Check my selected sources automatically</label>
        <Select label="Check interval" value={cadence} disabled={busy || schedule.running} onChange={event => setCadence(Number(event.target.value))}>
          <option value={24}>Daily</option><option value={168}>Weekly</option><option value={720}>Every 30 days</option>
          {![24, 168, 720].includes(cadence) && <option value={cadence}>Every {cadence} hours</option>}
        </Select>
      </div>
      <div className="updates-schedule-selection">{groups.map(group => {
        const options = schedule.options.filter(option => option.kind === group.kind);
        if (!options.length) return null;
        return <fieldset key={group.kind}><legend>{group.label}</legend>{options.map(option => {
          const checked = selection.some(item => key(item) === key(option));
          return <label key={key(option)} className="update-checkbox"><input type="checkbox" checked={checked}
            disabled={busy || schedule.running || !checked && selection.length >= schedule.max_selection} onChange={() => toggle(option)} />
            <span>{option.title}<small>{option.source_id} · {option.route}</small></span></label>;
        })}</fieldset>;
      })}</div>
      {schedule.jobs.filter(job => !job.available && selection.some(item => key(item) === job.kind + ':' + job.target_id)).map(job => <div key={job.kind + job.target_id} className="updates-automatic-actions"><p>Unavailable selection: {job.title}.</p><Button variant="ghost" disabled={busy || schedule.running} onClick={() => setSelection(previous => previous.filter(item => key(item) !== job.kind + ':' + job.target_id))}>Remove {job.title}</Button></div>)}
      <p className="updates-automatic-help">{selection.length} of {schedule.max_selection} routes selected. Up to {schedule.max_batch} per batch. Save your selection to apply it.</p>
      <div className="updates-automatic-actions">
        <Button disabled={busy || schedule.running || !dirty || enabled && !selection.length} onClick={() => action('save')}>Save automatic checks</Button>
        <Button variant="secondary" disabled={busy || schedule.running || dirty || !schedule.selection.length} onClick={() => action('check')}>Check selected now</Button>
        {schedule.running && <Button variant="ghost" disabled={busy} onClick={() => action('cancel')}>Stop checks</Button>}
      </div>
      {message && <p className="updates-automatic-message" role="status">{message}</p>}
      <dl className="updates-schedule-times">
        <div><dt>Last run</dt><dd>{last ? date(last.started_at) + ' · ' + last.state + ' · ' + last.checked + ' checked' : 'Not yet'}</dd></div>
        <div><dt>Next due</dt><dd>{schedule.enabled ? date(schedule.next_due_at) : 'Automatic checks off'}</dd></div>
      </dl>
      {failed && <p className="updates-automatic-failure">{last.failed > 0 ? last.failed + ' route checks failed. ' : ''}Previous successful evidence is retained. Check your connection or try Check selected now.</p>}
      {schedule.jobs.length > 0 && <details className="updates-schedule-results"><summary>Check results by source</summary>
        <ul>{schedule.jobs.map(job => <li key={job.kind + job.target_id}><strong>{job.title}</strong><span>{job.state} · Last successful check: {date(job.last_success_at)}</span>
          <span>Next due: {date(job.next_due_at)}{job.retry_count ? ' · Retry ' + job.retry_count + ' of ' + schedule.max_retries : ''}{job.error_code ? ' · ' + job.error_code : ''}</span></li>)}</ul>
      </details>}
    </>}
  </details>;
}
