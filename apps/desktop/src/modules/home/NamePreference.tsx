import { useEffect, useState, type FormEvent } from 'react';
import { Button, Input } from '../../ui';
import { ApiError, isCancelled } from '../../platform/api';
import { readName, saveName } from './requests';
import type { HomePreferences } from './types';

/** Mounted by Settings; the name is chosen here, never inferred from the OS. */
export function NamePreference() {
  const [preferences, setPreferences] = useState<HomePreferences>();
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [request, setRequest] = useState<{ text: string; revision: number; key: string }>();
  useEffect(() => {
    const controller = new AbortController();
    void readName(controller.signal).then(value => { setPreferences(value); setName(value.doctor_name ?? ''); })
      .catch(error => { if (!isCancelled(error)) setMessage('Your name preference could not be loaded. Reopen Settings to try again.'); });
    return () => controller.abort();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!preferences || busy) return;
    const command = request?.text === name && request.revision === preferences.revision ? request :
      { text: name, revision: preferences.revision, key: crypto.randomUUID() };
    setRequest(command); setBusy(true); setMessage('');
    try {
      const saved = await saveName(name.trim() || null, command.revision, command.key);
      setPreferences(saved); setName(saved.doctor_name ?? ''); setRequest(undefined); setMessage('Your greeting name is saved.');
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Your name could not be saved. Try again.');
      if (error instanceof ApiError && error.code === 'revision_conflict') {
        const current = await readName().catch(() => undefined);
        if (current) { setPreferences(current); setRequest(undefined); }
      }
    } finally { setBusy(false); }
  }
  return <form className="section" onSubmit={submit} aria-label="Greeting name">
    <Input label="Name for your greeting" value={name} maxLength={80} autoComplete="off"
      hint="Optional. Leave blank for a generic welcome." disabled={!preferences || busy}
      onChange={event => { setName(event.target.value); setMessage(''); }} />
    <div><Button type="submit" busy={busy} disabled={!preferences}>Save name</Button></div>
    {message && <p role="status">{message}</p>}
  </form>;
}
