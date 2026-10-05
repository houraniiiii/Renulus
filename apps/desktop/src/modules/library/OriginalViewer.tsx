import { useEffect, useRef, useState } from 'react';
import { apiResponse, ApiError, isCancelled } from '../../platform/api';
import { Button, ErrorState } from '../../ui';
import type { Citation } from './types';
import { officeOriginalExtension } from './file-formats';

export default function OriginalViewer({ citation, wholeOriginal }: { citation: Citation; wholeOriginal: boolean }) {
  const [original, setOriginal] = useState<{ url: string; type: string; text?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [imageFailed, setImageFailed] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
  const officeExtension = original ? officeOriginalExtension(original.type) : null;
  const imageExtension = original ? ({ 'image/png': 'png', 'image/jpeg': 'jpg', 'image/tiff': 'tiff', 'image/tif': 'tif' } as Record<string, string>)[original.type.toLowerCase().split(';')[0]] : null;
  const tiff = imageExtension === 'tiff' || imageExtension === 'tif';
  useEffect(() => () => {
    controller.current?.abort();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
  }, []);

  async function open() {
    if (busy || original) return;
    const pending = new AbortController(); controller.current = pending;
    setBusy(true); setError(undefined);
    try {
      const response = await apiResponse(citation.original_url, { signal: pending.signal });
      const blob = await response.blob();
      if (!blob.size) throw new ApiError('The original response was empty. Try again to load the source.', 0, 'empty_original', true);
      const text = blob.type.startsWith('text/') ? await blob.text() : undefined;
      if (pending.signal.aborted) return;
      objectUrl.current = URL.createObjectURL(blob);
      setOriginal({ url: objectUrl.current, type: blob.type, text });
    } catch (caught) { if (!pending.signal.aborted && !isCancelled(caught)) setError(caught); }
    finally { if (!pending.signal.aborted) setBusy(false); }
  }
  return <>
    <div className="actions"><Button variant="secondary" busy={busy} disabled={!!original} onClick={() => void open()}>{wholeOriginal ? 'Open whole original' : 'Open original'}{citation.page !== null ? ' · page ' + citation.page : ''}</Button></div>
    {error !== undefined && <ErrorState title="The original could not be loaded" error={error} onRetry={() => void open()} />}
    {original && (officeExtension ? <div className="library-document"><p className="muted">Save this original to view the complete document in an Office-compatible application.</p><div className="actions"><a className="button button-secondary" href={original.url} download={'renulus-original.' + officeExtension}>Save original (.{officeExtension})</a></div></div> :
      original.type.startsWith('image/') ? <figure className="library-original-figure">
        {tiff ? <p className="muted">TIFF previews are unavailable here. Save the original to view it in an image viewer.</p> : imageFailed ? <p className="field-error" role="alert">The image preview could not be displayed. Save the original to view it in an image viewer.</p> : <img className="library-original-image" src={original.url} alt="Original imported document" onError={() => setImageFailed(true)} />}
        <figcaption>{citation.title}</figcaption>
        {imageExtension && <div className="actions"><a className="button button-secondary" href={original.url} download={'renulus-original.' + imageExtension}>Save original (.{imageExtension})</a></div>}
      </figure> :
      original.text !== undefined ? <pre className="library-original-text">{original.text}</pre> :
        <iframe className="library-original" title="Original document viewer" src={original.url + (citation.page !== null ? '#page=' + citation.page : '')} />)}
  </>;
}
