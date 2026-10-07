/** Unchanged parent native entry, cancelled before backend readiness. Not a final bundle proof. */
import { _electron as electron } from '@playwright/test';
import { build } from 'esbuild';
import { mkdir, readFile, writeFile, copyFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { randomUUID, createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = process.env.RENULUS_STARTUP_SOURCE;
const requestedRevision = process.env.RENULUS_STARTUP_REVISION;
const python = process.env.RENULUS_PYTHON;
if (!source || !path.isAbsolute(source) || !requestedRevision || !python || !path.isAbsolute(python)) throw new Error('Explicit parent source/revision and the existing embedded interpreter are required.');
const revision = execFileSync('git', ['rev-parse', requestedRevision], { cwd:source, encoding:'utf8' }).trim();
const evidence = path.join(desktop, 'test-results', 'opening-' + randomUUID().slice(0, 8));
const snapshot = path.join(evidence, 'source');
const native = path.join(snapshot, 'apps/desktop/electron');
const compiled = path.join(snapshot, 'apps/desktop/dist-electron');
await mkdir(native, { recursive:true }); await mkdir(compiled, { recursive:true });
const files = execFileSync('git', ['ls-tree', '-r', '--name-only', revision, '--', 'apps/desktop/electron'], { cwd:source, encoding:'utf8' }).trim().split('\n');
const hashes = {};
for (const file of files) {
  const bytes = execFileSync('git', ['show', revision + ':' + file], { cwd:source, encoding:null });
  const target = path.join(snapshot, file); await mkdir(path.dirname(target), { recursive:true }); await writeFile(target, bytes);
  hashes[file] = createHash('sha256').update(bytes).digest('hex');
}
await build({ entryPoints:[path.join(native, 'main.ts')], outfile:path.join(compiled, 'main.cjs'), bundle:true, platform:'node', format:'cjs', target:'node24', external:['electron'], logLevel:'warning' });
await mkdir(path.join(snapshot, 'apps/desktop/dist'));
await copyFile(path.join(desktop, 'public/renulus.ico'), path.join(snapshot, 'apps/desktop/dist/renulus.ico'));
const env = {};
for (const name of ['SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','USERPROFILE','LOCALAPPDATA','APPDATA']) if (process.env[name]) env[name] = process.env[name];
env.PATH = path.join(process.env.SystemRoot, 'System32'); env.RENULUS_PROFILE = path.join(evidence, 'profile'); env.RENULUS_PYTHON = python;
const expectedElectron = JSON.parse(await readFile(path.join(desktop, 'package.json'), 'utf8')).devDependencies.electron;
const alive = pid => { try { process.kill(pid, 0); return true; } catch (error) { return error.code === 'EPERM'; } };
let application, result = { kind:'committed-native-source-early-close', sourceRevision:revision, sourceSha256:hashes, embeddedInterpreter:python, limits:['Nonpackaged source checkpoint; final matching bundle/installer proof remains separate', 'Backend deliberately closed before readiness; no framework/model/inference proof', 'Tree exit does not prove Services.on_shutdown callbacks'] };
try {
  const startedAt = Date.now();
  application = await electron.launch({ executablePath:path.join(desktop, 'node_modules/electron/dist/electron.exe'), args:[path.join(compiled, 'main.cjs')], cwd:path.join(snapshot, 'apps/desktop'), env, timeout:20_000 });
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline) {
    result.opening = await application.evaluate(({ BrowserWindow, app }) => {
      const opening = BrowserWindow.getAllWindows().find(window => window.isVisible() && window.webContents.getURL().startsWith('data:'));
      if (!opening) return null;
      const preferences = opening.webContents.getLastWebPreferences();
      const children = process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(child => ({ pid:child.pid, command:child.spawnfile, exitCode:child.exitCode }));
      return { mainPid:process.pid, electron:process.versions.electron, packaged:app.isPackaged, children, flowWindows:BrowserWindow.getAllWindows().filter(window => window.webContents.getURL().startsWith('http://127.0.0.1:')).length, policy:{ javascript:preferences.javascript, preload:Boolean(preferences.preload), sandbox:preferences.sandbox, contextIsolation:preferences.contextIsolation, nodeIntegration:preferences.nodeIntegration, persistent:opening.webContents.session.isPersistent() } };
    });
    if (result.opening?.children.length === 1 && result.opening.children[0].exitCode === null) break;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  result.firstVisibleWindowSeconds = (Date.now() - startedAt) / 1000;
  const opening = result.opening;
  if (!opening || opening.electron !== expectedElectron || opening.packaged || opening.flowWindows || opening.children.length !== 1 || path.resolve(opening.children[0].command).toLowerCase() !== path.resolve(python).toLowerCase() || !alive(opening.children[0].pid) || opening.policy.javascript !== false || opening.policy.preload || !opening.policy.sandbox || !opening.policy.contextIsolation || opening.policy.nodeIntegration || opening.policy.persistent) throw new Error('The unchanged protected opening surface and physically owned embedded child were not observed.');
  const page = application.windows().find(page => page.url().startsWith('data:'));
  if (page) await page.screenshot({ path:path.join(evidence, 'protected-opening-window.png') });
  const closed = application.waitForEvent('close', { timeout:20_000 });
  const closingAt = Date.now();
  await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().find(window => window.webContents.getURL().startsWith('data:')).close());
  await closed; application = null;
  result.closeSeconds = (Date.now() - closingAt) / 1000;
  result.childrenAfterClose = opening.children.map(child => child.pid).filter(alive);
  if (result.childrenAfterClose.length) throw new Error('The early-close owned backend survived.');
} catch (error) { result.error = error.message; }
finally { if (application) await application.close(); await writeFile(path.join(evidence, 'opening-evidence.json'), JSON.stringify({ checkedAt:new Date().toISOString(), ...result }, null, 2)); }
console.log(JSON.stringify({ evidence, ...result }));
if (result.error) process.exitCode = 1;
