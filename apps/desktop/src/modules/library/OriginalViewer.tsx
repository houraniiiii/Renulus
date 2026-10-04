import { useEffect, useRef, useState } from 'react';
import { apiResponse, isCancelled } from '../../platform/api';
import { Button, ErrorState } from '../../ui';
import type { Citation } from './types';

export default function OriginalViewer({ citation, wholeOriginal }: { citation: Citation; wholeOriginal: boolean }) {
  const [original, setOriginal] = useState<{ url: string; type: string; text?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const controller = useRef<AbortController | null>(null);
  const objectUrl = useRef<string | null>(null);
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
    {original && (original.type.startsWith('image/') ? <img className="library-original-image" src={original.url} alt="Original imported document" /> :
      original.text !== undefined ? <pre className="library-original-text">{original.text}</pre> :
        <iframe className="library-original" title="Original document viewer" src={original.url + (citation.page !== null ? '#page=' + citation.page : '')} />)}
  </>;
}
