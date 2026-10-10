import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Badge, Button, ErrorState, Input, LoadingState, Notice } from '../../ui';
import { readNightly, readPreferences, savePreferences } from './api';
import type { NightlyCount, NightlyPreferencesUpdate, NightlyPreferencesValue } from './types';
import './nightly.css';

export interface NightlyPreferencesProps {
  assistanceAllowed?: boolean;
  onSaved?: (preferences: NightlyPreferencesValue) => void;
}

/** Settings mounts this; enabling/saving never invokes generation from the renderer. */
export function NightlyPreferences({ assistanceAllowed, onSaved }: NightlyPreferencesProps) {
  const { resource, retry } = useResource(readNightly);
  if (resource.status === 'loading') return <LoadingState label="Loading nightly preferences" />;
  if (resource.status === 'error') return <ErrorState title="Nightly preferences could not be loaded" error={resource.error} onRetry={retry} />;
  return <PreferencesForm initial={resource.data.preferences}
    assistanceAllowed={assistanceAllowed ?? resource.data.assistance_allowed} onSaved={onSaved} />;
}

// Off/On leads this quiet reading surface. Source Sans 3, paper/teal and the
// existing controls keep it part of Renulus; time/count form one compact group.
function PreferencesForm({ initial, assistanceAllowed, onSaved }: NightlyPreferencesProps & { initial: NightlyPreferencesValue }) {
  const [current, setCurrent] = useState(initial);
  const [localTime, setLocalTime] = useState(initial.local_time);
  const [count, setCount] = useState<NightlyCount>(initial.question_count);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [failure, setFailure] = useState(false);
  const [timeError, setTimeError] = useState('');
  const pending = useRef<{ body: NightlyPreferencesUpdate; key: string } | null>(null);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);

  async function save(enabled: boolean, preserveDraft = false) {
    if (locked.current) return;
    const time = preserveDraft ? current.local_time : localTime;
    if (!/^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(time)) { setTimeError('Choose a local time in HH:mm format.'); return; }
    const body = { enabled, local_time: time, question_count: preserveDraft ? current.question_count : count, expected_revision: current.revision };
    const command = pending.current && JSON.stringify(pending.current.body) === JSON.stringify(body)
      ? pending.current : { body, key: crypto.randomUUID() };
    pending.current = command; locked.current = true; setBusy(true); setMessage(''); setTimeError(''); setFailure(false);
    const abort = new AbortController(); controller.current = abort;
    try {
      const saved = await savePreferences(command.body, command.key, abort.signal);
      if (abort.signal.aborted) return;
      setCurrent(saved); pending.current = null;
      if (!preserveDraft) { setLocalTime(saved.local_time); setCount(saved.question_count); }
      setMessage(saved.enabled ? 'Nightly preferences saved.' : 'Nightly preferences saved. Generation is off.');
      onSaved?.(saved);
    } catch (error) {
      if (abort.signal.aborted || isCancelled(error)) return;
      setFailure(true);
      setMessage(error instanceof ApiError ? error.message : 'Your preferences could not be saved. Keep your changes and retry.');
      if (error instanceof ApiError && error.code === 'revision_conflict') {
        // Keep the unsaved time/count while obtaining the current canonical revision.
        const latest = await readPreferences(abort.signal).catch(() => undefined);
        if (latest && !abort.signal.aborted) { setCurrent(latest); pending.current = null; }
      }
    } finally {
      locked.current = false;
      if (!abort.signal.aborted) setBusy(false);
    }
  }
  function submit(event: FormEvent) { event.preventDefault(); void save(current.enabled); }
  return <form className="nightly-preferences" onSubmit={submit} aria-label="Nightly preferences">
    <div className="nightly-preferences-panel">
      <header className="nightly-heading">
        <h2>Nightly generation</h2>
        <div className="nightly-heading-actions"><Badge tone={current.enabled ? 'default' : 'neutral'}>{current.enabled ? 'On' : 'Off'}</Badge>
          <Button variant="secondary" busy={busy} disabled={!current.enabled && !assistanceAllowed}
            onClick={() => void save(!current.enabled, current.enabled)}>{current.enabled ? 'Turn off' : 'Turn on'}</Button>
        </div>
      </header>
      <div className="nightly-fields">
        <Input label="Preferred time" type="time" step={60} value={localTime} error={timeError} hint="Local time"
          disabled={busy} onChange={event => { setLocalTime(event.target.value); setTimeError(''); setMessage(''); }} />
        <fieldset className="nightly-counts" disabled={busy}><legend>Questions</legend>
          <div>{([5, 10, 20] as const).map(value => <Button key={value} variant="secondary"
            aria-label={value + ' questions'} aria-pressed={count === value} onClick={() => { setCount(value); setMessage(''); }}>{value}</Button>)}</div>
        </fieldset>
      </div>
      <p className="nightly-detail">One test per eligible night · {count} questions</p>
    </div>
    <Notice>Renulus must be running at your preferred time. After sleep, it can catch up once. Reopening or restoring waits for the next eligible time.</Notice>
    {!assistanceAllowed && <p className="nightly-detail">Nightly generation is paused during your Test. You can still turn it off.</p>}
    <div><Button type="submit" busy={busy} disabled={current.enabled && !assistanceAllowed}>Save preferences</Button></div>
    {message && <p className={failure ? 'field-error' : 'nightly-detail'} role={failure ? 'alert' : 'status'}>{message}</p>}
  </form>;
}
