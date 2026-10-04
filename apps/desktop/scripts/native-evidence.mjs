/** Explicit synthetic development proof. No account login, provider request or installer claim. */
import { _electron as electron } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(desktop, 'test-results', 'native-' + randomUUID());
await mkdir(evidence, { recursive: true });
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const attached = process.env.RENULUS_TEST_ATTACH === '1';
const python = process.env.RENULUS_PYTHON;
if (!attached && (!python || !path.isAbsolute(python))) throw new Error('Set an explicit RENULUS_PYTHON for this development proof.');
if (attached && (!process.env.RENULUS_BACKEND_URL || !process.env.RENULUS_SESSION_TOKEN)) throw new Error('Attached proof needs an explicit local backend and app-only development token.');
const env = { ...process.env, RENULUS_PYTHON: python };
if (!attached) { delete env.RENULUS_BACKEND_URL; delete env.RENULUS_SESSION_TOKEN; }
delete env.ELECTRON_RUN_AS_NODE;
const applications = [];
const records = [];
function alive(pid) { try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } }
try {
  for (const name of ['a', 'b']) {
    const profile = path.join(evidence, 'profile-' + name);
    const application = await electron.launch({ executablePath: path.join(desktop, 'node_modules', 'electron', 'dist', 'electron.exe'), args: ['.'], cwd: desktop, env: { ...env, RENULUS_PROFILE: profile }, timeout: 45_000 });
    applications.push(application);
    const page = await application.firstWindow(); await page.waitForSelector('h1');
    const info = await application.evaluate(({ app, BrowserWindow }) => {
      const window = BrowserWindow.getAllWindows()[0];
      return { pid: process.pid, electronVersion: process.versions.electron, chromeVersion: process.versions.chrome, nodeVersion: process.versions.node, userData: app.getPath('userData'), sessionData: app.getPath('sessionData'), persistentSession: window.webContents.session.isPersistent(), webPreferences: { nodeIntegration: window.webContents.getLastWebPreferences().nodeIntegration, contextIsolation: window.webContents.getLastWebPreferences().contextIsolation, sandbox: window.webContents.getLastWebPreferences().sandbox }, childPids: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid).filter(Boolean) };
    });
    const meta = await page.evaluate(async () => { const response = await fetch('/api/v1/meta'); return { status: response.status, value: await response.json(), rendererBridgeKeys: Object.keys(window.renulus ?? {}) }; });
    if (info.electronVersion !== expectedVersion || meta.status !== 200 || meta.value.api_version !== 1 || info.persistentSession || info.webPreferences.nodeIntegration || !info.webPreferences.contextIsolation || !info.webPreferences.sandbox || info.childPids.length !== (attached ? 0 : 1)) throw new Error('Native version/process/session boundary failed.');
    const unauthorizedStatus = (await fetch(new URL('/api/v1/meta', page.url()))).status;
    const authorizationRejected = await page.evaluate(async () => { try { await window.renulus.openAuthorization('https://untrusted.example/authorize'); return false; } catch { return true; } });
    if (unauthorizedStatus !== 401 || !authorizationRejected) throw new Error('Native API/sign-in boundary failed.');
    records.push({ name, profile, ...info, meta, unauthorizedStatus, authorizationRejected });
    if (name === 'a') {
      await page.setViewportSize({ width: 1440, height: 960 });
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: path.join(evidence, 'flow-native-desktop.png'), fullPage: true });
      const routes = ['Learn', 'Library', 'Cases', 'Test', 'Memory', 'Updates', 'Connections', 'Today'];
      for (const label of routes) { await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: label, exact: true }).click(); await page.waitForFunction(label => document.title === 'Renulus · ' + label, label); }
      if (attached) {
        await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Connections', exact: true }).click();
        await page.getByRole('region', { name: 'Learning subscriptions' }).waitFor();
        const connections = await page.evaluate(async () => { const response = await fetch('/api/v1/connections'); if (!response.ok) throw new Error('Runtime Connections endpoint failed'); return response.json(); });
        if (connections.selected_provider !== null || connections.connections.some(connection => connection.status !== 'disconnected')) throw new Error('This synthetic proof requires a disconnected development profile.');
        records[0].connections = connections;
        await page.screenshot({ path: path.join(evidence, 'flow-native-connections.png'), fullPage: true });
      }
      await page.getByRole('button', { name: 'End temporary context' }).click();
      await page.getByRole('button', { name: 'Find a destination' }).click(); await page.getByRole('textbox', { name: 'Search destinations' }).fill('Memory'); await page.getByRole('dialog').getByRole('button', { name: 'Memory', exact: true }).click(); await page.waitForFunction(() => document.title === 'Renulus · Memory');
      await page.setViewportSize({ width: 640, height: 900 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      if (overflow) throw new Error('Compact native viewport overflows horizontally.');
      await page.screenshot({ path: path.join(evidence, 'flow-native-compact.png'), fullPage: true });
      records[0].routesChecked = routes; records[0].compactOverflow = overflow; records[0].destinationSearch = 'passed';
    }
  }
  if (records[0].userData === records[1].userData || records[0].pid === records[1].pid) throw new Error('Two instances were not isolated.');
} finally {
  for (const app of applications.reverse()) await app.close();
}
for (const record of records) {
  record.childrenAfterClose = record.childPids.filter(alive);
  if (record.childrenAfterClose.length) throw new Error('An owned backend survived native app close.');
}
const attachedBackendAlive = attached ? (await fetch(new URL('/api/v1/meta', env.RENULUS_BACKEND_URL), { headers: { 'x-renulus-token': env.RENULUS_SESSION_TOKEN } })).status === 200 : undefined;
if (attached && !attachedBackendAlive) throw new Error('Attached backend did not survive app close.');
await writeFile(path.join(evidence, 'native-evidence.json'), JSON.stringify({ checkedAt: new Date().toISOString(), kind: attached ? 'attached-development-native' : 'managed-development-native', records, attachedBackendAlive, limits: ['No installed or signed Windows package proof', 'No provider login or model inference', 'Feature entries remain integration states in this lane', 'Windows tree-kill does not prove backend shutdown callbacks'] }, null, 2));
console.log(JSON.stringify({ evidence, electronVersion: expectedVersion, instances: records.length, ownedBackendsStopped: !attached, attachedBackendAlive, nativeLaunch: 'passed' }));
