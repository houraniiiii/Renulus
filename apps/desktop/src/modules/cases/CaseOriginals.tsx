// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState } from 'react';
import { FileText } from 'lucide-react';
import { apiResponse, ApiError, isCancelled } from '../../platform/api';
import { Badge, Button, ErrorState } from '../../ui';
import type { CaseAttachment, CaseSession } from './types';

function CaseOriginal({ caseId, attachment, disabled, remove }: {
  caseId: string; attachment: CaseAttachment; disabled: boolean;
  remove: (id: string) => Promise<CaseSession | null | undefined> | undefined;
}) {
  const [original, setOriginal] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [cancelled, setCancelled] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const request = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);

  function release() {
    request.current?.abort(); request.current = null;
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = null;
  }
  useEffect(() => () => release(), []);

  function close() {
    release(); setOriginal(undefined); setBusy(false); setError(undefined);
    setCancelled(busy); setImageFailed(false);
  }
  async function open() {
    if (request.current || original || !attachment.original_available) return;
    const pending = new AbortController(); request.current = pending;
    setBusy(true); setError(undefined); setCancelled(false);
    try {
      const response = await apiResponse('/cases/sessions/' + encodeURIComponent(caseId) + '/attachments/' +
        encodeURIComponent(attachment.id) + '/original', { signal: pending.signal, headers: { Accept: attachment.media_type } });
      const blob = await response.blob();
      if (pending.signal.aborted) return;
      if (!['application/pdf', 'image/png', 'image/jpeg'].includes(blob.type) || blob.type !== attachment.media_type ||
          !blob.size || blob.size !== attachment.bytes) {
        throw new ApiError('The original does not match this case file. Close and reopen the case to refresh it.', 0, 'case_original_mismatch');
      }
      objectUrl.current = URL.createObjectURL(blob);
      setOriginal(objectUrl.current);
    } catch (failure) {
      if (request.current === pending && !isCancelled(failure)) setError(failure);
    } finally {
      if (request.current === pending) { request.current = null; setBusy(false); }
    }
  }

  return <li className="case-original" aria-label={attachment.filename}>
    <div className="case-context-meta"><strong>{attachment.title || attachment.filename}</strong>
      <Badge tone={attachment.saved ? 'default' : 'warning'}>{attachment.saved ? 'Saved' : 'Temporary'}</Badge></div>
    <p className="muted">{attachment.filename} · {attachment.media_type === 'application/pdf' ? 'PDF' : attachment.media_type === 'image/png' ? 'PNG' : 'JPEG'} · {attachment.bytes.toLocaleString('en-GB')} bytes</p>
    {!attachment.original_available && <p className="muted">The original is unavailable. Restore a full backup that includes originals.</p>}
    <div className="actions"><Button variant="secondary" busy={busy} disabled={disabled || !!original || !attachment.original_available} onClick={() => void open()}>View original</Button>
      {(busy || original) && <Button variant="ghost" onClick={close}>{busy ? 'Cancel loading' : 'Close original'}</Button>}
      <Button variant="ghost" disabled={disabled || busy} onClick={() => { close(); void remove(attachment.id); }}>Remove</Button></div>
    {busy && <p className="muted" role="status">Loading original…</p>}
    {cancelled && <p className="muted" role="status">Original loading cancelled.</p>}
    {!!error && <ErrorState title="The original could not be loaded" error={error} onRetry={disabled ? undefined : () => void open()} />}
    {original && (attachment.media_type === 'application/pdf' ?
      <iframe className="case-original-pdf" title={'Original ' + attachment.filename} src={original} /> :
      imageFailed ? <p className="field-error" role="alert">The image preview could not be displayed. Close and reopen the original to try again.</p> :
        <img className="case-original-image" src={original} alt={'Original ' + attachment.filename} onError={() => setImageFailed(true)} />)}
  </li>;
}

export function CaseOriginals({ session, disabled, remove }: {
  session: CaseSession; disabled: boolean;
  remove: (id: string) => Promise<CaseSession | null | undefined> | undefined;
}) {
  const attachments = session.attachments ?? [];
  if (!attachments.length) return null;
  return <section className="case-originals section" aria-label="Case originals">
    <h2><FileText size={20} aria-hidden="true" />Case originals</h2>
    <p className="muted">Adding or removing a file changes this open case. Choose Save case or Save changes to keep the changes after closing.</p>
    <ul className="case-original-list">{attachments.map(attachment => <CaseOriginal
      key={session.id + ':' + attachment.id + ':' + attachment.sha256 + ':' + attachment.original_available}
      caseId={session.id} attachment={attachment} disabled={disabled} remove={remove} />)}</ul>
  </section>;
}
