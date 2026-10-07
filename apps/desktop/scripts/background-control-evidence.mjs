/** Synthetic source proof for hidden Electron control. No desktop input or providers. */
import { _electron as electron } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = process.env.RENULUS_CONTROL_EVIDENCE;
const python = process.env.RENULUS_PYTHON;
const bridgesOnly = process.env.RENULUS_CONTROL_CHECKS === 'bridges';
const profile = process.env.RENULUS_CONTROL_PROFILE ?? (evidence && path.join(evidence, 'profile'));
if (!evidence || !path.isAbsolute(evidence) || !python || !path.isAbsolute(python)) throw new Error('Set absolute RENULUS_CONTROL_EVIDENCE and RENULUS_PYTHON. Use a fresh synthetic profile.');
if (!profile || !path.isAbsolute(profile)) throw new Error('Use an absolute owned synthetic profile.');
await mkdir(evidence, { recursive: true });
// Exclusive output keeps a previous failed receipt from being overwritten.
await writeFile(path.join(evidence, 'started.json'), JSON.stringify({ at: new Date().toISOString(), scope: 'synthetic-source-background-control' }), { flag: 'wx' });
const env = {};
for (const key of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'ComSpec', 'PATH', 'Path', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA']) if (process.env[key]) env[key] = process.env[key];
Object.assign(env, { RENULUS_PROFILE: profile, RENULUS_PYTHON: python, RENULUS_BACKGROUND_TEST: '1' });
const receipt = { scope: 'synthetic-source-background-control', checks: bridgesOnly ? 'missing-native-bridges-and-lifecycle' : 'full', started_at: new Date().toISOString(), profile: env.RENULUS_PROFILE, providers_called: false, physical_input: false, screenshots: [], stages: [], errors: [], window_events: [] };
let application;
let page;
const alive = pid => { try { process.kill(pid, 0); return true; } catch (error) { return error.code !== 'ESRCH'; } };
async function hiddenState() {
  const windows = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().filter(window => !window.isDestroyed()).map(window => ({ id: window.id, visible: window.isVisible(), focused: window.isFocused(), focusable: window.isFocusable(), url: window.webContents.getURL() })));
  if (windows.some(window => window.visible || window.focused || window.focusable)) throw new Error('An owned test window became visible, focused or focusable.');
  return windows;
}
async function capture(name) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
  const owner = await application.browserWindow(page);
  const data = await owner.evaluate(async window => (await window.capturePage(undefined, { stayHidden: true, stayAwake: false })).toPNG().toString('base64'));
  await owner.dispose();
  const pixels = Buffer.from(data, 'base64');
  if (pixels.length < 1000) throw new Error('Hidden capture returned no useful pixels.');
  await writeFile(path.join(evidence, name), pixels, { flag: 'wx' });
  receipt.screenshots.push({ name, bytes: pixels.length, windows: await hiddenState() });
}
try {
  application = await electron.launch({ executablePath: path.join(desktop, 'node_modules/electron/dist/electron.exe'), args: ['.'], cwd: desktop, env, timeout: 60_000 });
  application.process().stderr.on('data', data => {
    for (const line of data.toString().split('\n')) if (line.startsWith('RENULUS_BACKGROUND_EVENT ')) {
      try { receipt.window_events.push(JSON.parse(line.slice('RENULUS_BACKGROUND_EVENT '.length))); } catch {}
    }
  });
  application.on('window', ownedPage => ownedPage.on('pageerror', error => receipt.errors.push(error.message)));
  const deadline = Date.now() + 300_000;
  while (Date.now() < deadline) {
    await hiddenState();
    page = application.windows().find(candidate => {
      if (candidate.isClosed()) return false;
      try { const url = new URL(candidate.url()); return url.protocol === 'http:' && url.hostname === '127.0.0.1' && !!url.port && url.pathname === '/'; } catch { return false; }
    });
    if (page) {
      try { await page.getByRole('navigation', { name: 'Main navigation', exact: true }).waitFor({ timeout: 150 }); break; } catch {}
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!page) throw new Error('The owned hidden Flow renderer did not become ready.');
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).waitFor({ timeout: 15_000 });
  page.setDefaultTimeout(15_000);
  receipt.owner = await application.evaluate(({ app }) => ({ pid: process.pid, packaged: app.isPackaged, userData: app.getPath('userData'), childPids: process._getActiveHandles().filter(handle => handle.constructor.name === 'ChildProcess').map(handle => handle.pid).filter(Boolean) }));
  if (receipt.owner.childPids.length !== 1 || receipt.owner.userData !== path.join(env.RENULUS_PROFILE, 'desktop')) throw new Error('A separate profile with exactly one owned backend is required.');
  receipt.stages.push('hidden-managed-startup');
  if (!bridgesOnly) {
  await writeFile(path.join(evidence, 'home.aria.txt'), await page.locator('body').ariaSnapshot(), { flag: 'wx' });
  await capture('home.png');
  await page.getByRole('link', { name: 'Cases', exact: true }).click();
  await page.getByRole('textbox', { name: 'Case title', exact: true }).fill('SYNTHETIC · Background control proof');
  await page.getByRole('textbox', { name: 'What would you like to discuss?', exact: true }).fill('SYNTHETIC TEST ONLY. Verify that app-scoped input reaches a hidden Renulus window. No patient information and no model request.');
  await page.getByRole('button', { name: 'Start temporary case', exact: true }).click();
  await page.getByRole('heading', { level: 1, name: 'SYNTHETIC · Background control proof', exact: true }).waitFor();
  await capture('case.png');
  receipt.stages.push('hidden-navigation-and-typing');
  }
  receipt.backup_bridge = await page.evaluate(async () => window.renulus.saveBackup('json', crypto.randomUUID()));
  if (receipt.backup_bridge.status !== 'cancelled') throw new Error('The valid backup request was not cancelled in background mode.');
  receipt.stages.push('native-save-dialog-suppression');
  if (!bridgesOnly) {
  receipt.native_bridges = await page.evaluate(async () => {
    const external = await window.renulus.openSource('https://example.org/renulus-control?token=SYNTHETIC').then(() => ({ blocked: false }), error => ({ blocked: true, message: error.message }));
    const authorization = await window.renulus.openAuthorization('https://auth.openai.com/api/accounts/authorize?state=SYNTHETIC').then(() => ({ blocked: false }), error => ({ blocked: true, message: error.message }));
    const backup = await window.renulus.saveBackup('json', crypto.randomUUID());
    return { external, authorization, backup };
  });
  if (!receipt.native_bridges.external.blocked || !receipt.native_bridges.authorization.blocked || receipt.native_bridges.backup.status !== 'cancelled') throw new Error('A native bridge escaped background suppression.');
  }
  await application.evaluate(({ app }) => { app.emit('activate'); app.emit('second-instance', {}, [], '', {}); });
  receipt.activation = await hiddenState();
  receipt.stages.push('external-dialog-and-activation-suppression');
  if (receipt.window_events.some(event => ['window-shown', 'window-focused'].includes(event.kind))) throw new Error('An owned window emitted a show/focus event.');
  const closing = application.waitForEvent('close', { timeout: 45_000 });
  await application.evaluate(({ app }) => app.quit());
  await closing;
  receipt.children_after_close = receipt.owner.childPids.filter(alive);
  if (receipt.children_after_close.length || alive(receipt.owner.pid)) throw new Error('The owned app/backend did not finish stopping.');
  application = undefined;
  receipt.stages.push('normal-owned-shutdown');
  if (receipt.errors.length) throw new Error('The owned renderer emitted an unexpected page error.');
  receipt.status = 'passed';
} catch (error) {
  receipt.status = 'failed'; receipt.failure = error.stack; process.exitCode = 1;
} finally {
  if (application) {
    try { await application.close(); } catch (error) { receipt.cleanup_error = error.message; }
  }
  receipt.finished_at = new Date().toISOString();
  await writeFile(path.join(evidence, 'result.json'), JSON.stringify(receipt, null, 2), { flag: 'wx' });
  console.log(JSON.stringify({ status: receipt.status, evidence, stages: receipt.stages, failure: receipt.failure }));
}
