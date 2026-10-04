// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DataManagement } from './DataManagement';
import type { BackupSaveResult } from './desktop';

const archiveDate = '2026-10-04T10:24:00.123400+00:00';
const MiB = 1024 * 1024;
const omissions = { knowledge_catalogue: { records: 183891, reason: 'Acquisition catalogue is input metadata tied to external collection paths; retained library metadata remains in knowledge_documents and knowledge_revisions.' } };
const request = vi.fn<typeof fetch>();
const createObjectURL = vi.fn(() => 'blob:synthetic-download');
const revokeObjectURL = vi.fn();
const originalURL = URL;
function json(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }); }
function rebuildState(status = 'idle') { return { status, modules: { knowledge: { status }, memory: { status } } }; }
function recoveryState(status = 'idle') { return { last_restore: null as Record<string, unknown> | null, rebuild: rebuildState(status), limits: { archive_bytes: 288 * MiB, json_bytes: 16 * MiB, original_bytes: 64 * MiB, total_original_bytes: 256 * MiB, originals: 1000 }, omissions }; }
function zipPreview(overrides: Record<string, unknown> = {}) { return { preview_token: 'preview-token', exported_at: archiveDate, expires_at: new Date(Date.now() + 600_000).toISOString(), format: 'renulus-full-backup', record_count: 9, original_count: 2, original_bytes: 100, deletion_notice: 'This archive knows only the deletions available at export.', omissions, ...overrides }; }
function recordsBundle(overrides: Record<string, unknown> = {}) { return { format: 'renulus-canonical-export', format_version: 1, schema_version: 1, exported_at: archiveDate, records: { memory_facts: [{ id: 'synthetic-memory' }], knowledge_documents: [{ id: 'synthetic-ckd-document' }, { id: 'synthetic-dialysis-document' }] }, artifacts: {}, omissions, ...overrides }; }
function restored(zip = true) { return { restored_records: 7, ...(zip ? { restored_originals: 2, excluded_originals: 1 } : {}), excluded_by_deletion: 1, removed_by_deletion: 2, exported_at: archiveDate, indexes: 'rebuild-required', recovery_id: 'synthetic-recovery', rebuild: rebuildState('required') }; }
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason: unknown) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; }
function button(name: string | RegExp) { return screen.getByRole('button', { name }) as HTMLButtonElement; }
function selectedFile(file: File) { fireEvent.change(screen.getByLabelText('Choose ZIP backup or JSON export'), { target: { files: [file] } }); }
function zipFile(name = 'study-library.zip') { return new File(['SYNTHETIC_ZIP_BYTES'], name, { type: 'application/zip' }); }
function confirm() { fireEvent.click(screen.getByRole('checkbox', { name: /I reviewed the backup date/ })); fireEvent.click(screen.getByRole('checkbox', { name: /I understand and accept the deletion limits/ })); }
function calls(path: string) { return request.mock.calls.filter(([url]) => url === '/api/v1' + path); }
type SaveBackup = NonNullable<NonNullable<Window['renulus']>['saveBackup']>;
function installNative(save = vi.fn<SaveBackup>(), cancel = vi.fn<(id: string) => Promise<void>>().mockResolvedValue(undefined)) {
  window.renulus = { openAuthorization: vi.fn(), version: vi.fn(), saveBackup: save, cancelBackup: cancel };
  return { save, cancel };
}
function streamed(headers: Record<string, string> = {}) {
  let writer!: ReadableStreamDefaultController<Uint8Array>;
  const cancelled = vi.fn();
  const body = new ReadableStream<Uint8Array>({ start(controller) { writer = controller; }, cancel: cancelled });
  return { response: new Response(body, { headers: { 'Content-Type': 'application/zip', ...headers } }), writer, cancelled };
}
function reply(path: string, response: Response | Promise<Response>) {
  const original = request.getMockImplementation()!;
  request.mockImplementation((url, options) => url === '/api/v1' + path ? Promise.resolve(response) : original(url, options));
}
function noBrowserSave() {
  expect(calls('/data/backup')).toHaveLength(0); expect(calls('/data/export')).toHaveLength(0);
  expect(createObjectURL).not.toHaveBeenCalled(); expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
  expect(request.mock.calls.every(([url]) => url === '/api/v1/data/recovery')).toBe(true);
}
function advertiseSegmented(overrides: Record<string, unknown> = {}) {
  const formats = { '1': { ...recovery.limits }, '2': { ...recovery.limits, archive_bytes: 8 * 1024 * MiB, canonical_bytes: 2 * 1024 * MiB,
    records: 1_000_000, segments: 4096, row_bytes: 16 * MiB, segment_bytes: 32 * MiB, ...overrides } };
  Object.assign(recovery, { backup_formats: formats }); return formats;
}
let recovery: ReturnType<typeof recoveryState>;

beforeEach(() => {
  recovery = recoveryState();
  request.mockImplementation(async (url, options) => {
    if (url === '/api/v1/data/recovery') return json(recovery);
    if (url === '/api/v1/data/backup') return new Response('SYNTHETIC_ZIP_BYTES', { headers: { 'Content-Type': 'application/zip', 'Content-Disposition': 'attachment; filename="renulus-study.zip"' } });
    if (url === '/api/v1/data/export') return json(recordsBundle());
    if (url === '/api/v1/data/backup/preview' && options?.method === 'POST') return json(zipPreview());
    if (String(url).startsWith('/api/v1/data/backup/preview/') && options?.method === 'DELETE') return new Response(null, { status: 204 });
    if (url === '/api/v1/data/backup/restore' || url === '/api/v1/data/restore') { const result = restored(url === '/api/v1/data/backup/restore'); recovery = { ...recovery, last_restore: result, rebuild: result.rebuild }; return json(result); }
    if (url === '/api/v1/data/rebuild' && options?.method === 'POST') return json(rebuildState('blocked'));
    throw new Error('Unexpected synthetic request: ' + url);
  });
  vi.stubGlobal('fetch', request);
  vi.stubGlobal('URL', class extends originalURL { static createObjectURL = createObjectURL; static revokeObjectURL = revokeObjectURL; });
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
});
afterEach(() => { cleanup(); delete window.renulus; vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('DataManagement downloads and recovery scope', () => {
  it('starts ZIP and records-only JSON downloads through the authenticated same-origin transport', async () => {
    const view = render(<DataManagement />);
    await screen.findByText('A restore schedules a local rebuild after deletion checks.');
    expect(button('Restore full backup').disabled).toBe(true);
    fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText(/Full backup download started/);
    const zip = calls('/data/backup')[0][1]!;
    expect(zip.credentials).toBe('same-origin');
    expect((zip.headers as Headers).get('Accept')).toBe('application/zip');
    expect((zip.headers as Headers).has('Authorization')).toBe(false);
    fireEvent.click(button('Export records only (JSON)'));
    await screen.findByText(/Records-only JSON download started/);
    expect((calls('/data/export')[0][1]!.headers as Headers).get('Accept')).toBe('application/json');
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(2);
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    view.unmount();
    expect(revokeObjectURL).toHaveBeenCalled();
  });
  it('shows the catalogue omission count, reason and server limits without claiming a full profile capture', async () => {
    recovery.limits = { archive_bytes: 200 * MiB, json_bytes: 8 * MiB, original_bytes: 32 * MiB, total_original_bytes: 180 * MiB, originals: 500 };
    render(<DataManagement />);
    await screen.findByText(/ZIP up to 200 MiB; records-only JSON up to 8 MiB/);
    expect(screen.getAllByText('183,891 acquisition catalogue records excluded').length).toBe(2);
    expect(screen.getAllByText(omissions.knowledge_catalogue.reason).length).toBe(2);
    fireEvent.click(screen.getByText('Local recovery limits and backup scope'));
    expect(screen.getByText('32 MiB')).toBeTruthy();
    expect(screen.getByText('180 MiB')).toBeTruthy();
    expect(screen.getByText('500')).toBeTruthy();
    expect(screen.getByText(/This is not a full backup/)).toBeTruthy();
  });
  it('reports a failed download and leaves the action available for a deliberate retry', async () => {
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup' ? Promise.resolve(json({ detail: { code: 'backup_unavailable', message: 'A library original is missing. Restore the file before downloading a backup.' } }, 409)) : original(url, options));
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText('A library original is missing. Restore the file before downloading a backup.');
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
    expect(createObjectURL).not.toHaveBeenCalled();
  });
});

describe('Native backup save and cancellation', () => {
  it('saves ZIP and JSON with distinct v4 UUIDs and confirmed basenames/bytes without renderer downloads', async () => {
    advertiseSegmented();
    const blob = vi.spyOn(Response.prototype, 'blob');
    const { save, cancel } = installNative(vi.fn<SaveBackup>().mockImplementation(async kind => ({ status: 'saved', fileName: kind === 'zip' ? 'Renulus study.zip' : 'Renulus records.json', bytes: kind === 'zip' ? 2 * 1024 * MiB : 512 })));
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB/);
    fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText(/Full backup saved: Renulus study.zip/);
    fireEvent.click(button('Export records only (JSON)'));
    await screen.findByText(/Records-only JSON saved: Renulus records.json/);
    expect(screen.getByText(/Library originals are not included/)).toBeTruthy();
    expect(save.mock.calls.map(([kind]) => kind)).toEqual(['zip', 'json']);
    const ids = save.mock.calls.map(([, id]) => id);
    ids.forEach(id => expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i));
    expect(new Set(ids).size).toBe(2);
    expect(cancel).not.toHaveBeenCalled(); expect(blob).not.toHaveBeenCalled(); noBrowserSave();
  });
  it.each(['cancelled', 'error', 'rejected', 'aborted'] as const)('reports native %s without silently starting a browser download', async outcome => {
    const save = vi.fn<SaveBackup>();
    if (outcome === 'rejected') save.mockRejectedValue(new Error('C:\\private-synthetic\\native-error'));
    else if (outcome === 'aborted') save.mockRejectedValue(new DOMException('Synthetic IPC interruption', 'AbortError'));
    else if (outcome === 'error') save.mockResolvedValue({ status: 'error', code: 'backup_save_failed', message: 'Choose a folder with enough free space and try again.' });
    else save.mockResolvedValue({ status: 'cancelled' });
    installNative(save); render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText(outcome === 'cancelled' ? 'Backup save cancelled.' : outcome === 'error' ? 'Choose a folder with enough free space and try again.' : 'The backup save could not be confirmed. Check the selected folder before trying again.');
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
    expect(screen.queryByText(/private-synthetic/)).toBeNull();
    expect(screen.queryByText(/download started/)).toBeNull(); noBrowserSave();
  });
  it('refuses an incomplete native bridge instead of starting a save that cannot be cancelled', async () => {
    const { save } = installNative(); delete window.renulus!.cancelBackup;
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText('Native backup cancellation is unavailable. Restart Renulus before saving a backup.');
    expect(save).not.toHaveBeenCalled(); noBrowserSave();
  });
  it('rejects private-path save metadata without showing it or claiming a successful save', async () => {
    installNative(vi.fn<SaveBackup>().mockResolvedValue({ status: 'saved', fileName: 'C:\\private-synthetic\\study.zip', bytes: 123 }));
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText('Renulus could not confirm whether the file was saved. Check the selected folder before trying again.');
    expect(screen.queryByText(/private-synthetic/)).toBeNull(); expect(screen.queryByText(/Full backup saved/)).toBeNull(); noBrowserSave();
  });
  it('cancels the matching UUID once and waits for the terminal result before enabling another save', async () => {
    const waiting = deferred<BackupSaveResult>(); const { save, cancel } = installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise));
    const view = render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    fireEvent.click(button('Cancel download'));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith(save.mock.calls[0][1]));
    expect(button('Cancelling download…').disabled).toBe(true);
    expect(button('Export records only (JSON)').disabled).toBe(true);
    expect(screen.getByText(/close it to finish cancelling/)).toBeTruthy();
    fireEvent.click(button('Cancelling download…')); expect(cancel).toHaveBeenCalledTimes(1);
    waiting.resolve({ status: 'cancelled' }); await screen.findByText('Backup save cancelled.');
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
    view.unmount(); expect(cancel).toHaveBeenCalledTimes(1); noBrowserSave();
  });
  it('reports a completed save honestly when it wins a cancellation race', async () => {
    const waiting = deferred<BackupSaveResult>(); const cancellation = deferred<void>();
    const { cancel } = installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise), vi.fn<(id: string) => Promise<void>>().mockReturnValue(cancellation.promise));
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)')); fireEvent.click(button('Cancel download'));
    waiting.resolve({ status: 'saved', fileName: 'finished-study.zip', bytes: 77 });
    await screen.findByText(/Full backup saved: finished-study.zip \(77 bytes\)/);
    await act(async () => { cancellation.reject(new Error('late synthetic cancellation failure')); });
    expect(cancel).toHaveBeenCalledTimes(1); expect(screen.queryByText('Backup save cancelled.')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull(); noBrowserSave();
  });
  it('allows an explicit cancellation retry without ending the still-pending native save', async () => {
    const waiting = deferred<BackupSaveResult>();
    const { save, cancel } = installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise), vi.fn<(id: string) => Promise<void>>().mockRejectedValueOnce(new Error('synthetic IPC failure')).mockResolvedValue(undefined));
    render(<DataManagement />); fireEvent.click(button('Export records only (JSON)')); fireEvent.click(button('Cancel download'));
    await screen.findByText('Renulus could not request cancellation. Try Cancel download again, or close the save dialog.');
    expect(button('Download full backup (ZIP)').disabled).toBe(true);
    fireEvent.click(button('Cancel download'));
    await waitFor(() => expect(cancel).toHaveBeenCalledTimes(2));
    expect(cancel.mock.calls.map(([id]) => id)).toEqual([save.mock.calls[0][1], save.mock.calls[0][1]]);
    waiting.resolve({ status: 'cancelled' }); await screen.findByText('Backup save cancelled.');
    expect(screen.queryByRole('alert')).toBeNull(); noBrowserSave();
  });
  it('cancels on unmount using the captured bridge and ignores a late save and cancellation rejection', async () => {
    const waiting = deferred<BackupSaveResult>(); const cancellation = deferred<void>();
    const { save, cancel } = installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise), vi.fn<(id: string) => Promise<void>>().mockReturnValue(cancellation.promise));
    const view = render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    const replacement = installNative(); view.unmount();
    expect(cancel).toHaveBeenCalledWith(save.mock.calls[0][1]); expect(replacement.cancel).not.toHaveBeenCalled();
    render(<DataManagement />);
    await act(async () => { waiting.resolve({ status: 'saved', fileName: 'old-operation.zip', bytes: 11 }); cancellation.reject(new Error('late unmount cancellation')); });
    expect(screen.queryByText(/old-operation/)).toBeNull(); expect(button('Download full backup (ZIP)').disabled).toBe(false); noBrowserSave();
  });
  it('replaces an earlier cancellation error with the confirmed terminal save outcome', async () => {
    const waiting = deferred<BackupSaveResult>();
    installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise), vi.fn<(id: string) => Promise<void>>().mockRejectedValue(new Error('synthetic cancellation failure')));
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)')); fireEvent.click(button('Cancel download'));
    await screen.findByText('Renulus could not request cancellation. Try Cancel download again, or close the save dialog.');
    waiting.resolve({ status: 'saved', fileName: 'completed-study.zip', bytes: 101 });
    await screen.findByText(/Full backup saved: completed-study.zip/);
    expect(screen.queryByRole('alert')).toBeNull(); noBrowserSave();
  });
  it('keeps a native save cancellable beyond the former two-minute budget', async () => {
    vi.useFakeTimers(); const waiting = deferred<BackupSaveResult>();
    const { cancel } = installNative(vi.fn<SaveBackup>().mockReturnValue(waiting.promise));
    await act(async () => { render(<DataManagement />); });
    await act(async () => { fireEvent.click(button('Download full backup (ZIP)')); await vi.advanceTimersByTimeAsync(121_000); });
    expect(button('Cancel download').disabled).toBe(false); expect(cancel).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(button('Cancel download')); waiting.resolve({ status: 'cancelled' }); });
    expect(screen.getByText('Backup save cancelled.')).toBeTruthy(); noBrowserSave();
  });
});

describe('Bounded browser backup streaming', () => {
  it('cancels a response body after headers without allocating or dispatching a download', async () => {
    const stream = streamed(); reply('/data/backup', stream.response);
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await waitFor(() => expect(stream.response.body?.locked).toBe(true));
    stream.writer.enqueue(new Uint8Array([1, 2])); fireEvent.click(button('Cancel download'));
    await screen.findByText('Download cancelled. You can start another download.');
    expect(stream.cancelled).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(button('Export records only (JSON)')); await screen.findByText(/Records-only JSON download started/);
    expect(createObjectURL).toHaveBeenCalledTimes(1);
  });
  it('does not let a cancelled late response replace a newer completed download', async () => {
    const late = deferred<Response>(); reply('/data/backup', late.promise);
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)')); fireEvent.click(button('Cancel download'));
    expect((calls('/data/backup')[0][1]!.signal as AbortSignal).aborted).toBe(true);
    fireEvent.click(button('Export records only (JSON)')); await screen.findByText(/Records-only JSON download started/);
    const stream = streamed(); await act(async () => { late.resolve(stream.response); });
    expect(stream.cancelled).toHaveBeenCalledTimes(1);
    expect(createObjectURL).toHaveBeenCalledTimes(1); expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Full backup download started/)).toBeNull();
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
  });
  it.each([undefined, '2'])('counts actual chunks and cancels an oversized body despite Content-Length %s', async length => {
    recovery.limits.archive_bytes = 4;
    const stream = streamed(length ? { 'Content-Length': length } : {}); reply('/data/backup', stream.response);
    render(<DataManagement />); await screen.findByText(/ZIP up to 4 bytes/); fireEvent.click(button('Download full backup (ZIP)'));
    stream.writer.enqueue(new Uint8Array([1, 2, 3])); stream.writer.enqueue(new Uint8Array([4, 5, 6]));
    await screen.findByText(/exceeds the browser download limit of 4 bytes/);
    expect(stream.cancelled).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled();
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
  });
  it('rejects a declared oversized archive before reading and clamps expanded native limits to the browser ceiling', async () => {
    advertiseSegmented();
    const stream = streamed({ 'Content-Length': String(288 * MiB + 1) }); reply('/data/backup?format_version=2', stream.response);
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB/); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText(/exceeds the browser download limit of 288 MiB/);
    expect(stream.cancelled).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled();
  });
  it('rejects a truncated transfer without calling blob or dispatching a file', async () => {
    const blob = vi.spyOn(Response.prototype, 'blob');
    reply('/data/backup', new Response(new Uint8Array([1, 2]), { headers: { 'Content-Type': 'application/zip', 'Content-Length': '3' } }));
    render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await screen.findByText('The backup transfer did not finish. Try the download again.');
    expect(blob).not.toHaveBeenCalled(); expect(createObjectURL).not.toHaveBeenCalled();
  });
  it('bounds stalled body reads to thirty minutes, including time after response headers', async () => {
    vi.useFakeTimers(); const stream = streamed(); reply('/data/backup', stream.response);
    await act(async () => { render(<DataManagement />); });
    await act(async () => { fireEvent.click(button('Download full backup (ZIP)')); });
    await act(async () => { await vi.advanceTimersByTimeAsync(121_000); });
    expect(button('Cancel download').disabled).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(30 * 60 * 1000 - 121_000 + 1); });
    expect(screen.getByText('The backup download took longer than 30 minutes and was stopped. Try again.')).toBeTruthy();
    expect(stream.cancelled).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled();
    expect(button('Download full backup (ZIP)').disabled).toBe(false);
  });
  it('cancels a browser body on unmount and ignores its completion', async () => {
    const stream = streamed(); reply('/data/backup', stream.response);
    const view = render(<DataManagement />); fireEvent.click(button('Download full backup (ZIP)'));
    await waitFor(() => expect(stream.response.body?.locked).toBe(true));
    view.unmount(); await act(async () => {});
    expect(stream.cancelled).toHaveBeenCalledTimes(1); expect(createObjectURL).not.toHaveBeenCalled(); expect(HTMLAnchorElement.prototype.click).not.toHaveBeenCalled();
  });
});

describe('Advertised full-backup routes and limits', () => {
  it.each([1, 2])('uploads the original ZIP File through the advertised route and restores validated archive version %s', async version => {
    advertiseSegmented(); reply('/data/backup/preview?format_version=2', json(zipPreview({ format_version: version })));
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB; records-only JSON up to 16 MiB/);
    const file = zipFile(); if (version === 2) Object.defineProperty(file, 'size', { value: 300 * MiB });
    selectedFile(file); await screen.findByText('ZIP verified by Renulus');
    const upload = calls('/data/backup/preview?format_version=2')[0][1]!;
    expect(upload.body).toBe(file); expect((upload.headers as Headers).get('Content-Type')).toBe('application/zip');
    expect(calls('/data/backup/preview')).toHaveLength(0);
    confirm(); fireEvent.click(button('Restore full backup')); await screen.findByText('7 records merged · 2 originals restored');
    expect(JSON.parse(calls('/data/backup/restore')[0][1]!.body as string)).toEqual({ preview_token: 'preview-token', confirmed_exported_at: archiveDate, acknowledge_deletion_limits: true });
    expect(screen.queryByText(/segmented|format_version/)).toBeNull();
  });
  it('uses the advertised ZIP producer while records-only JSON keeps its existing route', async () => {
    advertiseSegmented(); reply('/data/backup?format_version=2', new Response('SYNTHETIC_ZIP_BYTES', { headers: { 'Content-Type': 'application/zip' } }));
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB/);
    fireEvent.click(button('Download full backup (ZIP)')); await screen.findByText(/Full backup download started/);
    expect(calls('/data/backup?format_version=2')).toHaveLength(1); expect(calls('/data/backup')).toHaveLength(0);
    fireEvent.click(button('Export records only (JSON)')); await screen.findByText(/Records-only JSON download started/);
    expect(calls('/data/export')).toHaveLength(1); expect(calls('/data/export?format_version=2')).toHaveLength(0);
  });
  it('shows a failed advertised producer without retrying through the legacy route', async () => {
    advertiseSegmented(); reply('/data/backup?format_version=2', json({ error: { code: 'backup_original_missing', message: 'An original is missing. Check the library before downloading this backup.' } }, 409));
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB/);
    fireEvent.click(button('Download full backup (ZIP)')); await screen.findByText('An original is missing. Check the library before downloading this backup.');
    expect(calls('/data/backup?format_version=2')).toHaveLength(1); expect(calls('/data/backup')).toHaveLength(0); expect(createObjectURL).not.toHaveBeenCalled();
  });
  it.each([{ segments: 0 }, { row_bytes: 32 * MiB }, { canonical_bytes: undefined }])('rejects unsupported advertised limits %j before selecting larger-archive routes', async overrides => {
    advertiseSegmented(overrides); render(<DataManagement />);
    await screen.findByText('The local runtime reported unsupported full-backup limits. Refresh recovery status before choosing a larger ZIP.');
    fireEvent.click(button('Download full backup (ZIP)')); await screen.findByText(/Full backup download started/);
    expect(calls('/data/backup?format_version=2')).toHaveLength(0); expect(calls('/data/backup')).toHaveLength(1);
    const file = zipFile(); Object.defineProperty(file, 'size', { value: 300 * MiB }); selectedFile(file);
    await screen.findByText(/exceeds the local ZIP limit of 288 MiB/);
    expect(calls('/data/backup/preview?format_version=2')).toHaveLength(0); expect(calls('/data/backup/preview')).toHaveLength(0);
  });
  it('keeps JSON upload bounded by legacy limits even when the full-backup limits report a larger JSON budget', async () => {
    advertiseSegmented({ json_bytes: 32 * MiB }); render(<DataManagement />);
    await screen.findByText(/ZIP up to 8,192 MiB; records-only JSON up to 16 MiB/);
    const file = new File([JSON.stringify(recordsBundle())], 'synthetic-records.json', { type: 'application/json' }); Object.defineProperty(file, 'size', { value: 17 * MiB });
    selectedFile(file); await screen.findByText(/exceeds the local JSON limit of 16 MiB/);
    expect(calls('/data/restore')).toHaveLength(0); expect(calls('/data/backup/preview?format_version=2')).toHaveLength(0);
  });
  it('preserves the advertised full-backup mode across a module rebuild result', async () => {
    recovery = recoveryState('required'); advertiseSegmented();
    reply('/data/backup?format_version=2', new Response('SYNTHETIC_ZIP_BYTES', { headers: { 'Content-Type': 'application/zip' } }));
    render(<DataManagement />); await screen.findByText(/ZIP up to 8,192 MiB/);
    fireEvent.click(button('Rebuild local indexes'));
    await screen.findByText('Local helpers are unavailable. Review the messages below, then retry when they are available.');
    fireEvent.click(button('Download full backup (ZIP)')); await screen.findByText(/Full backup download started/);
    expect(calls('/data/backup?format_version=2')).toHaveLength(1); expect(calls('/data/backup')).toHaveLength(0);
  });
});

describe('ZIP validation and deliberate restore permission', () => {
  it.each([undefined, 1, 2])('preserves the exact reviewed date and restore permission for ZIP format %s with additive limits', async version => {
    Object.assign(recovery.limits, { manifest_bytes: MiB });
    if (version === 2) advertiseSegmented();
    const path = version === 2 ? '/data/backup/preview?format_version=2' : '/data/backup/preview'; reply(path, json(zipPreview({ format_version: version })));
    render(<DataManagement />); await screen.findByText(version === 2 ? /ZIP up to 8,192 MiB/ : /ZIP up to/); const file = zipFile(); selectedFile(file);
    await screen.findByText('ZIP verified by Renulus'); confirm(); fireEvent.click(button('Restore full backup'));
    await screen.findByText('7 records merged · 2 originals restored');
    expect(calls(path)[0][1]?.body).toBe(file);
    expect(JSON.parse(calls('/data/backup/restore')[0][1]!.body as string)).toEqual({ preview_token: 'preview-token', confirmed_exported_at: archiveDate, acknowledge_deletion_limits: true });
  });
  it('allows a long ZIP preview and restore without timing out after two minutes', async () => {
    vi.useFakeTimers(); const previewResponse = deferred<Response>(); const restoreResponse = deferred<Response>();
    advertiseSegmented(); reply('/data/backup/preview?format_version=2', previewResponse.promise); reply('/data/backup/restore', restoreResponse.promise);
    await act(async () => { render(<DataManagement />); });
    await act(async () => { selectedFile(zipFile()); await vi.advanceTimersByTimeAsync(121_000); });
    expect((calls('/data/backup/preview?format_version=2')[0][1]!.signal as AbortSignal).aborted).toBe(false);
    expect(screen.queryByRole('checkbox')).toBeNull();
    await act(async () => { previewResponse.resolve(json(zipPreview({ format_version: 2 }))); });
    expect(screen.getByText('ZIP verified by Renulus')).toBeTruthy(); confirm();
    await act(async () => { fireEvent.click(button('Restore full backup')); await vi.advanceTimersByTimeAsync(121_000); });
    expect((calls('/data/backup/restore')[0][1]!.signal as AbortSignal).aborted).toBe(false);
    expect(button('Restoring…').disabled).toBe(true);
    await act(async () => { const result = restored(); recovery = { ...recovery, last_restore: result, rebuild: result.rebuild }; restoreResponse.resolve(json(result)); });
    expect(screen.getByText('7 records merged · 2 originals restored')).toBeTruthy();
  });
  it('uploads raw ZIP bytes, waits for server validation and requires both confirmations before restoring the exact date', async () => {
    const waiting = deferred<Response>(); const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? waiting.promise : original(url, options));
    render(<DataManagement />); const file = zipFile(); selectedFile(file);
    await waitFor(() => expect(calls('/data/backup/preview')).toHaveLength(1));
    const upload = calls('/data/backup/preview')[0][1]!;
    expect(upload.body).toBe(file);
    expect((upload.headers as Headers).get('Content-Type')).toBe('application/zip');
    expect(upload.credentials).toBe('same-origin');
    fireEvent.click(button('Restore full backup'));
    expect(calls('/data/backup/restore')).toHaveLength(0);
    expect(screen.queryByRole('checkbox')).toBeNull();
    waiting.resolve(json(zipPreview()));
    await screen.findByText('ZIP verified by Renulus');
    expect(screen.getByText('9 records · 2 originals (100 bytes)')).toBeTruthy();
    expect(screen.getAllByText('183,891 acquisition catalogue records excluded').length).toBe(3);
    expect(screen.getByText(/4 Oct 2026, 10:24:00 UTC/, { selector: 'time' })).toBeTruthy();
    fireEvent.click(screen.getByRole('checkbox', { name: /I reviewed the backup date/ }));
    expect(button('Restore full backup').disabled).toBe(true);
    fireEvent.click(screen.getByRole('checkbox', { name: /I understand and accept the deletion limits/ }));
    fireEvent.click(button('Restore full backup'));
    await screen.findByText('7 records merged · 2 originals restored');
    expect(JSON.parse(calls('/data/backup/restore')[0][1]!.body as string)).toEqual({ preview_token: 'preview-token', confirmed_exported_at: archiveDate, acknowledge_deletion_limits: true });
    expect(screen.getByText(/1 record excluded by deletion/)).toBeTruthy();
    expect(screen.getByText(/2 existing records removed by deletion/)).toBeTruthy();
    expect(screen.getByText(/1 original excluded/)).toBeTruthy();
    expect(screen.queryByText('Complete')).toBeNull();
    expect(calls('/data/rebuild')).toHaveLength(0);
    expect(calls('/data/restore')).toHaveLength(0);
  });
  it('clears old permission and discards the staged preview when another file is selected', async () => {
    const original = request.getMockImplementation()!; let previews = 0;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? Promise.resolve(json(zipPreview({ preview_token: 'preview-' + (++previews) }))) : original(url, options));
    render(<DataManagement />); selectedFile(zipFile('older.zip'));
    await screen.findByText('ZIP verified by Renulus'); confirm();
    expect(button('Restore full backup').disabled).toBe(false);
    selectedFile(zipFile('newer.zip'));
    expect(button('Restore full backup').disabled).toBe(true);
    await screen.findByText('ZIP verified by Renulus');
    expect((screen.getByRole('checkbox', { name: /I reviewed/ }) as HTMLInputElement).checked).toBe(false);
    expect((screen.getByRole('checkbox', { name: /I understand/ }) as HTMLInputElement).checked).toBe(false);
    expect(calls('/data/backup/preview/preview-1')[0][1]?.method).toBe('DELETE');
    expect(calls('/data/backup/restore')).toHaveLength(0);
  });
  it('ignores and discards a delayed old preview so it cannot replace a newer selection', async () => {
    const waiting = deferred<Response>(); const original = request.getMockImplementation()!; let previews = 0;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? (++previews === 1 ? waiting.promise : Promise.resolve(json(zipPreview({ preview_token: 'new-preview', exported_at: '2026-10-03T18:00:00Z' })))) : original(url, options));
    render(<DataManagement />); selectedFile(zipFile('old.zip')); selectedFile(zipFile('new.zip'));
    await screen.findByText('ZIP verified by Renulus');
    await act(async () => { waiting.resolve(json(zipPreview({ preview_token: 'old-preview' }))); });
    expect((calls('/data/backup/preview')[0][1]!.signal as AbortSignal).aborted).toBe(true);
    expect(screen.getByText('new.zip')).toBeTruthy();
    expect(screen.queryByText('old.zip')).toBeNull();
    expect(screen.getByText('3 Oct 2026, 18:00:00 UTC', { selector: 'time' })).toBeTruthy();
    expect(calls('/data/backup/preview/old-preview')[0][1]?.method).toBe('DELETE');
    confirm(); fireEvent.click(button('Restore full backup'));
    await waitFor(() => expect(calls('/data/backup/restore')).toHaveLength(1));
    expect(JSON.parse(calls('/data/backup/restore')[0][1]!.body as string).preview_token).toBe('new-preview');
  });
  it.each(['cancel', 'unmount'])('discards a verified staged preview on %s', async action => {
    const view = render(<DataManagement />); selectedFile(zipFile()); await screen.findByText('ZIP verified by Renulus');
    if (action === 'cancel') { confirm(); fireEvent.click(button('Cancel restore')); expect(button('Restore full backup').disabled).toBe(true); expect(screen.queryByRole('checkbox')).toBeNull(); }
    view.unmount();
    await waitFor(() => expect(calls('/data/backup/preview/preview-token')).toHaveLength(1));
    expect(calls('/data/backup/preview/preview-token')[0][1]).toMatchObject({ method: 'DELETE', keepalive: true });
  });
  it('clears permission immediately on cancel even if a pending upload returns later', async () => {
    const waiting = deferred<Response>(); const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? waiting.promise : original(url, options));
    render(<DataManagement />); selectedFile(zipFile()); fireEvent.click(button('Cancel restore'));
    await act(async () => { waiting.resolve(json(zipPreview())); });
    expect(screen.queryByText('ZIP verified by Renulus')).toBeNull();
    expect(button('Restore full backup').disabled).toBe(true);
    expect(calls('/data/backup/preview/preview-token')).toHaveLength(1);
  });
  it.each(['missing token', 'expired', 'server failure'])('does not permit restore after a %s preview', async failure => {
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? Promise.resolve(failure === 'server failure'
      ? json({ detail: { code: 'invalid_zip', message: 'The archive failed validation. Choose another backup.' } }, 400)
      : json(zipPreview(failure === 'missing token' ? { preview_token: null } : { expires_at: '2026-01-01T00:00:00Z' }))) : original(url, options));
    render(<DataManagement />); selectedFile(zipFile()); await screen.findByRole('alert');
    expect(button('Restore full backup').disabled).toBe(true);
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(calls('/data/backup/restore')).toHaveLength(0);
  });
  it('expires a previously confirmed preview instead of retaining restore permission', async () => {
    vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-04T20:00:00Z'));
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/preview' ? Promise.resolve(json(zipPreview({ expires_at: '2026-10-04T20:00:01Z' }))) : original(url, options));
    await act(async () => { render(<DataManagement />); });
    await act(async () => { selectedFile(zipFile()); }); confirm();
    expect(button('Restore full backup').disabled).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(1001); });
    expect(button('Restore full backup').disabled).toBe(true);
    expect(screen.getByText(/This ZIP preview has expired/)).toBeTruthy();
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(calls('/data/backup/restore')).toHaveLength(0);
  });
  it('invalidates permission after a restore failure and refreshes recovery instead of automatically resubmitting', async () => {
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/backup/restore' ? Promise.resolve(json({ detail: { code: 'preview_expired', message: 'The staged preview expired. Select the backup again.' } }, 409)) : original(url, options));
    render(<DataManagement />); selectedFile(zipFile()); await screen.findByText('ZIP verified by Renulus'); confirm(); fireEvent.click(button('Restore full backup'));
    await screen.findByText('The staged preview expired. Select the backup again.');
    expect(button('Restore full backup').disabled).toBe(true);
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(calls('/data/backup/restore')).toHaveLength(1);
    await waitFor(() => expect(calls('/data/recovery').length).toBeGreaterThan(1));
  });
});

describe('Records-only JSON recovery', () => {
  it.each([undefined, {}])('excludes legacy catalogue rows from the preview, derives missing omissions (%j), and restores the original bundle', async missingOmissions => {
    const retained = recordsBundle().records;
    const catalogue = Array.from({ length: 5 }, (_, index) => ({ id: 'synthetic-acquisition-' + index }));
    const bundle = JSON.parse(JSON.stringify(recordsBundle({ records: { ...retained, knowledge_catalogue: catalogue }, omissions: missingOmissions })));
    render(<DataManagement />); selectedFile(new File([JSON.stringify(bundle)], 'legacy-records.json', { type: 'application/json' }));
    await screen.findByText('Records-only JSON · checked locally');
    expect(screen.getByText('3 records')).toBeTruthy();
    expect(screen.queryByText('8 records')).toBeNull();
    expect(screen.getByText('5 acquisition catalogue records excluded')).toBeTruthy();
    expect(screen.queryByText('This copy does not report an omission count.')).toBeNull();
    expect(calls('/data/backup/preview')).toHaveLength(0);
    confirm(); fireEvent.click(button('Restore records only'));
    await screen.findByText('7 records merged');
    const sent = JSON.parse(calls('/data/restore')[0][1]!.body as string);
    expect(sent).toEqual({ bundle, confirm_backup_date: true, confirmed_exported_at: archiveDate });
    expect(sent.bundle.records.knowledge_catalogue).toEqual(catalogue);
    expect(sent.bundle.omissions).toEqual(bundle.omissions);
  });
  it('previews JSON locally, distinguishes omitted originals and posts the original bundle and exact reviewed date', async () => {
    const bundle = recordsBundle({ omissions: { knowledge_catalogue: { records: 70000, reason: omissions.knowledge_catalogue.reason } } });
    render(<DataManagement />); selectedFile(new File([JSON.stringify(bundle)], 'study-records.json', { type: 'application/json' }));
    await screen.findByText('Records-only JSON · checked locally');
    expect(screen.getByText('3 records')).toBeTruthy();
    expect(screen.getByText('70,000 acquisition catalogue records excluded')).toBeTruthy();
    expect(screen.getByText(/Library attachment bytes are not included or recovered/)).toBeTruthy();
    expect(calls('/data/backup/preview')).toHaveLength(0);
    expect(button('Restore records only').disabled).toBe(true);
    confirm(); fireEvent.click(button('Restore records only'));
    await screen.findByText('7 records merged');
    expect(JSON.parse(calls('/data/restore')[0][1]!.body as string)).toEqual({ bundle, confirm_backup_date: true, confirmed_exported_at: archiveDate });
    expect(calls('/data/backup/restore')).toHaveLength(0);
    expect(screen.queryByText(/originals restored/)).toBeNull();
  });
  it.each(['{invalid JSON', JSON.stringify(recordsBundle({ exported_at: 'not a date' }))])('rejects invalid JSON/date content without granting permission: %s', async contents => {
    render(<DataManagement />); selectedFile(new File([contents], 'broken.json', { type: 'application/json' }));
    await screen.findByRole('alert');
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(button('Restore full backup').disabled).toBe(true);
    expect(calls('/data/restore')).toHaveLength(0);
  });
  it.each([{ name: 'large.zip', size: 288 * MiB + 1, limit: '288 MiB' }, { name: 'large.json', size: 16 * MiB + 1, limit: '16 MiB' }])('bounds $name before reading or uploading it', async ({ name, size, limit }) => {
    render(<DataManagement />); const file = new File(['SYNTHETIC'], name); Object.defineProperty(file, 'size', { value: size }); selectedFile(file);
    await screen.findByText(new RegExp('exceeds the local .* limit of ' + limit));
    expect(screen.queryByRole('checkbox')).toBeNull();
    expect(calls('/data/backup/preview')).toHaveLength(0);
    expect(calls('/data/restore')).toHaveLength(0);
  });
});

describe('Honest rebuild status and polling', () => {
  it('labels library passages and memory records separately and reports partial cleanup without claiming an index failure', async () => {
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/recovery' ? Promise.resolve(json({ ...recovery, last_restore: restored(), rebuild: { status: 'partial', modules: {
      knowledge: { status: 'partial', rebuilt_records: 12, rebuilt_unit: 'passages', cleanup_pending: true },
      memory: { status: 'complete', rebuilt_records: 2, rebuilt_unit: 'records', cleanup_pending: false },
    } } })) : original(url, options));
    render(<DataManagement />); await screen.findByText('12 passages rebuilt');
    const library = within(screen.getByText('Library search').closest('li')!);
    const memory = within(screen.getByText('Learning memory').closest('li')!);
    expect(library.getByText('12 passages rebuilt')).toBeTruthy();
    expect(library.getByText('Partial')).toBeTruthy();
    expect(library.getByText('Cleanup is still pending for this module. Retry the local rebuild to check it.')).toBeTruthy();
    expect(memory.getByText('2 records rebuilt')).toBeTruthy();
    expect(memory.getByText('Complete')).toBeTruthy();
    expect(memory.queryByText(/Cleanup is still pending/)).toBeNull();
    expect(screen.queryByText('12 records rebuilt')).toBeNull();
    expect(screen.queryByText(/Some indexes could not be rebuilt/)).toBeNull();
    expect(button('Retry local rebuild').disabled).toBe(false);
  });
  it('accepts an idle backend with no module results and disables rebuild until a restore exists', async () => {
    const original = request.getMockImplementation()!;
    const scope = 'Retained learning records and app-owned originals only; external originals and managed helper weights are excluded.';
    request.mockImplementation((url, options) => url === '/api/v1/data/recovery' ? Promise.resolve(json({ ...recovery, rebuild: { status: 'idle', modules: {} }, backup_scope: scope })) : original(url, options));
    render(<DataManagement />); await screen.findByText('Not rebuilding');
    expect(screen.getAllByText('Not reported')).toHaveLength(2);
    expect(screen.getByText(scope + ' Indexes are rebuilt locally after a restore.')).toBeTruthy();
    expect(button('Rebuild local indexes').disabled).toBe(true);
    expect(screen.getAllByText('183,891 acquisition catalogue records excluded')).toHaveLength(2);
    expect(screen.queryByRole('alert')).toBeNull();
  });
  it('keeps an interrupted aggregate rebuild failure recoverable when module results are absent', async () => {
    const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => url === '/api/v1/data/recovery' ? Promise.resolve(json({ ...recovery, last_restore: restored(), rebuild: { status: 'blocked', modules: {}, error_code: 'rebuild_interrupted', message: 'The local rebuild was interrupted. Retry it to check the indexes.' } })) : original(url, options));
    render(<DataManagement />); await screen.findByText('The local rebuild was interrupted. Retry it to check the indexes.');
    expect(screen.getAllByText('Not reported')).toHaveLength(2);
    expect(button('Retry local rebuild').disabled).toBe(false);
    expect(screen.getByText('Reference: rebuild_interrupted')).toBeTruthy();
    expect(screen.queryByText('Complete')).toBeNull();
  });
  it('shows missing local helpers and explicit retry, polls a running rebuild, then stops at the reported completion', async () => {
    vi.useFakeTimers();
    let reads = 0; const original = request.getMockImplementation()!;
    request.mockImplementation((url, options) => {
      if (url === '/api/v1/data/recovery') { ++reads; const result = recoveryState(reads === 1 ? 'blocked' : reads === 2 ? 'running' : 'complete'); if (reads === 1) Object.assign(result.rebuild.modules.knowledge, { error_code: 'helpers_missing', message: 'The bundled embedding helper is missing.' }); return Promise.resolve(json(result)); }
      if (url === '/api/v1/data/rebuild') return Promise.resolve(json(rebuildState('running')));
      return original(url, options);
    });
    const view = await act(async () => render(<DataManagement />));
    expect(screen.getByText('The bundled embedding helper is missing.')).toBeTruthy();
    expect(screen.getByText('Reference: helpers_missing')).toBeTruthy();
    expect(screen.queryByText('Complete')).toBeNull();
    await act(async () => { fireEvent.click(button('Retry local rebuild')); });
    expect(calls('/data/rebuild')[0][1]?.method).toBe('POST');
    expect(button('Rebuild local indexes').disabled).toBe(true);
    expect(screen.getAllByText('Rebuilding')).toHaveLength(3);
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
    expect(screen.getAllByText('Complete')).toHaveLength(3);
    expect(reads).toBe(3);
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(reads).toBe(3);
    view.unmount();
  });
  it('loads an in-progress recovery and cancels its scheduled poll on unmount', async () => {
    vi.useFakeTimers(); recovery = recoveryState('running');
    const view = await act(async () => render(<DataManagement />));
    expect(screen.getAllByText('Rebuilding')).toHaveLength(3);
    view.unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(calls('/data/recovery')).toHaveLength(1);
  });
  it('reports an unavailable recovery API and allows a status retry without inventing successful indexes', async () => {
    const original = request.getMockImplementation()!; let fail = true;
    request.mockImplementation((url, options) => url === '/api/v1/data/recovery' && fail ? Promise.resolve(json({ detail: { code: 'unavailable', message: 'The local recovery runtime is unavailable. Try again.' } }, 503)) : original(url, options));
    render(<DataManagement />); await screen.findByText('The local recovery runtime is unavailable. Try again.');
    expect(button('Rebuild local indexes').disabled).toBe(true);
    expect(screen.queryByText('Complete')).toBeNull();
    fail = false; fireEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Try again' }));
    await screen.findByText('A restore schedules a local rebuild after deletion checks.');
    expect(button('Rebuild local indexes').disabled).toBe(true);
  });
});
