// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { FileText, Square, X } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { Button, ErrorState, Input, Notice, Textarea } from '../../ui';
import type { AttachmentPreview, CaseCapabilities, CaseSession } from './types';

interface Work { controller: AbortController; previewId?: string }
const previewPath = (id: string) => '/cases/attachments/' + encodeURIComponent(id);
const media: Record<string, string> = { '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };

function pause(signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, 500);
    if (signal.aborted) abort();
    else signal.addEventListener('abort', abort, { once: true });
  });
}

export function CaseAttachments({ session, capabilities, disabled, apply }: {
  session: CaseSession; capabilities?: CaseCapabilities; disabled: boolean;
  apply: (id: string, text: string) => Promise<CaseSession | null | undefined> | undefined;
}) {
  const [preview, setPreview] = useState<AttachmentPreview>();
  const [text, setText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<unknown>();
  const [applying, setApplying] = useState(false);
  const current = useRef<Work | null>(null);
  const alive = useRef(false);

  useEffect(() => {
    alive.current = true;
    setPreview(undefined); setText(''); setProcessing(false); setApplying(false); setError(undefined);
    return () => {
      alive.current = false;
      const work = current.current;
      current.current = null;
      work?.controller.abort();
      if (work?.previewId) void api(previewPath(work.previewId), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
    };
  }, [session.id, session.revision]);

  async function discard() {
    const work = current.current;
    current.current = null;
    work?.controller.abort();
    setPreview(undefined); setText(''); setProcessing(false); setError(undefined);
    if (work?.previewId) {
      try { await api(previewPath(work.previewId), { method: 'DELETE', timeoutMs: 5000 }); }
      catch (failure) { if (alive.current && !isCancelled(failure)) setError(failure); }
    }
  }

  async function select(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !capabilities?.extraction?.supported || disabled || current.current) return;
    const suffix = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!media[suffix] || file.size === 0 || file.size > capabilities.extraction.max_bytes) {
      setError(new ApiError('Choose a PDF, PNG or JPEG file up to 10 MiB.', 413, 'case_attachment_limit'));
      return;
    }
    const work: Work = { controller: new AbortController() };
    current.current = work;
    setProcessing(true); setError(undefined); setPreview(undefined); setText('');
    try {
      const path = '/cases/sessions/' + encodeURIComponent(session.id) + '/attachments';
      const headers = { 'Content-Type': media[suffix], 'x-renulus-filename': encodeURIComponent(file.name),
        'x-renulus-case-options': JSON.stringify({ revision: session.revision,
          scope: { kind: 'temporary-case', entity_id: session.id }, title: 'Attachment text' }) };
      let value = await api<AttachmentPreview>(path + '/prepare', {
        method: 'POST', signal: work.controller.signal, headers,
      });
      work.previewId = value.id;
      if (!alive.current || current.current !== work || work.controller.signal.aborted) {
        void api(previewPath(value.id), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
        return;
      }
      if (value.case_id !== session.id || value.revision !== session.revision ||
        value.scope.kind !== 'temporary-case' || value.scope.entity_id !== session.id || value.state !== 'reading') {
        throw new ApiError('The case changed before the upload started. Select the file again.', 409, 'case_revision_conflict', true);
      }
      value = await api<AttachmentPreview>(path + '/extract', {
        method: 'POST', signal: work.controller.signal, body: file,
        headers: { ...headers, 'x-renulus-preview-id': work.previewId },
      });
      if (!alive.current || current.current !== work || work.controller.signal.aborted) return;
      while (value.state === 'reading' || value.state === 'processing') {
        value = await api<AttachmentPreview>(previewPath(value.id), { signal: work.controller.signal });
        if (!alive.current || current.current !== work || work.controller.signal.aborted) return;
        if (value.state === 'reading' || value.state === 'processing') await pause(work.controller.signal);
      }
      if (value.id !== work.previewId || value.case_id !== session.id || value.revision !== session.revision ||
        value.scope.kind !== 'temporary-case' || value.scope.entity_id !== session.id) {
        throw new ApiError('The case changed before extraction finished. Select the file again.', 409, 'case_revision_conflict', true);
      }
      if (value.state === 'failed') throw new ApiError(value.error?.message ?? 'The attachment could not be read. Try another file.',
        0, value.error?.code ?? 'case_extraction_failed', value.error?.retryable ?? true);
      if (value.state === 'ready') { setPreview(value); setText(value.text); }
      else { setProcessing(false); current.current = null; }
    } catch (failure) {
      if (alive.current && current.current === work) {
        if (!isCancelled(failure)) setError(failure);
        setProcessing(false);
        current.current = null;
        if (work.previewId) void api(previewPath(work.previewId), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
      }
    } finally {
      if (alive.current && current.current === work) setProcessing(false);
    }
  }

  async function useText() {
    if (!preview || !text.trim()) return;
    setApplying(true);
    try { await apply(preview.id, text.trim()); }
    finally { if (alive.current) setApplying(false); }
  }

  return <section className="case-attachments section" aria-label="Temporary attachment text">
    <h2><FileText size={20} aria-hidden="true" />Bring text from a file</h2>
    <p className="muted">Review extracted text before adding it to your case. Save keeps the case text and discussion; the original file stays on your computer.</p>
    {!capabilities?.extraction?.supported ? <p className="muted">Temporary attachment extraction is unavailable in this installation. Paste relevant text into your learning question.</p> :
      <Input label="PDF or image for text extraction" type="file" accept=".pdf,.png,.jpg,.jpeg" disabled={disabled || processing || !!preview || applying}
        hint={['PDF, PNG or JPEG', 'Up to 10 MiB',
          capabilities.extraction.max_pages ? 'Up to ' + capabilities.extraction.max_pages + ' PDF pages' : undefined,
          capabilities.extraction.image_pixels ? 'Images up to ' + (capabilities.extraction.image_pixels / 1_000_000) + ' MP' : undefined,
          'Temporary processing'].filter(Boolean).join(' · ')} onChange={event => void select(event)} />}
    {!!error && <ErrorState error={error} title="The attachment could not be read" />}
    {processing && <Notice><p>Reading attachment text locally. The preview remains temporary.</p>
      <Button variant="secondary" onClick={() => void discard()}><Square size={15} aria-hidden="true" />Stop extraction</Button></Notice>}
    {preview && <div className="case-extraction-preview">
      <p className="muted">{preview.filename} · {typeof preview.ocr.confidence === 'number' ?
        'OCR confidence: ' + Math.round(preview.ocr.confidence * 100) + '%.' : 'OCR confidence was not reported.'} Check numbers, units and tables against your file.</p>
      <Textarea label="Review extracted text" rows={8} maxLength={50000} value={text} disabled={disabled || applying}
        onChange={event => setText(event.target.value)} />
      <div className="actions"><Button variant="secondary" busy={applying} disabled={disabled || !text.trim()} onClick={() => void useText()}>Use extracted text</Button>
        <Button variant="ghost" disabled={applying} onClick={() => void discard()}><X size={16} aria-hidden="true" />Discard preview</Button></div>
      <p className="muted">Using this text does not save it. Choose Save case to keep it.</p>
    </div>}
    {capabilities?.image_interpretation && !capabilities.image_interpretation.supported &&
      <p className="muted">Image interpretation is unavailable. Text extraction reads labels and words; it does not interpret clinical images.</p>}
  </section>;
}
