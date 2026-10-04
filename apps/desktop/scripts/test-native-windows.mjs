/** Actual Electron regression for the transient startup window; no product/API proof. */
import { _electron as electron } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
await mkdir(path.join(desktop, 'test-results'), { recursive: true });
const evidence = path.join(desktop, 'test-results', 'windows-' + randomUUID().slice(0, 8));
await mkdir(evidence);
const entry = path.join(evidence, 'main.cjs');
await writeFile(entry, `
const { app, BrowserWindow } = require('electron');
const { createServer } = require('node:http');
app.setPath('userData', ${JSON.stringify(path.join(evidence, 'profile'))});
let server;
app.whenReady().then(async () => {
  const startup = new BrowserWindow({ width:480, height:320, show:false, webPreferences:{ sandbox:true, contextIsolation:true, nodeIntegration:false } });
  await startup.loadURL('data:text/html,' + encodeURIComponent('<h1>Opening your learning space</h1>'));
  startup.show();
  await new Promise(resolve => setTimeout(resolve, 4200));
  server = createServer((request, response) => { response.writeHead(200, { 'Content-Type':'text/html' }); response.end('<title>Synthetic Flow renderer fixture</title><nav aria-label="Main navigation">Synthetic navigation</nav><h1>Renderer fixture</h1>'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const flow = new BrowserWindow({ width:640, height:480, show:false, webPreferences:{ sandbox:true, contextIsolation:true, nodeIntegration:false } });
  await flow.loadURL('http://127.0.0.1:' + server.address().port + '/');
  flow.show(); startup.close();
});
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => server?.close());
`);
const env = {};
for (const key of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[key]) env[key] = process.env[key];
env.PATH = path.join(process.env.SystemRoot, 'System32');
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const startedAt = Date.now();
let application;
try {
  application = await electron.launch({ executablePath:path.join(desktop, 'node_modules/electron/dist/electron.exe'), args:[entry], env, cwd:evidence, timeout:30_000 });
  const { page, ...timing } = await waitForFlowWindow(application, { startedAt, timeout:30_000 });
  const version = await application.evaluate(() => process.versions.electron);
  assert.equal(version, expectedVersion);
  assert.equal(await page.title(), 'Synthetic Flow renderer fixture');
  assert.equal(timing.startupWindowSeen, true);
  assert.equal(timing.firstVisibleWindowKind, 'startup');
  assert.ok(timing.firstVisibleWindowSeconds < timing.rendererReadySeconds - 0.5);
  assert.equal(await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().length), 1);
  const result = { kind:'pinned-Electron-synthetic-window-regression', version, timing, startupClosed:true, limits:['No product backend or packaged/native-installer proof'] };
  await writeFile(path.join(evidence, 'window-evidence.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify({ evidence, ...result }));
} finally { if (application) await application.close(); }
