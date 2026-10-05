// SPDX-License-Identifier: MIT
import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import { FileText, Square, X } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { Button, ErrorState, Input, Notice, Select, Textarea } from '../../ui';
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

export function CaseAttachments({ session, capabilities, disabled, apply, keepImage, discussImage }: {
  session: CaseSession; capabilities?: CaseCapabilities; disabled: boolean;
  apply: (id: string, text: string) => Promise<CaseSession | null | undefined> | undefined;
  keepImage?: (id: string) => Promise<CaseSession | null | undefined> | undefined;
  discussImage?: (id: string, model: string, question: string) => Promise<void>;
}) {
  const [preview, setPreview] = useState<AttachmentPreview>();
  const [text, setText] = useState('');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<unknown>();
  const [applying, setApplying] = useState(false);
  const [mode, setMode] = useState<'text' | 'image'>('text');
  const [model, setModel] = useState('');
  const [question, setQuestion] = useState('');
  const imageCapability = capabilities?.image_interpretation;
  const canRead = mode === 'image' ? imageCapability?.supported : capabilities?.extraction?.supported;
  const current = useRef<Work | null>(null);
  const alive = useRef(false);

  useEffect(() => {
    alive.current = true;
    setPreview(undefined); setText(''); setQuestion(''); setProcessing(false); setApplying(false); setError(undefined);
    return () => {
      alive.current = false;
      const work = current.current;
      current.current = null;
      work?.controller.abort();
      if (work?.previewId) void api(previewPath(work.previewId), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
    };
  }, [session.id, session.revision, session.scope.kind]);

  async function discard() {
    const work = current.current;
    current.current = null;
    work?.controller.abort();
    setPreview(undefined); setText(''); setQuestion(''); setProcessing(false); setError(undefined);
    if (work?.previewId) {
      try { await api(previewPath(work.previewId), { method: 'DELETE', timeoutMs: 5000 }); }
      catch (failure) { if (alive.current && !isCancelled(failure)) setError(failure); }
    }
  }

  async function select(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file || !canRead || disabled || current.current) return;
    const suffix = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    if (!media[suffix] || (mode === 'image' && suffix === '.pdf') || file.size === 0 || file.size > (mode === 'image' ? imageCapability?.max_bytes ?? 8 * 1024 * 1024 : capabilities?.extraction?.max_bytes ?? 0)) {
      setError(new ApiError(mode === 'image' ? 'Choose a PNG or JPEG image up to 8 MiB and 16 MP.' : 'Choose a PDF, PNG or JPEG file up to 10 MiB.', 413, 'case_attachment_limit'));
      return;
    }
    const work: Work = { controller: new AbortController() };
    current.current = work;
    setProcessing(true); setError(undefined); setPreview(undefined); setText('');
    try {
      const path = '/cases/sessions/' + encodeURIComponent(session.id) + '/attachments';
      const headers = { 'Content-Type': media[suffix], 'x-renulus-filename': encodeURIComponent(file.name),
        'x-renulus-case-options': JSON.stringify({ revision: session.revision,
          scope: { kind: 'temporary-case', entity_id: session.id }, title: mode === 'image' ? 'Temporary image' : 'Attachment text', ...(mode === 'image' ? { mode } : {}) }) };
      let value = await api<AttachmentPreview>(path + '/prepare', {
        method: 'POST', signal: work.controller.signal, headers,
      });
      work.previewId = value.id;
      if (!alive.current || current.current !== work || work.controller.signal.aborted) {
        void api(previewPath(value.id), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
        return;
      }
      if (value.case_id !== session.id || value.revision !== session.revision ||
        value.scope.kind !== 'temporary-case' || value.scope.entity_id !== session.id || value.state !== 'reading' || (value.mode ?? 'text') !== mode) {
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
        value.scope.kind !== 'temporary-case' || value.scope.entity_id !== session.id || (value.mode ?? 'text') !== mode) {
        throw new ApiError('The case changed before extraction finished. Select the file again.', 409, 'case_revision_conflict', true);
      }
      if (value.state === 'failed') throw new ApiError(value.error?.message ?? 'The attachment could not be read. Try another file.',
        0, value.error?.code ?? 'case_extraction_failed', value.error?.retryable ?? true);
      if (value.state === 'ready' && mode === 'image' && (!value.image || !['image/png', 'image/jpeg'].includes(value.image.media_type) || !/^[A-Za-z0-9+/]+={0,2}$/.test(value.image.data))) {
        throw new ApiError('The image preview is invalid. Select the image again.', 422, 'invalid_image');
      }
      if (value.state === 'ready') { setPreview(value); setText(value.text); setModel(imageCapability?.models?.[0] ?? ''); }
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

  async function keep() {
    if (!preview || !keepImage) return;
    setApplying(true);
    try { await keepImage(preview.id); }
    catch (failure) { if (alive.current && !isCancelled(failure)) setError(failure); }
    finally { if (alive.current) setApplying(false); }
  }

  return <section className="case-attachments section" aria-label="Temporary attachments">
    <h2><FileText size={20} aria-hidden="true" />Bring a file into your case</h2>
    <p className="muted">Review extracted text or select an image. Save keeps the case text, completed discussion and PDF, PNG or JPEG originals you explicitly add. A case can keep up to 16 originals totalling 32 MiB.</p>
    <Select label="Use this file for" value={mode} disabled={disabled || processing || !!preview} onChange={event => setMode(event.target.value as 'text' | 'image')}>
      <option value="text">Local text extraction</option><option value="image" disabled={!imageCapability?.supported || !discussImage}>Image discussion with selected subscription</option></Select>
    {!canRead ? <p className="muted">Temporary attachment extraction is unavailable in this installation. Paste relevant text into your learning question.</p> :
      <Input label={mode === 'image' ? 'Image to review before sending' : 'PDF or image for text extraction'} type="file" accept={mode === 'image' ? '.png,.jpg,.jpeg' : '.pdf,.png,.jpg,.jpeg'} disabled={disabled || processing || !!preview || applying}
        hint={[mode === 'image' ? 'PNG or JPEG' : 'PDF, PNG or JPEG', mode === 'image' ? 'Up to 8 MiB · Images up to 16 MP' : 'Up to 10 MiB',
          capabilities?.extraction?.max_pages && mode === 'text' ? 'Up to ' + capabilities.extraction.max_pages + ' PDF pages' : undefined,
          capabilities?.extraction?.image_pixels && mode === 'text' ? 'Images up to ' + (capabilities.extraction.image_pixels / 1_000_000) + ' MP' : undefined,
          'Temporary processing'].filter(Boolean).join(' · ')} onChange={event => void select(event)} />}
    {!!error && <ErrorState error={error} title="The attachment could not be read" />}
    {processing && <Notice><p>{mode === 'image' ? 'Validating the image locally. Review it before sending to your selected subscription.' : 'Reading attachment text locally. The preview remains temporary.'}</p>
      <Button variant="secondary" onClick={() => void discard()}><Square size={15} aria-hidden="true" />{mode === 'image' ? 'Stop image preparation' : 'Stop extraction'}</Button></Notice>}
    {preview?.mode === 'image' && preview.image && <div className="case-extraction-preview">
      <img src={'data:' + preview.image.media_type + ';base64,' + preview.image.data} alt="Selected image for temporary case discussion" style={{ maxWidth: '100%', maxHeight: 360, objectFit: 'contain' }} />
      <Notice><p>This preview is temporary. Keep image in case or send it for discussion to add its original. Choose Save case or Save changes to retain it after closing. Keeping an image does not send it to a model. Clinical accuracy and live image interpretation are unverified.</p></Notice>
      {keepImage && <div className="actions"><Button variant="secondary" busy={applying} disabled={disabled} onClick={() => void keep()}>Keep image in case</Button></div>}
      <Select label="Selected account image model" value={model} disabled={disabled || applying} onChange={event => setModel(event.target.value)}>{imageCapability?.models?.map(value => <option key={value}>{value}</option>)}</Select>
      <Textarea label="Question about this image" value={question} maxLength={11800} disabled={disabled || applying} onChange={event => setQuestion(event.target.value)} />
      <div className="actions"><Button disabled={disabled || applying || !question.trim() || !imageCapability?.models?.includes(model)} onClick={() => { if (discussImage) void discussImage(preview.id, model, question.trim()); }}>Send image for discussion</Button>
        <Button variant="ghost" disabled={disabled || applying} onClick={() => void discard()}>Discard image</Button></div>
    </div>}
    {preview && preview.mode !== 'image' && <div className="case-extraction-preview">
      <p className="muted">{preview.filename} · {typeof preview.ocr.confidence === 'number' ?
        'OCR confidence: ' + Math.round(preview.ocr.confidence * 100) + '%.' : 'OCR confidence was not reported.'} Check numbers, units and tables against your file.</p>
      <Textarea label="Review extracted text" rows={8} maxLength={50000} value={text} disabled={disabled || applying}
        onChange={event => setText(event.target.value)} />
      <div className="actions"><Button variant="secondary" busy={applying} disabled={disabled || !text.trim()} onClick={() => void useText()}>Use extracted text</Button>
        <Button variant="ghost" disabled={applying} onClick={() => void discard()}><X size={16} aria-hidden="true" />Discard preview</Button></div>
      <p className="muted">Using this text adds the reviewed text and its original to this case. Choose Save case or Save changes to keep both after closing.</p>
    </div>}
    {capabilities?.image_interpretation && !capabilities.image_interpretation.supported &&
      <p className="muted">Image discussion is unavailable: {capabilities.image_interpretation.reason} Text extraction reads labels and words; it does not interpret clinical images.</p>}
  </section>;
}
