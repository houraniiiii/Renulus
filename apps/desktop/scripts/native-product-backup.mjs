/** Real packaged DataManagement -> native Save dialog -> actual format-2 producer. */
import { spawn, execFileSync } from 'node:child_process';
import { readFile, writeFile, mkdir, readdir, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const testRoot = path.join(desktop, 'test-results');

async function hashFile(file) {
  const digest = createHash('sha256');
  for await (const block of createReadStream(file)) digest.update(block);
  return digest.digest('hex');
}

export async function proveNativeProductBackup(application, page, evidence, executable, env) {
  const relative = path.relative(testRoot, evidence);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) throw new Error('The producer proof requires its owned synthetic evidence folder.');
  const native = await application.evaluate(({ app }) => ({ packaged: app.isPackaged, pid: process.pid, executable: process.execPath, resources: process.resourcesPath, userData: app.getPath('userData') }));
  const profileRelative = path.relative(evidence, native.userData);
  if (!native.packaged || path.resolve(native.executable) !== path.resolve(executable) || !profileRelative || profileRelative.startsWith('..') || path.isAbsolute(profileRelative)) throw new Error('Actual producer backup proof is confined to the packaged app and its fresh synthetic profile.');
  const python = path.join(native.resources, 'backend/python/python.exe');
  const marker = 'Synthetic native backup verification ' + randomUUID();
  const added = await page.evaluate(async text => {
    const response = await fetch('/api/v1/memory/facts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, kind: 'goal', scope: { kind: 'study' }, idempotency_key: text }) });
    return { status: response.status, body: await response.json() };
  }, marker);
  if (added.status !== 201 || typeof added.body.id !== 'string' || added.body.text !== marker) throw new Error('The actual producer could not retain its synthetic manual learning note.');
  const recovery = await page.evaluate(async () => { const response = await fetch('/api/v1/data/recovery'); return { status: response.status, body: await response.json() }; });
  if (recovery.status !== 200 || !recovery.body.backup_formats?.['2']) throw new Error('The packaged backend did not advertise actual format-2 backup support.');
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Connections', exact: true }).click();
  await page.getByRole('navigation', { name: 'Connection settings', exact: true }).getByRole('button', { name: 'Your study data', exact: true }).click();
  await page.getByRole('heading', { name: 'Your study data', exact: true }).waitFor({ state: 'visible' });
  const exports = path.join(evidence, 'product-backup');
  await mkdir(exports);
  const target = path.join(exports, 'product-full-backup.zip');
  await writeFile(target, 'Synthetic existing native producer destination');
  await application.evaluate((_electron, ownedExports) => {
    const io = process.getBuiltinModule('fs/promises'), nativePath = process.getBuiltinModule('path');
    const original = io.open; globalThis.renulusProductBackupGuard = [];
    io.open = async (file, ...options) => {
      if (typeof file === 'string' && /[.]renulus-[0-9a-f-]+[.]partial$/.test(file)) {
        const confined = nativePath.dirname(nativePath.resolve(file)) === ownedExports;
        globalThis.renulusProductBackupGuard.push({ file, confined });
        if (!confined) { const error = new Error('Synthetic producer proof output escaped its export folder'); error.code = 'EACCES'; throw error; }
      }
      return original(file, ...options);
    };
  }, exports);
  function operateDialog(action, name) {
    return new Promise((resolve, reject) => {
      const powershell = path.join(process.env.SystemRoot, 'System32/WindowsPowerShell/v1.0/powershell.exe');
      const helper = spawn(powershell, ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', path.join(desktop, 'scripts/operate-owned-save-dialog.ps1'), '-AppProcessId', String(native.pid), '-ExpectedExecutable', executable, '-Action', action, '-Target', target, '-EvidencePath', path.join(evidence, name)], { windowsHide: true, timeout: 30_000 });
      let stderr = ''; helper.stderr.on('data', block => { stderr += block; }); helper.stdout.resume();
      helper.once('error', reject); helper.once('close', async code => {
        try { const gui = JSON.parse((await readFile(path.join(evidence, name + '.json'), 'utf8')).replace(/^﻿/, '')); if (code || gui.error || !gui.dialogFound) throw new Error(gui.error ?? stderr ?? 'Native dialog operation failed'); resolve(gui); } catch (error) { reject(error); }
      });
    });
  }
  await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().find(window => window.webContents.getURL().startsWith('http://127.0.0.1:'))?.focus());
  await page.getByRole('button', { name: 'Download full backup (ZIP)', exact: true }).click();
  const savedNotice = page.getByText(/^Full backup saved: product-full-backup[.]zip [(]/);
  const [dialog] = await Promise.all([operateDialog('save', 'actual-producer-save-dialog'), savedNotice.waitFor({ state: 'visible', timeout: 120_000 })]);
  const inspection = JSON.parse(execFileSync(python, ['-I', '-B', path.join(desktop, 'scripts/inspect-native-backup.py')], { windowsHide: true, env, input: JSON.stringify({ file: target, expected_id: added.body.id, expected_text: marker }), encoding: 'utf8', timeout: 30_000 }));
  const result = { native, syntheticMemory: { id: added.body.id, kind: 'goal', scope: 'study' }, dialog, bytes: (await stat(target)).size, sha256: await hashFile(target), inspection, savedNotice: await savedNotice.innerText(), limits: ['Real small format-2 producer archive; no restore/multi-GiB/live-account claim', 'Partial promotion/cancellation during transfer separately proved with the paced synthetic 64MiB fixture'] };
  await page.getByRole('button', { name: 'Download full backup (ZIP)', exact: true }).click();
  const cancelledNotice = page.getByText('Backup save cancelled.', { exact: true });
  const [cancelledDialog] = await Promise.all([operateDialog('cancel', 'actual-producer-cancel-dialog'), cancelledNotice.waitFor({ state: 'visible', timeout: 45_000 })]);
  result.cancelledDialog = cancelledDialog; result.cancelledNotice = await cancelledNotice.innerText();
  if (await hashFile(target) !== result.sha256) throw new Error('Actual Save dialog cancellation changed the completed producer archive.');
  result.partials = (await readdir(exports)).filter(file => file.endsWith('.partial'));
  result.outputGuards = await application.evaluate(() => globalThis.renulusProductBackupGuard);
  if (result.partials.length || !result.outputGuards.length || result.outputGuards.some(record => !record.confined)) throw new Error('The actual producer save left a partial or escaped its synthetic output folder.');
  await page.screenshot({ path: path.join(evidence, 'actual-producer-data-management.png'), fullPage: true });
  await writeFile(path.join(evidence, 'actual-producer-backup-evidence.json'), JSON.stringify(result, null, 2));
  return result;
}
