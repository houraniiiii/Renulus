/** Verify the official release archive, then use Electron's own pinned installer. */
import { downloadArtifact } from '@electron/get';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readJson = async relative => JSON.parse(await readFile(path.join(desktop, relative), 'utf8'));
const manifest = await readJson('package.json');
const installed = await readJson('node_modules/electron/package.json');
if (manifest.devDependencies.electron !== installed.version || !/^\d+\.\d+\.\d+$/.test(installed.version)) throw new Error('Electron must match the exact application pin.');
if (process.platform !== 'win32' || !['x64', 'arm64'].includes(process.arch)) throw new Error('This verifier targets supported Windows desktop artifacts.');
for (const key of Object.keys(process.env)) {
  if (/^(ELECTRON_(CUSTOM_|MIRROR|NIGHTLY_MIRROR|OVERRIDE_|INSTALL_)|npm_config_electron_|NPM_CONFIG_ELECTRON_|npm_package_config_electron_)/.test(key) && process.env[key]) throw new Error('Custom Electron download configuration is not accepted by this official-artifact verifier.');
}
const version = installed.version;
const filename = `electron-v${version}-win32-${process.arch}.zip`;
const release = `https://github.com/electron/electron/releases/download/v${version}/`;
const evidence = path.join(desktop, 'test-results', 'electron-install');
const cacheRoot = path.join(evidence, 'cache');
await mkdir(evidence, { recursive: true });
const response = await fetch(release + 'SHASUMS256.txt', { signal: AbortSignal.timeout(30_000) });
if (!response.ok) throw new Error('Official Electron checksum download failed.');
const checksumText = await response.text();
await writeFile(path.join(evidence, 'SHASUMS256.txt'), checksumText);
const line = checksumText.split(/\r?\n/).find(value => value.trim().endsWith(filename));
const publishedHash = line?.match(/^[a-f0-9]{64}/)?.[0];
const checksums = await readJson('node_modules/electron/checksums.json');
if (!publishedHash || checksums[filename] !== publishedHash) throw new Error('Release and npm-package Electron checksums disagree.');
const zip = await downloadArtifact({ version, artifactName: 'electron', platform: 'win32', arch: process.arch, cacheRoot, checksums, mirrorOptions: { resolveAssetURL: () => release + filename } });
async function sha256(file) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
const archiveHash = await sha256(zip);
if (archiveHash !== publishedHash) throw new Error('The Electron archive checksum is invalid.');
const env = {};
for (const key of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'PATH', 'Path', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'COMSPEC']) if (process.env[key]) env[key] = process.env[key];
env.electron_config_cache = cacheRoot;
const child = spawn(process.execPath, [path.join(desktop, 'node_modules/electron/install.js')], { cwd: desktop, env, stdio: 'inherit', windowsHide: true });
const exitCode = await new Promise((resolve, reject) => { child.once('error', reject); child.once('exit', resolve); });
if (exitCode !== 0) throw new Error('The verified Electron installer failed.');
const binary = path.join(desktop, 'node_modules/electron/dist/electron.exe');
const binaryVersion = (await readFile(path.join(desktop, 'node_modules/electron/dist/version'), 'utf8')).trim().replace(/^v/, '');
if (binaryVersion !== version) throw new Error('The installed Electron version is not the pinned version.');
const lock = await readJson('package-lock.json');
const toolPackages = ['electron', '@electron/get', '@electron-internal/extract-zip', 'vitest', 'esbuild', '@esbuild/win32-' + process.arch, 'electron-winstaller'];
const result = {
  checkedAt: new Date().toISOString(), version, platform: process.platform, arch: process.arch,
  source: release + filename, checksumSource: release + 'SHASUMS256.txt', archiveSha256: archiveHash, binarySha256: await sha256(binary),
  extractorBinarySha256: await sha256(path.join(desktop, 'node_modules/@electron-internal/extract-zip', `index.win32-${process.arch}-msvc.node`)),
  esbuildBinarySha256: await sha256(path.join(desktop, 'node_modules/@esbuild/win32-' + process.arch, 'esbuild.exe')),
  packages: Object.fromEntries(toolPackages.map(name => [name, { version: lock.packages['node_modules/' + name].version, integrity: lock.packages['node_modules/' + name].integrity }])),
  scripts: manifest.allowScripts,
};
const evidenceFile = path.join(evidence, 'provenance.json');
await writeFile(evidenceFile, JSON.stringify(result, null, 2));
console.log(JSON.stringify({ version, archiveSha256: archiveHash, evidenceFile }));
