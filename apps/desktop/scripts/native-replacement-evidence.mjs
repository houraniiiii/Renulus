/** One fresh matching installed start/shutdown; earlier full matrix stays dated. */
import { _electron as electron } from '@playwright/test';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { extractFile } from '@electron/asar';
import { execFileSync, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { waitForFlowWindow } from './wait-for-flow-window.mjs';
import { createNativeEvidence } from './native-evidence-directory.mjs';

export function validateReplacementSource(bundle, renderer, native, expectedRevision, expectedElectron) {
  if (!/^[0-9a-f]{40}$/.test(expectedRevision ?? '') || [bundle, renderer, native].some(part => part.source_revision !== expectedRevision)) throw new Error('Replacement backend, renderer and native must match the exact accepted revision.');
  if (bundle.format !== 'embedded-cpython-windows-v1' || bundle.python.version !== '3.14.4' || bundle.source_patches?.length) throw new Error('Replacement requires the admitted embedded Python contract and unpatched frozen source.');
  if (native.electron_version !== expectedElectron || native.backend_adoption.source_sha256 !== native.backend_adoption.adopted_sha256) throw new Error('Replacement Electron pin or native source adoption differs.');
}

async function run() {
  const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const executable = process.env.RENULUS_PACKAGED_EXECUTABLE;
  const revision = process.env.RENULUS_EXPECT_SOURCE_REVISION;
  if (!executable || !path.isAbsolute(executable) || process.env.RENULUS_SOURCE_DESKTOP || process.env.RENULUS_BACKEND_URL) throw new Error('Replacement proof requires one explicit installed executable and an independent managed backend.');
  const expectedElectron = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
  const resources = path.join(path.dirname(executable), 'resources');
  const backend = path.join(resources, 'backend');
  const bundle = JSON.parse(await readFile(path.join(backend, 'bundle.json'), 'utf8'));
  const archive = path.join(resources, 'app.asar');
  const renderer = JSON.parse(extractFile(archive, 'dist/renderer-provenance.json').toString('utf8'));
  const native = JSON.parse(extractFile(archive, 'dist-electron/native-provenance.json').toString('utf8'));
  validateReplacementSource(bundle, renderer, native, revision, expectedElectron);
  const evidence = await createNativeEvidence('replacement');
  const profile = path.join(evidence, 'profile');
  const temporary = path.join(evidence, 'temporary');
  await mkdir(temporary);
  const env = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATHEXT', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA']) if (process.env[name]) env[name] = process.env[name];
  const systemRoot = env.SystemRoot ?? env.SYSTEMROOT;
  if (!systemRoot) throw new Error('Windows system root is required.');
  env.PATH = [path.join(systemRoot, 'System32'), path.join(systemRoot, 'System32', 'Wbem')].join(path.delimiter);
  env.TEMP = temporary; env.TMP = temporary; env.RENULUS_PROFILE = profile;
  const absentTools = ['python', 'python3', 'py', 'uv', 'node', 'npm'];
  for (const tool of absentTools) if (spawnSync(path.join(systemRoot, 'System32', 'where.exe'), [tool], { env, windowsHide: true }).status !== 1) throw new Error('Developer tool resolves on the isolated child PATH: ' + tool);
  const interpreter = JSON.parse(execFileSync(path.join(backend, 'python/python.exe'), ['-I', '-B', '-X', 'utf8', '-c', 'import sys,json;print(json.dumps(dict(version=sys.version.split()[0],prefix=sys.prefix,base_prefix=sys.base_prefix,isolated=sys.flags.isolated,no_user_site=sys.flags.no_user_site,paths=sys.path)))'], { env, cwd: path.dirname(executable), windowsHide: true, encoding: 'utf8', timeout: 30_000 }));
  const inside = value => { const relative = path.relative(backend, value); return !relative.startsWith('..') && !path.isAbsolute(relative); };
  if (interpreter.version !== '3.14.4' || interpreter.isolated !== 1 || interpreter.no_user_site !== 1 || interpreter.prefix !== interpreter.base_prefix || !interpreter.paths.every(inside)) throw new Error('Replacement interpreter is not isolated inside this installed bundle.');
  const result = { checkedAt: new Date().toISOString(), kind: 'single-fresh-installed-replacement', sourceRevision: revision, executable, evidence, profile, renderer, native, interpreter, absentTools, limits: ['One isolated installed start/shutdown on this Windows machine', 'Earlier two-profile/full-nav/PDF/transfer/backup matrix belongs to ebb2db2e', 'No private originals, account login, model inference, normal-shortcut or real learning-queue claim', 'Physical process exit does not prove shutdown callbacks'] };
  let application; let owner; let children = [];
  const alive = pid => { try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } };
  try {
    const startedAt = Date.now();
    application = await electron.launch({ executablePath: executable, args: [], cwd: path.dirname(executable), env, timeout: 360_000 });
    owner = application.process().pid;
    const { page, ...timing } = await waitForFlowWindow(application, { startedAt, timeout: 360_000 });
    result.windowTiming = timing;
    result.runtime = await application.evaluate(({ app, BrowserWindow }, url) => {
      const window = BrowserWindow.getAllWindows().find(item => item.webContents.getURL() === url);
      const preferences = window.webContents.getLastWebPreferences();
      return { pid: process.pid, executable: process.execPath, packaged: app.isPackaged, electron: process.versions.electron, userData: app.getPath('userData'), sandbox: preferences.sandbox, nodeIntegration: preferences.nodeIntegration, contextIsolation: preferences.contextIsolation, children: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid).filter(Boolean) };
    }, page.url());
    children = result.runtime.children;
    if (!result.runtime.packaged || result.runtime.electron !== expectedElectron || path.resolve(result.runtime.userData) !== path.join(profile, 'desktop') || !result.runtime.sandbox || result.runtime.nodeIntegration || !result.runtime.contextIsolation || children.length !== 1) throw new Error('Replacement runtime/profile/backend ownership differs from the isolated launch.');
    const metadata = await page.evaluate(async () => { const response = await fetch('/api/v1/meta'); return { status: response.status, apiVersion: (await response.json()).api_version }; });
    if (metadata.status !== 200 || metadata.apiVersion !== 1) throw new Error('The replacement renderer did not authenticate its managed backend.');
    result.backend = metadata;
    result.windowTiming.backendReadySeconds = (Date.now() - startedAt) / 1000;
    await page.screenshot({ path: path.join(evidence, 'replacement-flow.png'), fullPage: true });
    const closedAt = Date.now();
    await application.close(); application = undefined;
    const deadline = Date.now() + 30_000;
    while ([owner, ...children].some(alive) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 100));
    result.shutdown = { seconds: (Date.now() - closedAt) / 1000, remainingOwners: [owner, ...children].filter(alive) };
    if (result.shutdown.remainingOwners.length) throw new Error('A replacement-owned process survived close.');
  } catch (error) { result.error = { message: error.message }; }
  finally {
    if (application) { try { await application.close(); } catch (error) { result.closeError = error.message; if (owner && alive(owner)) execFileSync(path.join(systemRoot, 'System32/taskkill.exe'), ['/PID', String(owner), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); } }
    result.ownedProcessesRemaining = [owner, ...children].filter(Boolean).filter(alive);
    await writeFile(path.join(evidence, 'replacement-evidence.json'), JSON.stringify(result, null, 2));
  }
  console.log(JSON.stringify({ evidence, sourceRevision: revision, error: result.error?.message, windowTiming: result.windowTiming, shutdown: result.shutdown, ownedProcessesRemaining: result.ownedProcessesRemaining }));
  if (result.error || result.ownedProcessesRemaining.length) process.exitCode = 1;
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await run();
