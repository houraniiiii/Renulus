/** Exact committed product entry/preload, real OS dialogs, declared transfer-only fixtures. */
import { _electron as electron } from '@playwright/test';
import { createServer } from 'node:http';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { spawn, execFileSync } from 'node:child_process';
import { randomUUID, randomBytes, createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const suppliedSource = process.env.RENULUS_SOURCE_DESKTOP;
const sourceDesktop = suppliedSource && path.resolve(suppliedSource);
const expectedRevision = process.env.RENULUS_EXPECT_SOURCE_REVISION;
const python = process.env.RENULUS_FIXTURE_PYTHON;
const relativeSource = sourceDesktop ? path.relative(path.join(desktop, 'test-results'), sourceDesktop) : '..';
if (!sourceDesktop || !path.isAbsolute(suppliedSource) || relativeSource.startsWith('..') || path.isAbsolute(relativeSource) || !/^[0-9a-f]{40}$/.test(expectedRevision ?? '') || !python || !path.isAbsolute(python)) throw new Error('Explicit owned compiled source/revision and fixture interpreter are required.');
const provenance = JSON.parse(await readFile(path.join(sourceDesktop, 'dist-electron/native-provenance.json'), 'utf8'));
const renderer = JSON.parse(await readFile(path.join(sourceDesktop, 'dist/renderer-provenance.json'), 'utf8'));
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const sourceMainHash = createHash('sha256').update(await readFile(path.join(sourceDesktop, 'electron/main.ts'))).digest('hex');
const mainBundleHash = createHash('sha256').update(await readFile(path.join(sourceDesktop, 'dist-electron/main.cjs'))).digest('hex');
if (provenance.source_revision !== expectedRevision || renderer.source_revision !== expectedRevision || provenance.main_source_sha256 !== sourceMainHash || provenance.main_bundle_sha256 !== mainBundleHash || provenance.backend_adoption.source_sha256 !== provenance.backend_adoption.adopted_sha256 || provenance.electron_version !== expectedVersion) throw new Error('This source proof requires unchanged committed main/backend and a matching renderer.');
const evidence = path.join(desktop, 'test-results', 'native-save-' + randomUUID().slice(0, 8));
console.log(JSON.stringify({ stage: 'native-save-evidence', evidence }));
const exports = path.join(evidence, 'exports'); await mkdir(exports, { recursive: true });
const fixture = path.join(evidence, 'synthetic-transfer.zip');
execFileSync(python, ['-I', '-B', '-c', 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1],"w",compression=zipfile.ZIP_STORED); f=z.open("synthetic-transfer.bin","w"); block=b"Z"*65536; [f.write(block) for _ in range(1024)]; f.close(); z.close()', fixture], { windowsHide: true });
const fixtureBytes = (await stat(fixture)).size;
async function hashFile(file) { const hash = createHash('sha256'); for await (const block of createReadStream(file)) hash.update(block); return hash.digest('hex'); }
const fixtureHash = await hashFile(fixture);
const token = randomBytes(32).toString('hex');
const transfers = []; let metadataRequests = 0;
const server = createServer(async (request, response) => {
  if (request.headers['x-renulus-token'] !== token) { response.writeHead(401).end(); return; }
  const url = new URL(request.url, 'http://127.0.0.1');
  if (url.pathname === '/api/v1/meta') {
    metadataRequests++; if (metadataRequests === 1) await new Promise(resolve => setTimeout(resolve, 1500));
    response.writeHead(200, { 'Content-Type': 'application/json' }).end(JSON.stringify({ api_version: 1, version: '0.1.0', modules: {} })); return;
  }
  if (url.pathname !== '/api/v1/data/backup') {
    response.writeHead(404, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: { code: 'synthetic_transfer_fixture', message: 'This native test supplies recovery transfers only.', retryable: false } })); return;
  }
  const transfer = { ordinal: transfers.length + 1, method: request.method, route: url.pathname + url.search, authenticated: true, bytesSent: 0, finished: false, closed: false }; transfers.push(transfer);
  response.on('close', () => { transfer.closed = true; });
  if (transfer.ordinal === 3) { response.writeHead(409, { 'Content-Type': 'application/json' }).end(JSON.stringify({ error: { code: 'synthetic_backup_failure', message: 'The synthetic backup is deliberately unavailable.', retryable: false } })); return; }
  response.writeHead(200, { 'Content-Type': 'application/zip', 'Content-Length': fixtureBytes });
  const stream = createReadStream(fixture, { highWaterMark: 64 * 1024 });
  response.on('close', () => stream.destroy());
  try {
    for await (const block of stream) {
      if (response.destroyed) break;
      const flowing = response.write(block); transfer.bytesSent += block.length;
      if (!flowing) await new Promise(resolve => { const done = () => { response.off('drain', done); response.off('close', done); resolve(); }; response.once('drain', done); response.once('close', done); });
      await new Promise(resolve => setTimeout(resolve, 8));
    }
    if (!response.destroyed) { transfer.finished = true; response.end(); }
  } catch (error) { transfer.streamStopped = error.code ?? error.name; }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32'); env.RENULUS_PROFILE = path.join(evidence, 'profile');
env.RENULUS_BACKEND_URL = 'http://127.0.0.1:' + server.address().port; env.RENULUS_SESSION_TOKEN = token;
const executable = path.join(desktop, 'node_modules/electron/dist/electron.exe');
const powershell = path.join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe');
let application, mainPid;
const result = { sourceRevision: expectedRevision, provenance, renderer, fixture: { bytes: fixtureBytes, sha256: fixtureHash, kind: 'valid ZIP of synthetic bytes; not a Renulus recovery archive' }, cases: [], limits: ['Unchanged committed product entry/preload/renderer, nonpackaged source proof', 'Attached declared transfer fixture; no real backend/module readiness or managed Python-child claim', 'Fixture metadata response delayed 1.5s to observe opening-to-Flow; not production startup timing', 'No model/helper/private-profile/clean-delivery use', 'Renderer consumer/segmented archive semantics and final matching bundle remain separate'] };
function operateDialog(action, target, name) {
  return new Promise((resolve, reject) => {
    const helper = spawn(powershell, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(desktop, 'scripts/operate-owned-save-dialog.ps1'), '-AppProcessId', String(mainPid), '-ExpectedExecutable', executable, '-Action', action, '-Target', target, '-EvidencePath', path.join(evidence, name)], { windowsHide: true, timeout: 30_000 });
    let stdout = '', stderr = ''; helper.stdout.on('data', block => { stdout += block; }); helper.stderr.on('data', block => { stderr += block; });
    helper.once('error', reject); helper.once('close', code => resolve({ code, stdout, stderr }));
  });
}
async function awaitPartial(target, name, outcome) {
  const deadline = Date.now() + 45_000;
  while (Date.now() < deadline) {
    if (outcome()) throw new Error('The actual IPC returned ' + JSON.stringify(outcome()) + ' before a confined sibling partial was observed.');
    try { const gui = await dialogResult(name); if (gui.error) throw new Error('Actual Windows dialog operation failed: ' + gui.error); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    for (const name of await readdir(exports)) {
      if (name.startsWith(path.basename(target) + '.renulus-') && name.endsWith('.partial')) { const bytes = (await stat(path.join(exports, name))).size; if (bytes >= 64 * 1024) return { file: name, bytes }; }
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw new Error('The actual backup IPC did not reach an observable sibling partial file.');
}
async function dialogResult(name) { return JSON.parse((await readFile(path.join(evidence, name + '.json'), 'utf8')).replace(/^\uFEFF/, '')); }
try {
  const startedAt = Date.now();
  application = await electron.launch({ executablePath: executable, args: [sourceDesktop], cwd: sourceDesktop, env, timeout: 45_000 });
  mainPid = await application.evaluate(() => process.pid);
  const { page, ...timing } = await waitForFlowWindow(application, { startedAt, timeout: 45_000, requireHeading: false }); result.timing = { ...timing, homeModuleVerified: false };
  result.native = await application.evaluate(({ app, BrowserWindow }) => ({ mainPid: process.pid, electron: process.versions.electron, packaged: app.isPackaged, windows: BrowserWindow.getAllWindows().map(window => ({ visible: window.isVisible(), url: window.webContents.getURL() })), childPids: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid) }));
  if (!timing.startupWindowSeen || result.native.electron !== expectedVersion || result.native.packaged || result.native.childPids.length || result.native.windows.some(window => window.url.startsWith('data:'))) throw new Error('The exact source opening-to-Flow handoff was not observed.');
  const bridge = await page.evaluate(() => ({ save: typeof window.renulus?.saveBackup, cancel: typeof window.renulus?.cancelBackup }));
  if (bridge.save !== 'function' || bridge.cancel !== 'function') throw new Error('The actual committed native recovery preload is absent.');
  result.invalidRequest = await page.evaluate(() => window.renulus.saveBackup('zip', 'invalid-operation'));
  if (result.invalidRequest.code !== 'invalid_backup_request') throw new Error('The actual IPC accepted an invalid operation.');
  result.writeConfinement = await application.evaluate((_electron, ownedExports) => {
    const io = process.getBuiltinModule('fs/promises'); const nativePath = process.getBuiltinModule('path');
    const original = io.open; globalThis.renulusSyntheticWriteGuard = [];
    io.open = async (file, ...options) => {
      if (typeof file === 'string' && /\.renulus-[0-9a-f-]+\.partial$/.test(file)) {
        const confined = nativePath.dirname(nativePath.resolve(file)) === ownedExports;
        globalThis.renulusSyntheticWriteGuard.push({ file, confined });
        if (!confined) { const error = new Error('Synthetic native proof output escaped its export folder'); error.code = 'EACCES'; throw error; }
      }
      return original(file, ...options);
    };
    return 'test-only open guard; unchanged original I/O for confined output; no dialog substitution';
  }, exports);
  for (const name of ['promotion', 'transfer-cancel', 'backend-error', 'dialog-cancel']) {
    const operation = randomUUID(); const target = path.join(exports, name + '.zip'); const sentinel = Buffer.from('Synthetic existing destination: ' + name);
    if (name !== 'dialog-cancel') await writeFile(target, sentinel);
    console.log(JSON.stringify({ stage: 'actual-native-dialog', name }));
    await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().find(window => window.webContents.getURL().startsWith('http://127.0.0.1:'))?.focus());
    let savedOutcome;
    const saved = page.evaluate(id => window.renulus.saveBackup('zip', id), operation);
    saved.then(response => { savedOutcome = response; console.log(JSON.stringify({ stage: 'backup-ipc-return', name, response })); }, () => {});
    const automation = operateDialog(name === 'dialog-cancel' ? 'cancel' : 'save', target, name);
    saved.catch(() => {}); automation.catch(() => {}); // Cleanup may close a pending native dialog.
    let partial;
    if (['promotion', 'transfer-cancel'].includes(name)) {
      partial = await awaitPartial(target, name, () => savedOutcome);
      if (!(await readFile(target)).equals(sentinel)) throw new Error('An existing destination changed before partial promotion.');
      if (name === 'transfer-cancel') await page.evaluate(id => window.renulus.cancelBackup(id), operation);
    }
    const [response, helper] = await Promise.all([saved, automation]); const gui = await dialogResult(name);
    if (helper.code || gui.error || !gui.dialogFound) throw new Error('Actual Windows Save dialog automation did not pass: ' + (gui.error ?? helper.stderr));
    const record = { name, operation, response, gui, partial, remainingPartials: (await readdir(exports)).filter(file => file.startsWith(path.basename(target) + '.renulus-')) };
    if (record.remainingPartials.length) throw new Error('An owned sibling partial survived the operation.');
    if (name === 'promotion') { record.sha256 = await hashFile(target); if (response.status !== 'saved' || response.bytes !== fixtureBytes || response.fileName !== path.basename(target) || record.sha256 !== fixtureHash) throw new Error('The selected file did not promote the exact completed ZIP.'); }
    if (name === 'transfer-cancel' && (response.status !== 'cancelled' || !(await readFile(target)).equals(sentinel))) throw new Error('Cancellation changed the existing target or status.');
    if (name === 'backend-error' && (response.status !== 'error' || response.code !== 'synthetic_backup_failure' || !(await readFile(target)).equals(sentinel))) throw new Error('The bounded API error or existing-file guard failed.');
    if (name === 'dialog-cancel' && response.status !== 'cancelled') throw new Error('Native dialog cancellation did not return cancelled.');
    result.cases.push(record);
  }
  result.transfers = transfers;
  result.nativeFileGuards = await application.evaluate(() => globalThis.renulusSyntheticWriteGuard);
  if (!result.nativeFileGuards.length || result.nativeFileGuards.some(record => !record.confined)) throw new Error('The native save proof escaped its synthetic export folder.');
  if (transfers.some(transfer => transfer.method !== 'GET' || transfer.route !== '/api/v1/data/backup?format_version=2')) throw new Error('The committed native bridge did not request the format-2 backup route.');
  if (transfers.length !== 3 || !transfers[0].finished || transfers[1].finished || !transfers[1].closed) throw new Error('Fixture transfer completion/cancellation did not match actual native operations.');
  await page.screenshot({ path: path.join(evidence, 'source-flow-after-dialogs.png'), fullPage: true });
} catch (error) { result.error = error.message; result.transfers = transfers; if (application) { try { result.nativeFileGuards = await application.evaluate(() => globalThis.renulusSyntheticWriteGuard); } catch {} } }
finally {
  if (application) { try { await application.close(); } catch (error) { result.closeError = error.message; if (mainPid) execFileSync('taskkill', ['/PID', String(mainPid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); } }
  server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  await writeFile(path.join(evidence, 'native-save-source-evidence.json'), JSON.stringify({ checkedAt: new Date().toISOString(), ...result }, null, 2));
}
console.log(JSON.stringify({ evidence, cases: result.cases.map(record => ({ name: record.name, status: record.response.status, dialogFound: record.gui.dialogFound })), error: result.error }));
if (result.error || result.closeError) process.exitCode = 1;
