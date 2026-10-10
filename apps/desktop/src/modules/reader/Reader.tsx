import { useEffect, useRef, useState } from 'react';
import { api, apiResponse, ApiError, isCancelled } from '../../platform/api';
import { Button, ErrorState, LoadingState, Notice } from '../../ui';
import type { ContentLocator, PassageDraft, ReaderProps } from '../../platform/designC';
import { studyHelpHeaders } from '../../platform/designC';
import type { ReaderBlock, ReaderDocument } from './types';
import './reader.css';

/** Only trusted app code calls the API. Assets are decoded/rasterised PNGs. */
function Asset({ assetId, request, sha256, zoom, studyHelpContext }: { assetId: string; request: object; sha256: string; zoom: number; studyHelpContext?: ReaderProps['studyHelpContext'] }) {
  const [url, setUrl] = useState<string>();
  const [error, setError] = useState<unknown>();
  const key = JSON.stringify({ ...request, asset_id: assetId, original_sha256: sha256 });
  const studyContext = JSON.stringify(studyHelpContext);
  useEffect(() => {
    const controller = new AbortController();
    let ownedUrl: string | undefined;
    setUrl(undefined); setError(undefined);
    void (async () => {
      try {
        const response = await apiResponse('/readers/asset', { method: 'POST', body: JSON.parse(key), signal: controller.signal,
          headers: studyHelpHeaders(studyHelpContext) });
        if (response.headers.get('content-type')?.split(';')[0] !== 'image/png') throw new ApiError('The preview returned an unexpected format.', 0, 'reader_asset_invalid');
        const blob = await response.blob();
        if (controller.signal.aborted) return;
        ownedUrl = URL.createObjectURL(blob); setUrl(ownedUrl);
      } catch (caught) { if (!controller.signal.aborted && !isCancelled(caught)) setError(caught); }
    })();
    return () => { controller.abort(); if (ownedUrl) URL.revokeObjectURL(ownedUrl); };
  }, [key, studyContext]);
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  if (error) return <ErrorState title="The page image could not be loaded" error={error} />;
  if (!url) return <LoadingState label="Loading page image" />;
  return <div className="reader-image-pan" tabIndex={0} aria-label="Page image; scroll or drag to pan"
    onPointerDown={event => {
      if (event.button !== 0) return;
      const pane = event.currentTarget;
      drag.current = { x: event.clientX, y: event.clientY, left: pane.scrollLeft, top: pane.scrollTop };
      pane.setPointerCapture(event.pointerId);
    }}
    onPointerMove={event => {
      if (!drag.current) return;
      event.currentTarget.scrollLeft = drag.current.left - (event.clientX - drag.current.x);
      event.currentTarget.scrollTop = drag.current.top - (event.clientY - drag.current.y);
    }}
    onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
    <img src={url} alt="Source page" draggable={false} style={{ width: zoom * 100 + '%' }} />
  </div>;
}

function Highlight({ text, query }: { text: string; query: string }) {
  const start = query ? text.toLocaleLowerCase().indexOf(query.toLocaleLowerCase()) : -1;
  return start < 0 ? <>{text}</> : <>{text.slice(0, start)}<mark>{text.slice(start, start + query.length)}</mark>{text.slice(start + query.length)}</>;
}

function TextBlock({ block, query }: { block: ReaderBlock; query: string }) {
  if (block.kind === 'table' && block.grid) {
    const { rows, header_rows: headers } = block.grid;
    return <div className="reader-table-scroll" tabIndex={0} aria-label="Source table">
      <table className="reader-prose-table" aria-label="Source document table">
        {headers > 0 && <thead>{rows.slice(0, headers).map((row, index) => <tr key={index}>
          {row.map((text, column) => <th scope="col" key={column}><Highlight text={text} query={query} /></th>)}
        </tr>)}</thead>}
        <tbody>{rows.slice(headers).map((row, index) => <tr key={index}>
          {row.map((text, column) => <td key={column}><Highlight text={text} query={query} /></td>)}
        </tr>)}</tbody>
      </table>
      {/* Grid text has canonical separators; DOM selections must not invent offsets. */}
    </div>;
  }
  const content = <Highlight text={block.text} query={query} />;
  const attributes = { 'data-reader-item': block.item_ref, className: 'reader-text-item' };
  if (block.kind === 'code') return <pre {...attributes}>{content}</pre>;
  if (block.kind === 'heading') return <div {...attributes} role="heading" aria-level={block.level ?? 2}>{content}</div>;
  if (block.kind === 'list_item') return <p {...attributes} className="reader-text-item reader-list-item">{content}</p>;
  return <p {...attributes}>{content}</p>;
}

function ReaderSession(props: ReaderProps) {
  const { reference, conversation, onPassage, studyHelpContext } = props;
  const studyContext = JSON.stringify(studyHelpContext);
  const headers = studyHelpHeaders(studyHelpContext);
  const locator = reference.locator;
  const [page, setPage] = useState(locator?.kind === 'pdf' ? locator.physical_page : locator?.kind === 'image' ? locator.frame : 1);
  const [sheet, setSheet] = useState(locator?.kind === 'table' ? locator.sheet_name ?? undefined : undefined);
  const [firstRow, setFirstRow] = useState(locator?.kind === 'table' ? locator.first_row : 1);
  const [document, setDocument] = useState<ReaderDocument>();
  const [error, setError] = useState<unknown>();
  const [actionError, setActionError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [selection, setSelection] = useState<ContentLocator | null>(null);
  const [zoom, setZoom] = useState(1);
  const [retry, setRetry] = useState(0);
  const request = { reference, conversation, page, sheet, first_row: firstRow, row_limit: 100 };
  const requestKey = JSON.stringify(request);
  const pendingAction = useRef<AbortController | null>(null);
  const download = useRef<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string>();
  const [loadedKey, setLoadedKey] = useState<string>();
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined); setSelection(null); setLoadedKey(undefined); setBusy(false); setActionError(undefined);
    pendingAction.current?.abort();
    void api<ReaderDocument>('/readers/resolve', { method: 'POST', body: JSON.parse(requestKey), signal: controller.signal, headers }).then(result => {
      if (!controller.signal.aborted) { setDocument(result); setLoadedKey(requestKey); }
    }).catch(caught => { if (!controller.signal.aborted && !isCancelled(caught)) setError(caught); });
    return () => controller.abort();
  }, [requestKey, retry, studyContext]);
  useEffect(() => () => {
    pendingAction.current?.abort();
    if (download.current) URL.revokeObjectURL(download.current);
  }, []);

  async function discuss(selected: ContentLocator) {
    if (!document || !onPassage || busy || !document.capabilities.passage) return;
    const controller = new AbortController(); pendingAction.current = controller;
    setBusy(true); setActionError(undefined);
    try {
      const passage = await api<PassageDraft>('/readers/passage', { method: 'POST', signal: controller.signal, headers,
        body: { ...request, locator: selected, original_sha256: document.original.sha256,
          expected_policy_revision: document.policy_revision, expected_context_epoch: document.context_epoch } });
      if (!controller.signal.aborted) onPassage(passage);
    } catch (caught) { if (!controller.signal.aborted && !isCancelled(caught)) setActionError(caught); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  async function prepareOriginal() {
    if (busy) return;
    const controller = new AbortController(); pendingAction.current = controller;
    setBusy(true); setActionError(undefined);
    try {
      const response = await apiResponse('/readers/original', { method: 'POST', body: request, signal: controller.signal, headers });
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (download.current) URL.revokeObjectURL(download.current);
      // The download is never mounted in a document frame, including HTML/XML.
      download.current = URL.createObjectURL(new Blob([blob], { type: 'application/octet-stream' }));
      setOriginalUrl(download.current);
    } catch (caught) { if (!controller.signal.aborted && !isCancelled(caught)) setActionError(caught); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }

  function captureSelection() {
    const selected = window.getSelection();
    if (!selected || selected.isCollapsed || !selected.rangeCount) { setSelection(null); return; }
    const range = selected.getRangeAt(0);
    const element = range.startContainer.nodeType === Node.ELEMENT_NODE ? range.startContainer as Element : range.startContainer.parentElement;
    const blockElement = element?.closest<HTMLElement>('[data-reader-item]');
    if (!blockElement || !blockElement.contains(range.endContainer)) { setSelection(null); return; }
    const prefix = range.cloneRange(); prefix.selectNodeContents(blockElement); prefix.setEnd(range.startContainer, range.startOffset);
    const start = Array.from(prefix.toString()).length;
    const end = start + Array.from(range.toString()).length;
    const itemRef = blockElement.dataset.readerItem;
    const item = document?.payload?.blocks.find(item => item.item_ref === itemRef);
    if (item && end > start && end <= Array.from(item.text).length) setSelection({ kind: 'text', item_ref: item.item_ref, start, end });
    else setSelection(null);
  }

  if (error) return <ErrorState title="The source could not be opened" error={error} onRetry={() => setRetry(value => value + 1)} />;
  if (!document || loadedKey !== requestKey) return <LoadingState label="Opening source" />;
  const payload = document.payload;
  const table = payload?.table;
  return <section className="reader" aria-label="Document reader">
    <header className="reader-header"><h2>{document.title}</h2><div className="reader-tools">
      {originalUrl ? <a className="button button-secondary" href={originalUrl} download={document.original.filename}>Save original</a> :
        <Button variant="secondary" busy={busy} onClick={() => void prepareOriginal()}>Prepare original download</Button>}
      <label>Find on this {payload?.kind === 'table' ? 'table window' : 'page'}<input type="search" value={query} onChange={event => setQuery(event.target.value)} /></label>
    </div></header>
    {actionError !== undefined && <ErrorState title="The source action could not be completed" error={actionError} />}
    {document.error && <Notice tone="warning"><p>{document.error.message} The retained original is still available above.</p></Notice>}
    {payload?.diagnostics.map(item => <p className="reader-status" key={item.code}>{item.message}</p>)}
    {!document.capabilities.passage && onPassage && <p className="reader-status">Passage discussion is unavailable for this source's permissions or extraction state.</p>}
    {payload && (payload.kind === 'pdf' || payload.kind === 'image') && <div className="reader-tools">
      <Button variant="ghost" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</Button>
      <label>{payload.kind === 'pdf' ? 'Physical page' : 'Image frame'}<input type="number" min={1} max={payload.pages ?? 1} value={page}
        onChange={event => { const value = Number(event.target.value); if (Number.isInteger(value) && value >= 1 && value <= (payload.pages ?? 1)) setPage(value); }} /></label>
      <span>of {payload.pages}</span><Button variant="ghost" disabled={page >= (payload.pages ?? 1)} onClick={() => setPage(value => value + 1)}>Next</Button>
      <Button variant="ghost" disabled={zoom <= 0.5} onClick={() => setZoom(value => Math.max(0.5, value - 0.25))}>Zoom out</Button>
      <span>{Math.round(zoom * 100)}%</span><Button variant="ghost" disabled={zoom >= 3} onClick={() => setZoom(value => Math.min(3, value + 0.25))}>Zoom in</Button>
      <Button variant="ghost" onClick={() => setZoom(1)}>Fit width</Button>
    </div>}
    {payload?.asset_id && <Asset assetId={payload.asset_id} request={request} sha256={document.original.sha256} zoom={zoom} studyHelpContext={studyHelpContext} />}
    {table && <>
      <div className="reader-tools">{table.format === 'xlsx' && <label>Sheet<select value={sheet ?? table.sheet_name ?? ''}
        onChange={event => { setSheet(event.target.value); setFirstRow(1); }}>{table.sheets.map(name => <option key={name}>{name}</option>)}</select></label>}
        <Button variant="ghost" disabled={firstRow <= 1} onClick={() => setFirstRow(value => Math.max(1, value - 100))}>Previous rows</Button>
        <span>Rows {firstRow}–{Math.min(firstRow + table.rows.length - 1, table.total_rows)} of {table.total_rows}</span>
        <Button variant="ghost" disabled={firstRow + table.rows.length > table.total_rows} onClick={() => setFirstRow(value => value + 100)}>Next rows</Button>
      </div>
      <div className="reader-table-scroll" tabIndex={0} aria-label="Source table"><table><thead><tr><th scope="col">Row</th>
        {Array.from({ length: table.total_columns }, (_, index) => <th scope="col" key={index}>Column {index + 1}</th>)}</tr></thead>
        <tbody>{table.rows.map((row, offset) => <tr key={firstRow + offset}><th scope="row">{firstRow + offset}</th>{row.map((cell, column) => <td key={column}>
          <button className="reader-cell" title={cell.formula ? cell.formula + (cell.cached ? '' : ' · no cached result') : cell.number_format ?? undefined}
            onClick={() => setSelection({ kind: 'table', format: table.format, sheet_name: table.sheet_name,
              first_row: firstRow + offset, last_row: firstRow + offset, first_column: column + 1, last_column: column + 1 })}>
            <Highlight text={cell.display} query={query} /></button></td>)}</tr>)}</tbody></table></div>
    </>}
    {!!payload?.blocks.length && <div className="reader-content" onMouseUp={captureSelection} onKeyUp={captureSelection}>
      {payload.blocks.map(item => item.kind === 'image' && item.asset_id ? <Asset key={item.item_ref} assetId={item.asset_id} request={request} sha256={document.original.sha256} zoom={1} studyHelpContext={studyHelpContext} /> :
        <div className="reader-block" key={item.item_ref}><TextBlock block={item} query={query} />
          {onPassage && document.capabilities.passage && item.text.length > 0 && Array.from(item.text).length <= 8000 && <Button variant="ghost" disabled={busy}
            onClick={() => void discuss({ kind: 'text', item_ref: item.item_ref, start: 0, end: Array.from(item.text).length })}>Discuss this passage</Button>}</div>)}
    </div>}
    {selection && onPassage && <div className="reader-selection"><span>Selected source passage</span><Button disabled={busy || !document.capabilities.passage}
      onClick={() => void discuss(selection)}>Ask about selected passage</Button></div>}
  </section>;
}

export default function Reader(props: ReaderProps) {
  // A different reference/context never inherits an old source, selection or Blob.
  return <ReaderSession key={JSON.stringify([props.reference, props.conversation, props.studyHelpContext])} {...props} />;
}
