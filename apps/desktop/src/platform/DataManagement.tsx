import { useCallback, useEffect, useId, useRef, useState, type ChangeEvent } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { Badge, Button, ErrorState, Input, LoadingState, Notice } from '../ui';
import { api, apiResponse, ApiError, isCancelled } from './api';
import './DataManagement.css';

const MiB = 1024 * 1024;
const defaultLimits = { archive_bytes: 288 * MiB, json_bytes: 16 * MiB, original_bytes: 64 * MiB, total_original_bytes: 256 * MiB, originals: 1000 };
type Limits = typeof defaultLimits;
interface Omissions { knowledge_catalogue: { records: number; reason: string } }
const catalogueReason = 'Acquisition catalogue input metadata is excluded. Retained library document metadata and provenance remain included.';
const deletionNotice = 'Restoring merges with this installation and preserves its newer deletion markers. An older backup on its own cannot know about later deletions, including on another installation.';
const rebuildStatuses = ['idle', 'required', 'running', 'complete', 'blocked', 'partial', 'failed'] as const;
type RebuildStatus = typeof rebuildStatuses[number];
interface ModuleStatus { status: string; rebuilt_records?: number; rebuilt_unit?: 'records' | 'passages'; cleanup_pending?: boolean; error_code?: string; message?: string }
interface Rebuild { status: RebuildStatus; modules: { knowledge?: ModuleStatus; memory?: ModuleStatus }; error_code?: string; message?: string }
interface RestoreResult {
  restored_records: number; restored_originals?: number; excluded_by_deletion: number; removed_by_deletion: number;
  excluded_originals?: number; exported_at: string; indexes: 'rebuild-required'; recovery_id: string; rebuild: Rebuild; data_kind?: 'full-backup' | 'records-only';
}
interface Recovery { last_restore: Partial<RestoreResult> | null; rebuild: Rebuild; limits?: Limits; omissions?: Omissions; backup_scope?: string }
interface RecordsBundle { format: 'renulus-canonical-export'; exported_at: string; records: Record<string, Record<string, unknown>[]>; limits?: string; omissions?: Omissions }
interface PreviewBase { fileName: string; exportedAt: string; recordCount: number; notice: string; omissions?: Omissions }
type Preview =
  | (PreviewBase & { kind: 'zip'; token: string; expiresAt: string; originalCount: number; originalBytes: number })
  | (PreviewBase & { kind: 'json'; bundle: RecordsBundle });

function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function count(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0; }
function dated(value: unknown): value is string {
  return typeof value === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) && Number.isFinite(Date.parse(value));
}
function utc(value: string) {
  return new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(value)) + ' UTC';
}
function bytes(value: number) { return value >= MiB ? new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1 }).format(value / MiB) + ' MiB' : new Intl.NumberFormat('en-GB').format(value) + ' bytes'; }
function quantity(value: number, unit: string) { return value.toLocaleString('en-GB') + ' ' + unit + (value === 1 ? '' : 's'); }
function invalid(message: string) { return new ApiError(message, 0, 'invalid_recovery_response'); }
function readOmissions(value: unknown): Omissions | undefined {
  if (value === undefined || (object(value) && Object.keys(value).length === 0)) return undefined;
  if (!object(value) || !object(value.knowledge_catalogue) || !count(value.knowledge_catalogue.records) ||
    typeof value.knowledge_catalogue.reason !== 'string' || !value.knowledge_catalogue.reason.trim()) throw invalid('The local runtime did not report the acquisition catalogue omission clearly. Refresh status or choose the file again.');
  return value as unknown as Omissions;
}
function readRebuild(value: unknown): Rebuild {
  if (!object(value) || !rebuildStatuses.includes(value.status as RebuildStatus) || !object(value.modules) ||
    (value.message !== undefined && typeof value.message !== 'string') || (value.error_code !== undefined && typeof value.error_code !== 'string') ||
    ![value.modules.knowledge, value.modules.memory].every(module => module === undefined || (object(module) && typeof module.status === 'string' &&
      (module.rebuilt_records === undefined || count(module.rebuilt_records)) &&
      (module.rebuilt_unit === undefined || ['records', 'passages'].includes(module.rebuilt_unit as string)) &&
      (module.cleanup_pending === undefined || typeof module.cleanup_pending === 'boolean') &&
      (module.message === undefined || typeof module.message === 'string') &&
      (module.error_code === undefined || typeof module.error_code === 'string')))) {
    throw invalid('The local runtime did not report a complete rebuild status. Refresh status to check it.');
  }
  return value as unknown as Rebuild;
}
function readRecovery(value: unknown): Recovery {
  if (!object(value) || !object(value.limits) || !Object.keys(defaultLimits).every(key => count((value.limits as Record<string, unknown>)[key])) ||
    (value.last_restore !== null && !object(value.last_restore))) throw invalid('Recovery status is incomplete. Refresh status to check the local limits and indexes.');
  if (value.backup_scope !== undefined && typeof value.backup_scope !== 'string') throw invalid('The local runtime did not report a valid backup scope. Refresh recovery status.');
  return { last_restore: value.last_restore as Recovery['last_restore'], rebuild: readRebuild(value.rebuild), limits: value.limits as Limits, omissions: readOmissions(value.omissions), backup_scope: value.backup_scope };
}
function readZipPreview(value: unknown, fileName: string): Preview {
  if (!object(value) || value.format !== 'renulus-full-backup' || typeof value.preview_token !== 'string' || !value.preview_token.trim() ||
    !dated(value.exported_at) || !dated(value.expires_at) || !count(value.record_count) || !count(value.original_count) || !count(value.original_bytes) ||
    typeof value.deletion_notice !== 'string' || !value.deletion_notice.trim()) throw invalid('The ZIP preview is incomplete. Choose the backup again to validate it before restoring.');
  if (Date.parse(value.expires_at) <= Date.now()) throw invalid('This ZIP preview has expired. Choose the backup again to validate it.');
  return { kind: 'zip', fileName, exportedAt: value.exported_at, token: value.preview_token, expiresAt: value.expires_at,
    recordCount: value.record_count, originalCount: value.original_count, originalBytes: value.original_bytes, notice: value.deletion_notice, omissions: readOmissions(value.omissions) };
}
function readRecords(text: string, fileName: string): Preview {
  let value: unknown;
  try { value = JSON.parse(text); } catch { throw new ApiError('This file is not valid JSON. Choose a Renulus records export.', 0, 'invalid_export'); }
  if (!object(value) || value.format !== 'renulus-canonical-export' || !dated(value.exported_at) || !object(value.records) ||
    !Object.values(value.records).every(rows => Array.isArray(rows) && rows.every(object))) {
    throw new ApiError('This is not a Renulus records export with a valid date and record lists. Choose a ZIP backup or a supported JSON export.', 0, 'invalid_export');
  }
  const bundle = value as unknown as RecordsBundle;
  const catalogue = bundle.records.knowledge_catalogue;
  const omissions = readOmissions(value.omissions) ?? (catalogue ? { knowledge_catalogue: { records: catalogue.length, reason: catalogueReason } } : undefined);
  const recordCount = Object.entries(bundle.records).reduce((total, [name, rows]) => total + (name === 'knowledge_catalogue' ? 0 : rows.length), 0);
  return { kind: 'json', fileName, exportedAt: bundle.exported_at, recordCount,
    notice: typeof bundle.limits === 'string' ? bundle.limits : deletionNotice, omissions, bundle };
}
function readText(file: File, signal: AbortSignal): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    const abort = () => reader.abort();
    const finish = () => signal.removeEventListener('abort', abort);
    reader.onload = () => { finish(); resolve(String(reader.result)); };
    reader.onerror = () => { finish(); reject(new ApiError('The records export could not be read. Choose the file again.', 0, 'file_unreadable')); };
    reader.onabort = () => { finish(); reject(new DOMException('File selection cancelled.', 'AbortError')); };
    if (signal.aborted) { reject(new DOMException('File selection cancelled.', 'AbortError')); return; }
    signal.addEventListener('abort', abort, { once: true });
    reader.readAsText(file);
  });
}
function readRestore(value: unknown, kind: Preview['kind']): RestoreResult {
  if (!object(value) || !count(value.restored_records) || !count(value.excluded_by_deletion) || !count(value.removed_by_deletion) ||
    !dated(value.exported_at) || value.indexes !== 'rebuild-required' || typeof value.recovery_id !== 'string' ||
    (kind === 'zip' && (!count(value.restored_originals) || !count(value.excluded_originals)))) {
    throw invalid('The restore outcome could not be confirmed. Refresh recovery status before trying another restore.');
  }
  return { ...value, rebuild: readRebuild(value.rebuild) } as unknown as RestoreResult;
}
const statusLabels: Record<RebuildStatus, string> = { idle: 'Not rebuilding', required: 'Rebuild needed', running: 'Rebuilding', complete: 'Complete', blocked: 'Blocked', partial: 'Partial', failed: 'Failed' };
const statusMessages: Record<RebuildStatus, string> = {
  idle: 'A restore schedules a local rebuild after deletion checks.',
  required: 'A local rebuild is needed before restored records can be retrieved.',
  running: 'Rebuilding library search and learning memory locally. Status updates automatically.',
  complete: 'The local rebuild has finished. See each module result below.',
  blocked: 'Local helpers are unavailable. Review the messages below, then retry when they are available.',
  partial: 'The local rebuild is only partly complete. Review the module results and any pending cleanup, then retry.',
  failed: 'The local rebuild failed. Review the messages below, then retry.',
};
function tone(status: string): 'default' | 'neutral' | 'warning' | 'error' {
  return status === 'complete' ? 'default' : status === 'failed' ? 'error' : ['blocked', 'partial', 'required'].includes(status) ? 'warning' : 'neutral';
}
function CatalogueOmission({ omissions, copy = false }: { omissions?: Omissions; copy?: boolean }) {
  const catalogue = omissions?.knowledge_catalogue;
  return <div className="data-catalogue-omission"><p><strong>{catalogue ? catalogue.records.toLocaleString('en-GB') + ' acquisition catalogue records excluded' : 'Acquisition catalogue excluded'}</strong></p><p className="muted">{catalogue?.reason ?? catalogueReason}</p>{!catalogue && copy && <p className="muted">This copy does not report an omission count.</p>}</div>;
}

/** Renderer-only recovery controls. All operations use the authenticated app transport. */
export function DataManagement() {
  const id = useId();
  const [recovery, setRecovery] = useState<Recovery>();
  const [recoveryError, setRecoveryError] = useState<unknown>();
  const [refreshing, setRefreshing] = useState(true);
  const [fileName, setFileName] = useState<string>();
  const [preview, setPreview] = useState<Preview>();
  const [checking, setChecking] = useState(false);
  const [reviewedDate, setReviewedDate] = useState(false);
  const [acknowledgedLimits, setAcknowledgedLimits] = useState(false);
  const [restoreError, setRestoreError] = useState<unknown>();
  const [cleanupError, setCleanupError] = useState<unknown>();
  const [downloadError, setDownloadError] = useState<unknown>();
  const [downloadNotice, setDownloadNotice] = useState<string>();
  const [downloading, setDownloading] = useState<'zip' | 'json'>();
  const [busy, setBusy] = useState<'restore' | 'rebuild'>();
  const mounted = useRef(false);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const stagedToken = useRef<string | undefined>(undefined);
  const selectionVersion = useRef(0);
  const selectionRequest = useRef<AbortController | null>(null);
  const downloadRequest = useRef<AbortController | null>(null);
  const mutationRequest = useRef<AbortController | null>(null);
  const recoveryRequest = useRef<AbortController | null>(null);
  const recoveryVersion = useRef(0);
  const recoveryTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const lastRecovery = useRef<Recovery | undefined>(undefined);
  const objectUrls = useRef(new Set<string>());

  const stopRecoveryRead = useCallback(() => {
    ++recoveryVersion.current; recoveryRequest.current?.abort(); clearTimeout(recoveryTimer.current);
  }, []);
  const refreshRecovery = useCallback(async function readStatus(visible = true) {
    if (!mounted.current || mutationRequest.current) return;
    stopRecoveryRead();
    const version = recoveryVersion.current;
    const controller = new AbortController(); recoveryRequest.current = controller;
    if (visible) setRefreshing(true);
    try {
      const result = readRecovery(await api<unknown>('/data/recovery', { signal: controller.signal }));
      if (controller.signal.aborted || version !== recoveryVersion.current || !mounted.current) return;
      lastRecovery.current = result; setRecovery(result); setRecoveryError(undefined);
      if (result.rebuild.status === 'running') recoveryTimer.current = setTimeout(() => void readStatus(false), 1500);
    } catch (error) {
      if (controller.signal.aborted || version !== recoveryVersion.current || !mounted.current || isCancelled(error)) return;
      setRecoveryError(error);
      if (lastRecovery.current?.rebuild.status === 'running') recoveryTimer.current = setTimeout(() => void readStatus(false), 3000);
    } finally { if (!controller.signal.aborted && version === recoveryVersion.current && mounted.current) setRefreshing(false); }
  }, [stopRecoveryRead]);
  const discard = useCallback(async (token: string) => {
    try { await api('/data/backup/preview/' + encodeURIComponent(token), { method: 'DELETE', keepalive: true, timeoutMs: 5000 }); }
    catch (error) { if (mounted.current && !(error instanceof ApiError && [404, 410].includes(error.status))) setCleanupError(new ApiError('The staged ZIP could not be discarded. Its restore permission has been cleared here; the local preview will expire automatically.', 0, 'preview_cleanup_failed')); }
  }, []);
  const clearSelection = useCallback((resetInput = true) => {
    ++selectionVersion.current; selectionRequest.current?.abort(); selectionRequest.current = null;
    const token = stagedToken.current; stagedToken.current = undefined; if (token) void discard(token);
    setPreview(undefined); setReviewedDate(false); setAcknowledgedLimits(false); setChecking(false); setRestoreError(undefined); setFileName(undefined);
    if (resetInput && fileInput.current) fileInput.current.value = '';
  }, [discard]);
  useEffect(() => {
    mounted.current = true; void refreshRecovery();
    return () => {
      mounted.current = false; ++selectionVersion.current; selectionRequest.current?.abort(); downloadRequest.current?.abort(); mutationRequest.current?.abort(); stopRecoveryRead();
      const token = stagedToken.current; stagedToken.current = undefined; if (token) void discard(token);
      objectUrls.current.forEach(url => URL.revokeObjectURL(url)); objectUrls.current.clear();
    };
  }, [discard, refreshRecovery, stopRecoveryRead]);
  useEffect(() => {
    if (preview?.kind !== 'zip' || busy === 'restore') return;
    const remaining = Date.parse(preview.expiresAt) - Date.now();
    const timer = setTimeout(() => {
      if (stagedToken.current !== preview.token) return;
      clearSelection(); setFileName(preview.fileName);
      setRestoreError(new ApiError('This ZIP preview has expired. Choose the backup again to validate it.', 0, 'preview_expired'));
    }, Math.min(Math.max(remaining, 0), 2_147_483_647));
    return () => clearTimeout(timer);
  }, [preview, busy, clearSelection]);

  async function selectFile(event: ChangeEvent<HTMLInputElement>) {
    if (mutationRequest.current) return;
    const file = event.target.files?.[0];
    clearSelection(false);
    if (!file) return;
    const version = selectionVersion.current;
    const controller = new AbortController(); selectionRequest.current = controller;
    const current = () => mounted.current && !controller.signal.aborted && version === selectionVersion.current;
    setFileName(file.name); setChecking(true);
    const limits = lastRecovery.current?.limits ?? defaultLimits;
    let token: string | undefined;
    try {
      const extension = file.name.toLowerCase().split('.').pop();
      if (extension !== 'zip' && extension !== 'json') throw new ApiError('Choose a Renulus ZIP backup or a records-only JSON export.', 0, 'unsupported_backup');
      const limit = extension === 'zip' ? limits.archive_bytes : limits.json_bytes;
      if (file.size > limit) throw new ApiError('This file exceeds the local ' + (extension === 'zip' ? 'ZIP' : 'JSON') + ' limit of ' + bytes(limit) + '. Choose a smaller export.', 0, 'backup_too_large');
      let result: Preview;
      if (extension === 'zip') {
        const response = await api<unknown>('/data/backup/preview', { method: 'POST', body: file, headers: { 'Content-Type': 'application/zip' }, signal: controller.signal, timeoutMs: 120_000 });
        if (object(response) && typeof response.preview_token === 'string' && response.preview_token.trim()) token = response.preview_token;
        if (!current()) { if (token) void discard(token); return; }
        result = readZipPreview(response, file.name);
      } else {
        const text = await readText(file, controller.signal);
        if (!current()) return;
        result = readRecords(text, file.name);
      }
      if (!current()) return;
      stagedToken.current = token; setPreview(result);
    } catch (error) {
      if (token) void discard(token);
      if (current() && !isCancelled(error)) setRestoreError(error);
    } finally { if (current()) { setChecking(false); selectionRequest.current = null; } }
  }
  async function download(kind: 'zip' | 'json') {
    if (downloadRequest.current) return;
    const controller = new AbortController(); downloadRequest.current = controller;
    setDownloading(kind); setDownloadError(undefined); setDownloadNotice(undefined);
    try {
      const mime = kind === 'zip' ? 'application/zip' : 'application/json';
      const response = await apiResponse(kind === 'zip' ? '/data/backup' : '/data/export', { headers: { Accept: mime }, signal: controller.signal, timeoutMs: 120_000 });
      if (response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== mime) throw invalid('The local runtime returned the wrong download format. Try the download again.');
      const blob = await response.blob();
      if (controller.signal.aborted || !mounted.current) return;
      const url = URL.createObjectURL(blob); objectUrls.current.add(url);
      const anchor = document.createElement('a'); anchor.href = url;
      const suggested = response.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/i)?.[1];
      anchor.download = suggested && /^[a-z0-9_. -]+$/i.test(suggested) && suggested.toLowerCase().endsWith('.' + kind)
        ? suggested : 'renulus-' + (kind === 'zip' ? 'full-backup-' : 'records-') + new Date().toISOString().slice(0, 10) + '.' + kind;
      document.body.append(anchor); anchor.click(); anchor.remove();
      setTimeout(() => { if (objectUrls.current.delete(url)) URL.revokeObjectURL(url); }, 1000);
      setDownloadNotice(kind === 'zip' ? 'Full backup download started. Keep the ZIP in a safe location.' : 'Records-only JSON download started. Library originals are not included.');
    } catch (error) { if (!controller.signal.aborted && mounted.current && !isCancelled(error)) setDownloadError(error); }
    finally { if (mounted.current && downloadRequest.current === controller) { downloadRequest.current = null; setDownloading(undefined); } }
  }
  function reportRebuild(rebuild: Rebuild, restored?: RestoreResult) {
    const result: Recovery = { last_restore: restored ?? lastRecovery.current?.last_restore ?? null, rebuild, limits: lastRecovery.current?.limits, omissions: lastRecovery.current?.omissions, backup_scope: lastRecovery.current?.backup_scope };
    lastRecovery.current = result; setRecovery(result); setRecoveryError(undefined);
  }
  async function restore() {
    if (!preview || !reviewedDate || !acknowledgedLimits || mutationRequest.current) return;
    if (preview.kind === 'zip' && (stagedToken.current !== preview.token || Date.parse(preview.expiresAt) <= Date.now())) {
      clearSelection(); setRestoreError(new ApiError('This ZIP preview has expired. Choose the backup again to validate it.', 0, 'preview_expired')); return;
    }
    const controller = new AbortController(); mutationRequest.current = controller; stopRecoveryRead();
    setBusy('restore'); setRestoreError(undefined); setReviewedDate(false); setAcknowledgedLimits(false);
    try {
      const value = await api<unknown>(preview.kind === 'zip' ? '/data/backup/restore' : '/data/restore', {
        method: 'POST', signal: controller.signal, timeoutMs: 120_000,
        body: preview.kind === 'zip'
          ? { preview_token: preview.token, confirmed_exported_at: preview.exportedAt, acknowledge_deletion_limits: true }
          : { bundle: preview.bundle, confirm_backup_date: true, confirmed_exported_at: preview.exportedAt },
      });
      if (controller.signal.aborted || !mounted.current) return;
      const result = readRestore(value, preview.kind);
      stagedToken.current = undefined; clearSelection(); reportRebuild(result.rebuild, result);
    } catch (error) {
      if (!controller.signal.aborted && mounted.current && !isCancelled(error)) { clearSelection(); setRestoreError(error); }
    } finally {
      if (mounted.current && mutationRequest.current === controller) { mutationRequest.current = null; setBusy(undefined); void refreshRecovery(false); }
    }
  }
  async function rebuild() {
    if (mutationRequest.current || !lastRecovery.current || lastRecovery.current.rebuild.status === 'running' || (lastRecovery.current.rebuild.status === 'idle' && !lastRecovery.current.last_restore)) return;
    const controller = new AbortController(); mutationRequest.current = controller; stopRecoveryRead(); setBusy('rebuild'); setRecoveryError(undefined);
    let poll = false;
    try {
      const result = readRebuild(await api<unknown>('/data/rebuild', { method: 'POST', signal: controller.signal, timeoutMs: 120_000 }));
      if (!controller.signal.aborted && mounted.current) { reportRebuild(result); poll = result.status === 'running'; }
    } catch (error) { if (!controller.signal.aborted && mounted.current && !isCancelled(error)) setRecoveryError(error); }
    finally {
      if (mounted.current && mutationRequest.current === controller) {
        mutationRequest.current = null; setBusy(undefined);
        if (poll) void refreshRecovery(false);
      }
    }
  }

  const limits = recovery?.limits ?? defaultLimits;
  const canRestore = !!preview && reviewedDate && acknowledgedLimits && !busy && !checking;
  const lastRestore = recovery?.last_restore;
  return <section className="data-management" aria-labelledby={id + '-title'}>
    <div className="data-backup-heading">
      <div className="data-copy"><h2 id={id + '-title'}>Your study data</h2><p>Keep a copy of your saved learning and eligible library originals.</p><p className="muted">{recovery?.backup_scope ?? 'Credentials, search indexes and the acquisition catalogue are excluded.'} Indexes are rebuilt locally after a restore.</p></div>
      <Button onClick={() => void download('zip')} busy={downloading === 'zip'} disabled={!!downloading || !!busy}><Download size={17} aria-hidden="true" />{downloading === 'zip' ? 'Preparing full backup…' : 'Download full backup (ZIP)'}</Button>
    </div>
    <CatalogueOmission omissions={recovery?.omissions} />
    <div className="data-records-export"><Button variant="ghost" onClick={() => void download('json')} busy={downloading === 'json'} disabled={!!downloading || !!busy}>{downloading === 'json' ? 'Preparing records export…' : 'Export records only (JSON)'}</Button><p className="muted">Records only, without attachment bytes or indexes. This is not a full backup.</p></div>
    {!!downloadError && <ErrorState title="Download could not be prepared" error={downloadError} />}
    {downloadNotice && <Notice><p>{downloadNotice}</p></Notice>}
    {!!cleanupError && <Notice tone="warning"><p>{cleanupError instanceof ApiError ? cleanupError.message : 'The staged preview could not be discarded; it will expire automatically.'}</p></Notice>}
    <div className="data-recovery-columns">
      <section className="data-restore" aria-labelledby={id + '-restore'}>
        <div className="data-copy"><h3 id={id + '-restore'}>Restore from a copy</h3><p>Choose a file, review its date and contents, then confirm the restore.</p></div>
        <Input id={id + '-file'} label="Choose ZIP backup or JSON export" type="file" accept=".zip,application/zip,.json,application/json" disabled={!!busy} onChange={event => { fileInput.current = event.currentTarget; void selectFile(event); }} hint={'ZIP up to ' + bytes(limits.archive_bytes) + '; records-only JSON up to ' + bytes(limits.json_bytes) + '.'} />
        {fileName && <p className="data-file-name">Selected: <strong>{fileName}</strong></p>}
        {checking && <LoadingState label="Validating your selected file" />}
        {!!restoreError && <ErrorState title="Restore is not ready" error={restoreError} />}
        {preview ? <div className="data-preview">
          <div role="status"><Badge tone={preview.kind === 'zip' ? 'default' : 'neutral'}>{preview.kind === 'zip' ? 'ZIP verified by Renulus' : 'Records-only JSON · checked locally'}</Badge></div>
          <dl className="data-archive-details"><div><dt>Exported</dt><dd><time dateTime={preview.exportedAt} title={preview.exportedAt}>{utc(preview.exportedAt)}</time></dd></div><div><dt>Contents</dt><dd>{quantity(preview.recordCount, 'record')}{preview.kind === 'zip' && <> · {quantity(preview.originalCount, 'original')} ({bytes(preview.originalBytes)})</>}</dd></div></dl>
          {preview.kind === 'json' && <p className="muted">This restores records only. Library attachment bytes are not included or recovered.</p>}
          <CatalogueOmission omissions={preview.omissions} copy />
          {preview.kind === 'zip' && <p className="muted">Preview expires: <time dateTime={preview.expiresAt}>{utc(preview.expiresAt)}</time></p>}
          <Notice tone="warning"><div className="data-copy"><strong>Deletion limits</strong><p>{deletionNotice}</p>{preview.notice !== deletionNotice && <p>{preview.notice}</p>}</div></Notice>
          <fieldset className="data-confirmations" disabled={!!busy}><legend>Confirm this restore</legend>
            <label><input type="checkbox" checked={reviewedDate} onChange={event => setReviewedDate(event.target.checked)} /><span>I reviewed the backup date: <strong>{utc(preview.exportedAt)}</strong>.</span></label>
            <label><input type="checkbox" checked={acknowledgedLimits} onChange={event => setAcknowledgedLimits(event.target.checked)} /><span>I understand and accept the deletion limits of this backup.</span></label>
          </fieldset>
        </div> : !checking && !restoreError && <p className="muted">No file selected. Restoring merges saved records; it preserves newer deletions known to this installation.</p>}
        <div className="actions"><Button variant="secondary" disabled={!canRestore} busy={busy === 'restore'} onClick={() => void restore()}>{busy === 'restore' ? 'Restoring…' : preview?.kind === 'json' ? 'Restore records only' : 'Restore full backup'}</Button>{fileName && <Button variant="ghost" disabled={!!busy} onClick={() => clearSelection()}>Cancel restore</Button>}</div>
      </section>
      <section className="data-recovery-status" aria-labelledby={id + '-recovery'}>
        <h3 id={id + '-recovery'}>Recovery status</h3>
        {refreshing && !recovery && <LoadingState label="Checking local recovery status" />}
        {!!recoveryError && <ErrorState title="Recovery status could not be checked" error={recoveryError} onRetry={() => void refreshRecovery()} />}
        {lastRestore && <div className="data-last-restore" role="status"><strong>Last restore{lastRestore.data_kind === 'records-only' ? ' · records only' : ''}</strong>{dated(lastRestore.exported_at) && <p>From <time dateTime={lastRestore.exported_at}>{utc(lastRestore.exported_at)}</time></p>}<p>{count(lastRestore.restored_records) && <>{quantity(lastRestore.restored_records, 'record')} merged</>}{lastRestore.data_kind !== 'records-only' && count(lastRestore.restored_originals) && <> · {quantity(lastRestore.restored_originals, 'original')} restored</>}</p><p className="muted">{count(lastRestore.excluded_by_deletion) && <>{quantity(lastRestore.excluded_by_deletion, 'record')} excluded by deletion. </>}{count(lastRestore.removed_by_deletion) && <>{quantity(lastRestore.removed_by_deletion, 'existing record')} removed by deletion. </>}{lastRestore.data_kind !== 'records-only' && count(lastRestore.excluded_originals) && <>{quantity(lastRestore.excluded_originals, 'original')} excluded.</>}</p></div>}
        {recovery && <div className="data-rebuild" aria-live="polite"><div className="data-status-heading"><strong>Local indexes</strong><Badge tone={tone(recovery.rebuild.status)}>{statusLabels[recovery.rebuild.status]}</Badge></div><p>{recovery.rebuild.message ?? statusMessages[recovery.rebuild.status]}</p>{recovery.rebuild.error_code && <p className="muted">Reference: {recovery.rebuild.error_code}</p>}{!!recoveryError && <p className="muted">Showing the last reported status.</p>}
          <ul className="data-module-status">{(['knowledge', 'memory'] as const).map(key => {
            const module = recovery.rebuild.modules[key];
            return <li key={key}>
              <div className="data-status-heading"><strong>{key === 'knowledge' ? 'Library search' : 'Learning memory'}</strong><Badge tone={tone(module?.status ?? '')}>{module ? statusLabels[module.status as RebuildStatus] ?? module.status.replaceAll('_', ' ').replaceAll('-', ' ') : 'Not reported'}</Badge></div>
              {module?.message && <p>{module.message}</p>}
              {module && count(module.rebuilt_records) && <p className="muted">{quantity(module.rebuilt_records, module.rebuilt_unit === 'passages' ? 'passage' : 'record')} rebuilt</p>}
              {module?.cleanup_pending && <p className="data-cleanup-pending">Cleanup is still pending for this module. Retry the local rebuild to check it.</p>}
              {module?.error_code && <p className="muted">Reference: {module.error_code}</p>}
            </li>;
          })}</ul>
        </div>}
        <div className="actions"><Button variant="secondary" disabled={!recovery || !!busy || recovery.rebuild.status === 'running' || (recovery.rebuild.status === 'idle' && !lastRestore)} busy={busy === 'rebuild'} onClick={() => void rebuild()}>{busy === 'rebuild' ? 'Starting rebuild…' : recovery && ['blocked', 'partial', 'failed'].includes(recovery.rebuild.status) ? 'Retry local rebuild' : 'Rebuild local indexes'}</Button><Button variant="ghost" disabled={refreshing || !!busy} onClick={() => void refreshRecovery()}><RefreshCw size={16} aria-hidden="true" />Refresh recovery status</Button></div>
        <CatalogueOmission omissions={recovery?.omissions} />
        <details className="data-limits"><summary>{recovery?.limits ? 'Local recovery limits and backup scope' : 'Recovery limits (engineering defaults)'}</summary><dl><div><dt>ZIP upload</dt><dd>{bytes(limits.archive_bytes)}</dd></div><div><dt>JSON upload</dt><dd>{bytes(limits.json_bytes)}</dd></div><div><dt>Each archive member</dt><dd>{bytes(limits.original_bytes)}</dd></div><div><dt>Expanded originals</dt><dd>{bytes(limits.total_original_bytes)}</dd></div><div><dt>Original files</dt><dd>{limits.originals.toLocaleString('en-GB')}</dd></div></dl></details>
      </section>
    </div>
  </section>;
}
