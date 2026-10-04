/** Explicit synthetic development proof. No account login, provider request or installer claim. */
import { _electron as electron } from '@playwright/test';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { extractFile, listPackage } from '@electron/asar';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
await mkdir(path.join(desktop, 'test-results'), { recursive: true });
const evidence = path.join(desktop, 'test-results', 'native-' + randomUUID().slice(0, 8));
await mkdir(evidence);
const expectedVersion = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const attached = process.env.RENULUS_TEST_ATTACH === '1';
const packagedExecutable = process.env.RENULUS_PACKAGED_EXECUTABLE;
const installed = process.env.RENULUS_INSTALLED_PROOF === '1';
if (installed && !packagedExecutable) throw new Error('Installed proof requires an explicit packaged executable.');
if (packagedExecutable && (!path.isAbsolute(packagedExecutable) || attached)) throw new Error('Packaged proof needs an explicit absolute executable and its own managed backend.');
const python = process.env.RENULUS_PYTHON;
if (!attached && !packagedExecutable && (!python || !path.isAbsolute(python))) throw new Error('Set an explicit RENULUS_PYTHON for this development proof.');
if (attached && (!process.env.RENULUS_BACKEND_URL || !process.env.RENULUS_SESSION_TOKEN)) throw new Error('Attached proof needs an explicit local backend and app-only development token.');
let env = { ...process.env, RENULUS_PYTHON: python };
let portableRuntime;
let packagedSource;
if (packagedExecutable) {
  env = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA']) {
    if (process.env[name]) env[name] = process.env[name];
  }
  const systemRoot = process.env.SystemRoot ?? process.env.SYSTEMROOT;
  if (!systemRoot) throw new Error('Windows system root is required.');
  env.PATH = [path.join(systemRoot, 'System32'), path.join(systemRoot, 'System32', 'Wbem')].join(path.delimiter);
  const where = path.join(systemRoot, 'System32', 'where.exe');
  const absentTools = ['python', 'python3', 'py', 'uv', 'node', 'npm'].map(name => {
    const result = spawnSync(where, [name], { env, windowsHide: true, encoding: 'utf8' });
    if (result.status !== 1) throw new Error(name + ' unexpectedly resolves on the isolated proof PATH.');
    return name;
  });
  const backendRoot = path.join(path.dirname(packagedExecutable), 'resources', 'backend');
  const bundle = JSON.parse(await readFile(path.join(backendRoot, 'bundle.json'), 'utf8'));
  const archive = path.join(path.dirname(packagedExecutable), 'resources', 'app.asar');
  const renderer = JSON.parse(extractFile(archive, 'dist/renderer-provenance.json').toString('utf8'));
  const entries = listPackage(archive, {}).map(entry => entry.replaceAll('\\', '/'));
  const native = entries.includes('/dist-electron/native-provenance.json') ? JSON.parse(extractFile(archive, 'dist-electron/native-provenance.json').toString('utf8')) : null;
  if (renderer.source_revision !== bundle.source_revision || (native && (native.source_revision !== bundle.source_revision || native.electron_version !== expectedVersion)) || (process.env.RENULUS_EXPECT_SOURCE_REVISION && bundle.source_revision !== process.env.RENULUS_EXPECT_SOURCE_REVISION)) throw new Error('The packaged source revisions or Electron pin do not match.');
  packagedSource = { sourceRevision: bundle.source_revision, runtimePatches: bundle.source_patches, renderer, native, helperContractSha256: bundle.helper_contract_sha256, pythonArchiveSha256: bundle.python.archive_sha256 };
  const runtime = JSON.parse(execFileSync(path.join(backendRoot, 'python', 'python.exe'), ['-I', '-B', '-X', 'utf8', '-c', 'import json,sys;print(json.dumps({"version":sys.version.split()[0],"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,"isolated":sys.flags.isolated,"no_user_site":sys.flags.no_user_site,"paths":sys.path}))'], { env, cwd: path.dirname(packagedExecutable), windowsHide: true, encoding: 'utf8', timeout: 30_000 }));
  const inside = value => { const relative = path.relative(backendRoot, value); return !relative.startsWith('..') && !path.isAbsolute(relative); };
  if (runtime.version !== '3.14.4' || runtime.isolated !== 1 || runtime.no_user_site !== 1 || runtime.prefix !== runtime.base_prefix || !runtime.paths.every(inside) || !inside(runtime.executable)) throw new Error('The relocated interpreter is not isolated inside the portable runtime.');
  portableRuntime = { backendRoot, isolatedPath: env.PATH, absentTools, ...runtime };
}
if (!attached) { delete env.RENULUS_BACKEND_URL; delete env.RENULUS_SESSION_TOKEN; }
delete env.ELECTRON_RUN_AS_NODE;
const applications = [];
const records = [];
let startupCancellation = { tested: false };
function alive(pid) { try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } }
async function proveOpeningClose() {
  const startedAt = Date.now();
  const profile = path.join(evidence, 'profile-cancel');
  const application = await electron.launch({ executablePath: packagedExecutable, args: [], cwd: path.dirname(packagedExecutable), env: { ...env, RENULUS_PROFILE: profile }, timeout: 45_000 });
  applications.push(application);
  let opening;
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    opening = await application.evaluate(({ BrowserWindow }) => {
      const owner = BrowserWindow.getAllWindows().find(window => window.isVisible() && window.webContents.getURL().startsWith('data:'));
      if (!owner) return null;
      const preferences = owner.webContents.getLastWebPreferences();
      return { mainPid: process.pid, childPids: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid).filter(Boolean), policy: { javascript: preferences.javascript, hasPreload: Boolean(preferences.preload), nodeIntegration: preferences.nodeIntegration, contextIsolation: preferences.contextIsolation, sandbox: preferences.sandbox, persistentSession: owner.webContents.session.isPersistent() } };
    });
    if (opening?.childPids.length === 1) break;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!opening || opening.childPids.length !== 1 || opening.policy.javascript !== false || opening.policy.hasPreload || opening.policy.nodeIntegration || !opening.policy.contextIsolation || !opening.policy.sandbox || opening.policy.persistentSession) throw new Error('The protected opening window and physically owned backend were not observed.');
  const firstVisibleWindowSeconds = (Date.now() - startedAt) / 1000;
  const closed = application.waitForEvent('close', { timeout: 45_000 });
  await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().find(window => window.webContents.getURL().startsWith('data:')).close());
  await closed;
  applications.pop();
  const childrenAfterClose = opening.childPids.filter(alive);
  const otherOwnedBackendsAlive = records.every(record => record.childPids.every(alive));
  if (childrenAfterClose.length || !otherOwnedBackendsAlive) throw new Error('Closing the opening window failed owned-child cleanup or affected another isolated instance.');
  return { tested: true, profile, firstVisibleWindowSeconds, ...opening, childrenAfterClose, otherOwnedBackendsAlive };
}
try {
  for (const name of ['a', 'b']) {
    const profile = path.join(evidence, 'profile-' + name);
    const startedAt = Date.now();
    console.log(JSON.stringify({ stage: 'native-instance-starting', name }));
    const application = await electron.launch({ executablePath: packagedExecutable ?? path.join(desktop, 'node_modules', 'electron', 'dist', 'electron.exe'), args: packagedExecutable ? [] : ['.'], cwd: packagedExecutable ? path.dirname(packagedExecutable) : desktop, env: { ...env, RENULUS_PROFILE: profile }, timeout: packagedExecutable ? 360_000 : 45_000 });
    applications.push(application);
    const { page, ...windowTiming } = await waitForFlowWindow(application, { startedAt, timeout: packagedExecutable ? 360_000 : 45_000 });
    const info = await application.evaluate(({ app, BrowserWindow }, rendererUrl) => {
      const window = BrowserWindow.getAllWindows().find(window => window.webContents.getURL() === rendererUrl);
      return { pid: process.pid, packaged: app.isPackaged, executable: process.execPath, electronVersion: process.versions.electron, chromeVersion: process.versions.chrome, nodeVersion: process.versions.node, userData: app.getPath('userData'), sessionData: app.getPath('sessionData'), persistentSession: window.webContents.session.isPersistent(), webPreferences: { nodeIntegration: window.webContents.getLastWebPreferences().nodeIntegration, contextIsolation: window.webContents.getLastWebPreferences().contextIsolation, sandbox: window.webContents.getLastWebPreferences().sandbox }, childPids: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid).filter(Boolean) };
    }, page.url());
    const meta = await page.evaluate(async () => { const response = await fetch('/api/v1/meta'); return { status: response.status, value: await response.json(), rendererBridgeKeys: Object.keys(window.renulus ?? {}) }; });
    const backendReadySeconds = (Date.now() - startedAt) / 1000;
    if (info.electronVersion !== expectedVersion || meta.status !== 200 || meta.value.api_version !== 1 || info.persistentSession || info.webPreferences.nodeIntegration || !info.webPreferences.contextIsolation || !info.webPreferences.sandbox || info.childPids.length !== (attached ? 0 : 1)) throw new Error('Native version/process/session boundary failed.');
    if (packagedExecutable && (!info.packaged || path.resolve(info.executable).toLowerCase() !== path.resolve(packagedExecutable).toLowerCase())) throw new Error('This is not the requested packaged executable.');
    if (packagedExecutable && ['runtime', 'content', 'knowledge', 'retrieval', 'learn', 'cases', 'assessment', 'memory', 'study', 'updates'].some(name => meta.value.modules[name]?.status !== 'installed')) throw new Error('A packaged backend module is absent.');
    const unauthorizedStatus = (await fetch(new URL('/api/v1/meta', page.url()))).status;
    const authorizationRejected = await page.evaluate(async () => { try { await window.renulus.openAuthorization('https://untrusted.example/authorize'); return false; } catch { return true; } });
    if (unauthorizedStatus !== 401 || !authorizationRejected) throw new Error('Native API/sign-in boundary failed.');
    const startupSeconds = (Date.now() - startedAt) / 1000;
    records.push({ name, profile, startupSeconds, ...windowTiming, backendReadySeconds, ...info, meta, unauthorizedStatus, authorizationRejected });
    console.log(JSON.stringify({ stage: 'native-instance-ready', name, startupSeconds }));
    if (name === 'a') {
      await page.setViewportSize({ width: 1440, height: 960 });
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: path.join(evidence, 'flow-native-desktop.png'), fullPage: true });
      const routes = ['Learn', 'Library', 'Cases', 'Test', 'Memory', 'Updates', 'Connections', 'Today'];
      for (const label of routes) { await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: label, exact: true }).click(); await page.waitForFunction(label => document.title === 'Renulus · ' + label, label); }
      if (attached || packagedExecutable) {
        await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Connections', exact: true }).click();
        await page.getByRole('region', { name: 'Learning subscriptions' }).waitFor();
        const connections = await page.evaluate(async () => { const response = await fetch('/api/v1/connections'); if (!response.ok) throw new Error('Runtime Connections endpoint failed'); return response.json(); });
        if (connections.selected_provider !== null || connections.connections.some(connection => connection.status !== 'disconnected')) throw new Error('This synthetic proof requires a disconnected development profile.');
        records[0].connections = connections;
        if (packagedExecutable) {
          const runtime = await page.evaluate(async () => { const response = await fetch('/api/v1/runtime/status'); if (!response.ok) throw new Error('Packaged runtime status failed'); return response.json(); });
          if (!runtime.helpers.embedding.ready || !runtime.helpers.docling.ready) throw new Error('Packaged CPU helpers are not ready');
          if (!runtime.helper_startup.configured || !runtime.helper_startup.imports.embedding.ready || !runtime.helper_startup.imports.docling.ready || runtime.helper_startup.downloads || runtime.helper_startup.model_instances_created) throw new Error('Packaged helper imports did not warm inside the controlled profile.');
          records[0].runtime = runtime;
        }
        await page.screenshot({ path: path.join(evidence, 'flow-native-connections.png'), fullPage: true });
      }
      const endTemporary = page.getByRole('button', { name: 'End temporary context' });
      if (await endTemporary.isVisible()) await endTemporary.click();
      await page.getByRole('button', { name: 'Find a destination' }).click(); await page.getByRole('textbox', { name: 'Search destinations' }).fill('Memory'); await page.getByRole('dialog').getByRole('button', { name: 'Memory', exact: true }).click(); await page.waitForFunction(() => document.title === 'Renulus · Memory');
      await page.setViewportSize({ width: 640, height: 900 });
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      if (overflow) throw new Error('Compact native viewport overflows horizontally.');
      await page.screenshot({ path: path.join(evidence, 'flow-native-compact.png'), fullPage: true });
      records[0].routesChecked = routes; records[0].compactOverflow = overflow; records[0].destinationSearch = 'passed';
    }
  }
  if (records[0].userData === records[1].userData || records[0].pid === records[1].pid) throw new Error('Two instances were not isolated.');
  if (process.env.RENULUS_EXPECT_STARTUP_WINDOW === '1' && records.some(record => !record.startupWindowSeen)) throw new Error('The required early opening window was not observed.');
  if (packagedExecutable && records.some(record => record.startupWindowSeen)) startupCancellation = await proveOpeningClose();
} finally {
  for (const app of applications.reverse()) await app.close();
}
for (const record of records) {
  record.childrenAfterClose = record.childPids.filter(alive);
  if (record.childrenAfterClose.length) throw new Error('An owned backend survived native app close.');
}
const attachedBackendAlive = attached ? (await fetch(new URL('/api/v1/meta', env.RENULUS_BACKEND_URL), { headers: { 'x-renulus-token': env.RENULUS_SESSION_TOKEN } })).status === 200 : undefined;
if (attached && !attachedBackendAlive) throw new Error('Attached backend did not survive app close.');
await writeFile(path.join(evidence, 'native-evidence.json'), JSON.stringify({ checkedAt: new Date().toISOString(), kind: packagedExecutable ? installed ? 'unsigned-installed-native' : 'unsigned-relocated-directory-native' : attached ? 'attached-development-native' : 'managed-development-native', portableRuntime, packagedSource, records, startupCancellation, attachedBackendAlive, limits: [installed ? 'No signed or clean-machine Windows package proof' : 'No installed or signed Windows package proof', 'No provider login or model inference', packagedExecutable ? 'Launch checks do not exercise every integrated feature journey' : 'Feature entries remain integration states in this lane', 'Windows tree-kill does not prove backend shutdown callbacks'] }, null, 2));
console.log(JSON.stringify({ evidence, electronVersion: expectedVersion, instances: records.length, ownedBackendsStopped: !attached, attachedBackendAlive, nativeLaunch: 'passed' }));
