import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { api } from '../../platform/api';
import type { ContentReference } from '../../platform/designC';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Panel } from '../../ui';
import { AttemptSession } from './session';
import { practiceLabel } from './types';
import type { Attempt, AttemptSummary, HelpReceipt, Mode, Setup, SetupTiming } from './types';
import AttemptRun from './AttemptRun';
import './attempts.css';

export interface AttemptsPageProps {
  attemptId?: string; versionId?: string;
  mode?: Mode; timing?: SetupTiming;
  onHelp?: (receipt: HelpReceipt) => void | Promise<void>;
  onOpenReference?: (reference: ContentReference, context: HelpReceipt['context']) => void;
  onRetake?: (versionId: string) => void;
}
export default function AttemptsPage(props: AttemptsPageProps) {
  const nav = useNavigation();
  const attemptId = props.attemptId ?? (typeof nav.handoff?.attempt_id === 'string' ? nav.handoff.attempt_id : undefined);
  const versionId = props.versionId ?? (typeof nav.handoff?.version_id === 'string' ? nav.handoff.version_id : undefined);
  const mode = props.mode ?? (nav.handoff?.mode === 'study' || nav.handoff?.mode === 'test' ? nav.handoff.mode : undefined);
  const handoffTiming = nav.handoff?.timing;
  const timing = props.timing ?? (validTiming(handoffTiming) ? handoffTiming : undefined);
  return <AttemptPage key={attemptId ?? versionId ?? String(nav.revision)} {...props} attemptId={attemptId} versionId={versionId} mode={mode} timing={timing} />;
}
function validTiming(value: unknown): value is SetupTiming {
  if (!value || typeof value !== 'object') return false;
  const row = value as Record<string, unknown>;
  return row.kind === 'untimed' ? row.duration_seconds == null : row.kind === 'timed' && typeof row.duration_seconds === 'number'
    && Number.isInteger(row.duration_seconds) && row.duration_seconds >= 1 && row.duration_seconds <= 86400;
}
/** Parent shell may also embed this connected page without a navigation handoff. */
export function AttemptPage({ attemptId, versionId, onRetake, mode, timing, ...consumers }: AttemptsPageProps) {
  const [selected, setSelected] = useState(attemptId);
  const [setupVersion, setSetupVersion] = useState(versionId);
  const [session] = useState(() => new AttemptSession());
  const state = useSyncExternalStore(session.subscribe, session.snapshot);
  const [history, setHistory] = useState<AttemptSummary[]>([]);
  const [historyError, setHistoryError] = useState<unknown>();
  const [active, setActive] = useState<string | null>(null);
  const [historyEpoch, refreshHistory] = useState(0);
  useEffect(() => {
    if (selected) { void session.open(selected); return; }
    let disposed = false;
    api<{ items: AttemptSummary[]; policy: Attempt['policy'] }>('/assessment/test-attempts').then(result => {
      if (!disposed) { setHistory(result.items); setActive(result.policy.active_test_id); setHistoryError(undefined); }
    }).catch(error => { if (!disposed) setHistoryError(error); });
    return () => { disposed = true; };
  }, [selected, session, historyEpoch]);
  useEffect(() => { const timer = setInterval(() => { void session.refresh(); }, 2000); return () => clearInterval(timer); }, [session]);
  useEffect(() => () => session.dispose(), [session]);
  function retake(id: string) { if (onRetake) onRetake(id); else { setSelected(undefined); setSetupVersion(id); } }
  if (state.attempt && selected === state.attempt.id) return <AttemptRun session={session} {...consumers} onRetake={retake} />;
  if (selected) return <div className="attempt-page"><PageHeader title="Your attempt" />{state.error
    ? <ErrorState error={state.error} onRetry={() => { void session.open(selected); }} /> : <LoadingState label="Opening the saved attempt" />}</div>;
  return <div className="attempt-page"><PageHeader title={setupVersion ? 'Set up your attempt' : 'Your attempts'} description="Saved work, separate from the test collection." />
    {active && <Notice tone="warning"><p>An unfinished Test is still active. Its timer and learning restriction continue while you are away.</p>
      <Button onClick={() => setSelected(active)}>Resume active Test</Button></Notice>}
    {setupVersion && !active && <AttemptSetup versionId={setupVersion} initialMode={mode} initialTiming={timing} onStart={attempt => { session.seed(attempt); setSelected(attempt.id); }} />}
    {!!historyError && <ErrorState error={historyError} onRetry={() => refreshHistory(value => value + 1)} />}
    {!setupVersion && !historyError && !history.length && <EmptyState title="Start with a saved test">Choose a version in Tests to set up Study or Test.</EmptyState>}
    {!!history.length && <Panel><h2>Saved attempts</h2><ul className="attempt-history">{history.map(attempt => <li key={attempt.id}>
      <div><strong>{attempt.mode === 'test' ? 'Test' : 'Study'}</strong><span>{attempt.status.replace('_', ' ')} · {new Date(attempt.created_at).toLocaleDateString()}</span></div>
      <Button variant="secondary" disabled={!!active && active !== attempt.id} onClick={() => setSelected(attempt.id)}>{['submitted', 'ended'].includes(attempt.status) ? 'Open results' : 'Resume'}</Button>
    </li>)}</ul></Panel>}
  </div>;
}

function AttemptSetup({ versionId, onStart, initialMode, initialTiming }: { versionId: string; initialMode?: Mode; initialTiming?: SetupTiming; onStart: (attempt: Attempt) => void }) {
  const [setup, setSetup] = useState<Setup>(); const [error, setError] = useState<unknown>();
  const [mode, setMode] = useState<Mode>(initialMode ?? 'study'); const [timed, setTimed] = useState(initialTiming?.kind === 'timed');
  const [divisor] = useState(initialTiming?.kind === 'timed' && initialTiming.duration_seconds % 60 !== 0 ? 1 : 60);
  const [minutes, setMinutes] = useState(initialTiming?.kind === 'timed' ? String(initialTiming.duration_seconds / divisor) : '30');
  const [busy, setBusy] = useState(false); const [reload, setReload] = useState(0);
  const pending = useRef<{ key: string; body: unknown } | null>(null);
  useEffect(() => { let disposed = false; api<Setup>('/assessment/tests/versions/' + encodeURIComponent(versionId) + '/setup')
    .then(value => { if (!disposed) { setSetup(value); setError(undefined); } }).catch(value => { if (!disposed) setError(value); });
    return () => { disposed = true; }; }, [versionId, reload]);
  async function start() {
    if (busy) return;
    setBusy(true); setError(undefined);
    pending.current ??= { key: crypto.randomUUID(), body: { version: { type: 'saved_test_version', id: versionId }, mode,
      timing: timed ? { kind: 'timed', duration_seconds: Number(minutes) * divisor } : { kind: 'untimed' } } };
    try { onStart(await api<Attempt>('/assessment/test-attempts', { method: 'POST', body: pending.current.body, headers: { 'Idempotency-Key': pending.current.key } })); }
    catch (value) { setError(value); } finally { setBusy(false); }
  }
  if (!setup) return error ? <ErrorState error={error} onRetry={() => setReload(value => value + 1)} /> : <LoadingState label="Opening the pinned version setup" />;
  const maximum = 86400 / divisor;
  const validDuration = !timed || (Number.isInteger(Number(minutes)) && Number(minutes) >= 1 && Number(minutes) <= maximum);
  return <Panel className="attempt-setup"><div className="attempt-meta"><Badge>{practiceLabel(setup.version)}</Badge><span>Version {setup.version.ordinal} · {setup.version.item_count} questions</span></div>
    <h2>{setup.test.title}</h2>
    {!setup.can_start && <Notice tone="warning">This version cannot start. Resolve its content warnings or restore the test in Tests.</Notice>}
    <fieldset className="attempt-mode" disabled={busy || !!pending.current}><legend>How would you like to practise?</legend>
      <label><input type="radio" name="attempt-mode" checked={mode === 'study'} onChange={() => setMode('study')} /><span><strong>Study</strong>Submit each answer to reveal feedback. Help is recorded separately.</span></label>
      <label><input type="radio" name="attempt-mode" checked={mode === 'test'} onChange={() => setMode('test')} /><span><strong>Test</strong>Edit your draft freely. Answers and scores appear after final submission; learning help stays restricted until then.</span></label>
    </fieldset>
    <fieldset className="attempt-timing" disabled={busy || !!pending.current}><legend>Timing</legend>
      <label><input type="checkbox" checked={timed} onChange={event => setTimed(event.target.checked)} /> Add a timer</label>
      {timed && <Input label={divisor === 60 ? 'Duration in minutes' : 'Duration in seconds'} type="number" min={1} max={maximum} step={1} value={minutes} onChange={event => setMinutes(event.target.value)} error={!validDuration ? 'Choose a whole number from 1 to ' + maximum + '.' : undefined} />}
      <p className="muted">{!timed ? 'Untimed is the default.' : mode === 'study' ? 'Study can pause. At expiry, keep your pending draft and choose Continue untimed or Finish study.' : 'Test starts on the next action. Closing Renulus does not pause it. At expiry, Renulus submits the answers already saved.'}</p>
    </fieldset>
    {!!error && <ErrorState error={error} title="The attempt has not been acknowledged" />}
    <Button busy={busy} disabled={!setup.can_start || !validDuration} onClick={() => { void start(); }}>{pending.current ? 'Retry start' : 'Start ' + (mode === 'test' ? 'Test' : 'Study')}</Button>
  </Panel>;
}
