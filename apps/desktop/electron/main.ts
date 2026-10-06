import { app, BrowserWindow, dialog, ipcMain, session, shell, type IpcMainInvokeEvent } from 'electron';
import { ownedApiHeaders } from './owned-api-headers';
import { randomBytes } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { allowedAuthorizationUrl, allowedSourceUrl, resolveProfile, type DesktopProfile } from './profile';
import { startBackend, type ManagedBackend } from './backend';
import { startFrontend } from './frontend';
import { createStartupWindow } from './startup-window';
import { isBuiltinPdfResource } from './pdf-resources';
import { BackupDownloadError, downloadBackup, validBackupOperation, type BackupSaveResult } from './backup-download';
import { activateWindow, ensureMainWindow } from './upstream/main-window-lifecycle';

app.setName('Renulus');
const workspace = path.resolve(__dirname, '../../..');
// Opt-in automation owns a separate profile and never uses desktop input.
const backgroundTest = process.env.RENULUS_BACKGROUND_TEST === '1';
function recordTestEvent(kind: string, details: Record<string, string> = {}) {
  process.stderr.write('RENULUS_BACKGROUND_EVENT ' + JSON.stringify({ kind, ...details, at: new Date().toISOString() }) + '\n');
}
function reportNativeError(title: string, message: string) {
  if (backgroundTest) recordTestEvent('error', { title, message });
  else dialog.showErrorBox(title, message);
}
async function openExternal(url: string, target: 'source' | 'authorization') {
  if (backgroundTest) {
    // Authorization URLs can contain account-specific state. Never log them.
    const source = new URL(url);
    recordTestEvent('external-blocked', { target, ...(target === 'source' ? { url: source.origin + source.pathname } : {}) });
    throw new Error('External windows are disabled in Renulus background tests.');
  }
  await shell.openExternal(url);
}
let profile: DesktopProfile;
try {
  if (backgroundTest && (!process.env.RENULUS_PROFILE || !path.isAbsolute(process.env.RENULUS_PROFILE))) throw new Error('Background tests require an explicit absolute synthetic RENULUS_PROFILE.');
  if (backgroundTest && process.env.RENULUS_BACKEND_URL) throw new Error('Background tests must launch their own managed backend.');
  profile = resolveProfile(process.env.RENULUS_PROFILE, app.isPackaged, process.env.LOCALAPPDATA);
}
catch (error) { reportNativeError('Renulus could not start', (error as Error).message); app.exit(1); throw error; }
mkdirSync(profile.desktop, { recursive: true }); mkdirSync(profile.session, { recursive: true });
app.setPath('userData', profile.desktop); app.setPath('sessionData', profile.session);
app.setAppUserModelId('org.renulus.desktop.' + (app.isPackaged ? 'app' : 'dev.' + profile.instance));
const ownsInstance = app.requestSingleInstanceLock({ instance: profile.instance });
if (!ownsInstance) app.exit(0);
if (backgroundTest) app.on('browser-window-created', (_event, owner) => {
  recordTestEvent('window-created');
  owner.on('show', () => recordTestEvent('window-shown'));
  owner.on('focus', () => recordTestEvent('window-focused'));
});
let window: BrowserWindow | null = null;
let openingWindow: BrowserWindow | null = null;
let backend: ManagedBackend | undefined;
let frontend: Awaited<ReturnType<typeof startFrontend>> | undefined;
const lifetime = new AbortController();
const backupDownloads = new Map<string, AbortController>();
const token = !app.isPackaged && process.env.RENULUS_BACKEND_URL && process.env.RENULUS_SESSION_TOKEN ? process.env.RENULUS_SESSION_TOKEN : randomBytes(32).toString('hex');
let stopping = false;
let stopPromise: Promise<void> | undefined;

function createWindow() {
  if (!frontend) return;
  const isolated = session.fromPartition('renulus-' + profile.instance); // No persist: prefix.
  window = new BrowserWindow({ title: app.isPackaged ? 'Renulus' : 'Renulus — Development', width: 1400, height: 960, minWidth: 640, minHeight: 540, show: false, focusable: !backgroundTest, skipTaskbar: backgroundTest, backgroundColor: '#faf9f6', icon: path.join(__dirname, '../dist/renulus.ico'), autoHideMenuBar: true, webPreferences: { preload: path.join(__dirname, 'preload.cjs'), session: isolated, nodeIntegration: false, contextIsolation: true, sandbox: true, webSecurity: true, v8CacheOptions: 'none', spellcheck: false, backgroundThrottling: !backgroundTest } });
  const owner = window;
  const origin = frontend.origin;
  isolated.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  isolated.setPermissionCheckHandler(() => false);
  isolated.webRequest.onBeforeRequest((details, callback) => {
    const local = details.url.startsWith(origin + '/') || details.url === origin;
    callback({ cancel: !local && !details.url.startsWith('data:') && !details.url.startsWith('blob:') && !isBuiltinPdfResource(details.url) });
  });
  isolated.webRequest.onBeforeSendHeaders({ urls: [origin + '/api/v1/*'] }, ownedApiHeaders(owner, token));
  owner.webContents.setWindowOpenHandler(({ url }) => {
    if (allowedSourceUrl(url)) void openExternal(url, 'source').catch(() => {
      if (!backgroundTest) reportNativeError('The source could not open', 'Try the source link again after checking your default browser.');
    });
    return { action: 'deny' };
  });
  owner.webContents.on('will-navigate', (event, url) => { if (new URL(url).origin !== origin) event.preventDefault(); });
  owner.webContents.on('will-attach-webview', event => event.preventDefault());
  owner.once('ready-to-show', () => {
    if (!backgroundTest) owner.show();
    else recordTestEvent('renderer-ready');
    if (openingWindow && !openingWindow.isDestroyed()) openingWindow.destroy();
    openingWindow = null;
  });
  owner.on('closed', () => {
    for (const pending of backupDownloads.values()) pending.abort();
    if (window === owner) window = null;
  });
  void owner.loadURL(origin);
}
ipcMain.handle('renulus:version', event => { if (event.sender !== window?.webContents) throw new Error('Invalid sender'); return app.getVersion(); });
ipcMain.handle('renulus:open-authorization', async (event, url: unknown) => {
  if (event.sender !== window?.webContents || typeof url !== 'string' || !allowedAuthorizationUrl(url)) throw new Error('The sign-in URL is not permitted.');
  await openExternal(url, 'authorization');
});
ipcMain.handle('renulus:open-source', async (event, url: unknown) => {
  if (event.sender !== window?.webContents || typeof url !== 'string' || !allowedSourceUrl(url)) throw new Error('The source URL is not permitted.');
  await openExternal(url, 'source');
});
function ownsBackupSender(event: IpcMainInvokeEvent): boolean {
  return !!window && !window.isDestroyed() && event.sender === window.webContents &&
    event.senderFrame === window.webContents.mainFrame;
}
ipcMain.handle('renulus:save-backup', async (event, kind: unknown, operation: unknown): Promise<BackupSaveResult> => {
  if (!ownsBackupSender(event) || !backend || (kind !== 'zip' && kind !== 'json') || !validBackupOperation(operation)) {
    return { status: 'error', code: 'invalid_backup_request', message: 'This backup must be saved from the current Renulus window.' };
  }
  if (backupDownloads.size) return { status: 'error', code: 'backup_busy', message: 'Wait for the current backup or cancel it before saving another.' };
  if (backgroundTest) {
    recordTestEvent('native-dialog-blocked', { target: 'save-backup', format: kind });
    return { status: 'cancelled' };
  }
  const format = kind as 'zip' | 'json';
  const controller = new AbortController(); backupDownloads.set(operation, controller);
  const stop = () => controller.abort(); lifetime.signal.addEventListener('abort', stop, { once: true });
  if (lifetime.signal.aborted) controller.abort();
  const timeout = setTimeout(stop, 30 * 60 * 1000);
  try {
    const selected = await dialog.showSaveDialog(window!, {
      title: format === 'zip' ? 'Save your Renulus backup' : 'Save your Renulus records',
      defaultPath: 'renulus-' + (format === 'zip' ? 'backup-' : 'records-') + new Date().toISOString().slice(0, 10) + '.' + format,
      filters: [{ name: format === 'zip' ? 'Renulus ZIP backup' : 'Renulus records JSON', extensions: [format] }],
      properties: ['showOverwriteConfirmation', 'createDirectory'],
    });
    if (selected.canceled || !selected.filePath || controller.signal.aborted) return { status: 'cancelled' };
    const result = await downloadBackup({ port: backend.port, token, kind: format, destination: selected.filePath, signal: controller.signal });
    return { status: 'saved', ...result };
  } catch (error) {
    if (controller.signal.aborted) return { status: 'cancelled' };
    if (error instanceof BackupDownloadError) return { status: 'error', code: error.code, message: error.message };
    const storageError = (error as NodeJS.ErrnoException).code;
    return { status: 'error', code: 'backup_save_failed', message: storageError === 'ENOSPC'
      ? 'There is not enough free space to save this backup. Choose a folder with more space and try again.'
      : 'The backup could not be saved. Check that the selected folder is writable, then try again.' };
  } finally {
    clearTimeout(timeout); lifetime.signal.removeEventListener('abort', stop); backupDownloads.delete(operation);
  }
});
ipcMain.handle('renulus:cancel-backup', (event, operation: unknown) => {
  if (!ownsBackupSender(event) || !validBackupOperation(operation)) throw new Error('This cancellation must come from the current Renulus window.');
  backupDownloads.get(operation)?.abort();
});
app.on('second-instance', () => ensureMainWindow(window ?? openingWindow, { isReady: app.isReady(), createWindow, focusWindow: activateWindow, focusExisting: !backgroundTest }));
app.on('activate', () => ensureMainWindow(window ?? openingWindow, { isReady: app.isReady(), createWindow, focusWindow: activateWindow, focusExisting: !backgroundTest }));
app.on('window-all-closed', () => app.quit());
app.on('before-quit', event => {
  if (stopping) return;
  event.preventDefault(); lifetime.abort();
  if (!stopPromise) stopPromise = (async () => {
    if (frontend) { frontend.server.closeAllConnections(); await new Promise<void>(resolve => frontend!.server.close(() => resolve())); }
    await backend?.stop();
  })();
  void stopPromise.then(() => { stopping = true; app.quit(); }, () => { stopPromise = undefined; reportNativeError('Renulus could not finish stopping', 'The owned backend did not exit cleanly. Close this development instance and inspect its lifecycle evidence.'); });
});
if (ownsInstance) void app.whenReady().then(async () => {
  try {
    openingWindow = createStartupWindow(profile.instance, path.join(__dirname, '../dist/renulus.ico'), lifetime.signal, backgroundTest);
    const openingOwner = openingWindow;
    openingOwner.on('closed', () => { if (openingWindow === openingOwner) openingWindow = null; });
    backend = await startBackend({ profile, token, workspace, resources: process.resourcesPath, packaged: app.isPackaged, signal: lifetime.signal, onOwnedChild: handle => { backend = handle; } });
    lifetime.signal.throwIfAborted();
    frontend = await startFrontend(path.join(__dirname, '../dist'), backend.port, token);
    lifetime.signal.throwIfAborted(); createWindow();
  } catch (error) {
    if (!lifetime.signal.aborted) reportNativeError('Renulus could not start', error instanceof Error ? error.message : 'The local runtime could not start.');
    app.quit();
  }
});
