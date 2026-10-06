import path from 'node:path';
import os from 'node:os';
import { randomBytes, createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { mkdir, readdir, readFile, writeFile, lstat, open, copyFile, rename } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { setTimeout as delay } from 'node:timers/promises';

export const LIMITS = Object.freeze({ operation: 15_000, lifecycle: 45_000, start: 360_000, logs: 1_000, line: 2_048, snapshot: 48_000, image: 8_000_000 });
const ROOT_MARKER = '.renulus-control.json';
const GROUPS = ['docling', 'embedding', 'ocr'];
const EVENT_PREFIX = 'RENULUS_BACKGROUND_EVENT ';
const execFileAsync = promisify(execFile);

export class ControlError extends Error {
  constructor(code, message) { super(message); this.name = 'ControlError'; this.code = code; }
}
function check(condition, code, message) { if (!condition) throw new ControlError(code, message); }
export function samePath(a, b) { return typeof a === 'string' && typeof b === 'string' && path.resolve(a).toLowerCase() === path.resolve(b).toLowerCase(); }
export function inside(root, file) { const relative = path.relative(root, file); return relative === '' || !relative.startsWith('..' + path.sep) && relative !== '..' && !path.isAbsolute(relative); }
function independent(a, b) { return !inside(a, b) && !inside(b, a); }
function absolute(value, label) {
  check(typeof value === 'string' && path.isAbsolute(value) && !value.split(/[\/]/).includes('..') && !value.startsWith('\\'), 'invalid_path', label + ' must be an absolute local path without parent traversal.');
  check(path.resolve(value) !== path.parse(path.resolve(value)).root, 'invalid_path', label + ' cannot be a drive root.');
  return path.resolve(value);
}
export function parseCli(argv) {
  const names = { '--repo': 'repo', '--python': 'python', '--executable': 'executable', '--state-root': 'stateRoot', '--helper-assets': 'helperAssets' };
  const result = { stateRoot: path.join(os.tmpdir(), 'rn-c') };
  for (let i = 0; i < argv.length; i += 2) {
    const key = names[argv[i]];
    check(key && i + 1 < argv.length && !argv[i + 1].startsWith('--') && !Object.hasOwn(result, key === 'stateRoot' ? '_stateRoot' : key), 'invalid_cli', 'Use --repo, --python, and optional --executable, --state-root, --helper-assets once each.');
    result[key] = absolute(argv[i + 1], argv[i]);
    if (key === 'stateRoot') result._stateRoot = true;
  }
  delete result._stateRoot;
  check(result.repo && (result.python || result.executable), 'invalid_cli', '--repo and either --python (source mode) or --executable (packaged mode) are required absolute paths.');
  return result;
}

// This is an allowlist, deliberately not a copy of the invoking account's environment.
export function isolatedEnvironment(inherited, config, session) {
  const result = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT']) if (inherited[name]) result[name] = inherited[name];
  const systemRoot = result.SystemRoot ?? result.SYSTEMROOT ?? 'C:\Windows';
  return { ...result, PATH: path.join(systemRoot, 'System32'), TEMP: session.temporary, TMP: session.temporary,
    RENULUS_BACKGROUND_TEST: '1', RENULUS_BACKGROUND_OWNER_PID: String(process.pid), RENULUS_PROFILE: session.profile, ...(config.python ? { RENULUS_PYTHON: config.python } : {}),
    HF_HUB_OFFLINE: '1', TRANSFORMERS_OFFLINE: '1', HF_HUB_DISABLE_TELEMETRY: '1', DO_NOT_TRACK: '1' };
}

export function redact(value, filledValues = []) {
  if (Array.isArray(value)) return value.map(item => redact(item, filledValues));
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([key, item]) => [key,
    /(?:token|secret|password|credential|authorization|api.?key|account|email|login.?id)/i.test(key) ? '[redacted]' : redact(item, filledValues)]));
  if (typeof value !== 'string') return value;
  let text = value;
  for (const filled of filledValues) if (filled && filled.length >= 8) text = text.split(filled).join('[filled value]');
  return text.split('\n').map(line => {
    if (/(?:bearer\s|\b(?:token|secret|password|credential|authorization|api[_ -]?key|access[_ -]?code|account[_ -]?id)\b|\bsk-[\w-]+)/i.test(line)) return '[redacted sensitive line]';
    return line.replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[redacted email]')
      .replace(/https?:\/\/[^\s<>"']+/gi, raw => { try { const url = new URL(raw); return isFlowUrl(url.href) ? url.origin + url.pathname : '[external URL]'; } catch { return '[URL]'; } });
  }).join('\n');
}

export function isFlowUrl(value) {
  try { const u = new URL(value); return u.protocol === 'http:' && u.hostname === '127.0.0.1' && !!u.port && !u.username && !u.password; } catch { return false; }
}
export function requestAllowed(url, method, origin) {
  let parsed;
  try { parsed = new URL(url); } catch { return false; }
  if (!isFlowUrl(url) || !origin || parsed.origin !== origin) return false;
  const p = parsed.pathname;
  if (!p.startsWith('/api/')) return method === 'GET' || method === 'HEAD';
  // App-owned subscription, source and retention gates produce actual product
  // errors. This controller does not substitute a local API mutation firewall.
  return p.startsWith('/api/v1/');
}

async function noLinks(file, allowMissing = false) {
  let cursor = path.resolve(file);
  while (true) {
    try { check(!(await lstat(cursor)).isSymbolicLink(), 'unsafe_path', 'Links and junctions are not accepted for controller state or helper artifacts.'); }
    catch (error) { if (!(allowMissing && error.code === 'ENOENT')) throw error; }
    const parent = path.dirname(cursor); if (parent === cursor) break; cursor = parent;
  }
}
async function outsideGit(directory) {
  let cursor = directory;
  while (true) {
    try { await lstat(path.join(cursor, '.git')); throw new ControlError('state_in_git', 'Controller state and evidence must live outside Git.'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    const parent = path.dirname(cursor); if (parent === cursor) break; cursor = parent;
  }
}
async function hashFile(file, signal) {
  const hash = createHash('sha256');
  for await (const chunk of createReadStream(file, { signal })) hash.update(chunk);
  return hash.digest('hex');
}
function canonical(value) {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
  return JSON.stringify(value);
}
async function boundedJson(file, limit = 1_000_000) {
  check((await lstat(file)).size <= limit, 'oversize_file', 'A controller contract exceeds its size limit.');
  return JSON.parse((await readFile(file, 'utf8')).replace(/^\uFEFF/, ''));
}

// Same manifest-last staging contract as scripts/copy_helper_assets.py, with link checks
// and equality against the repository's reviewed contract before reading any helper bytes.
export async function seedHelpers(repo, source, profile, signal) {
  const contractFile = path.join(repo, 'packaging/runtime/helper-assets.json');
  await noLinks(contractFile); await noLinks(path.join(source, 'manifest.json'));
  const reviewed = await boundedJson(contractFile);
  const acquired = await boundedJson(path.join(source, 'manifest.json'));
  check(canonical(reviewed) === canonical(acquired), 'helper_contract_mismatch', 'The acquired public helper manifest differs from the reviewed repository contract.');
  check(reviewed.version === 1 && Object.keys(reviewed.groups ?? {}).sort().join(',') === GROUPS.join(','), 'helper_contract_invalid', 'Expected the reviewed three-group helper contract.');
  const target = path.join(profile, 'helpers');
  check(independent(source, target), 'unsafe_path', 'Helper source and owned destination must be independent.');
  await noLinks(source); await noLinks(profile);
  const records = [], names = new Set();
  for (const group of Object.values(reviewed.groups)) {
    check(group.revision && group.source_url?.startsWith('https://') && Array.isArray(group.files) && group.files.length, 'helper_contract_invalid', 'Helper provenance is incomplete.');
    for (const record of group.files) {
      check(typeof record.path === 'string' && /^[A-Za-z0-9._/-]+$/.test(record.path) && !record.path.split('/').some(p => !p || p === '.' || p === '..') && !path.isAbsolute(record.path), 'unsafe_helper_path', 'A declared helper path is unsafe.');
      check(Number.isSafeInteger(record.size) && record.size > 0 && /^[a-f0-9]{64}$/.test(record.sha256) && !names.has(record.path.toLowerCase()), 'helper_contract_invalid', 'Helper hashes, sizes and paths must be unique and complete.');
      names.add(record.path.toLowerCase());
      const original = path.join(source, record.path), destination = path.join(target, record.path);
      await noLinks(original); await noLinks(destination, true);
      check((await lstat(original)).isFile() && (await lstat(original)).size === record.size && await hashFile(original, signal) === record.sha256, 'helper_integrity', 'A reviewed helper artifact failed its source hash or size check.');
      records.push({ ...record, original, destination });
    }
  }
  // Nothing else in the supplied directory is enumerated, opened or copied.
  for (const record of records) {
    signal?.throwIfAborted(); await mkdir(path.dirname(record.destination), { recursive: true });
    const staging = record.destination + '.copying';
    await copyFile(record.original, staging);
    check((await lstat(staging)).size === record.size && await hashFile(staging, signal) === record.sha256, 'helper_integrity', 'A staged public helper failed its copied hash or size check.');
    await rename(staging, record.destination);
  }
  await writeFile(path.join(target, 'manifest.json.copying'), JSON.stringify(reviewed, null, 2), { flag: 'wx' });
  await rename(path.join(target, 'manifest.json.copying'), path.join(target, 'manifest.json'));
  return { files: records.length, bytes: records.reduce((total, record) => total + record.size, 0), contractSha256: await hashFile(contractFile, signal) };
}

// ASAR's Pickle header is read without extracting an archive or executing package code.
async function asarText(archive, name, limit = 4_000_000) {
  const file = await open(archive, 'r');
  try {
    const prefix = Buffer.alloc(16); check((await file.read(prefix, 0, 16, 0)).bytesRead === 16 && prefix.readUInt32LE(0) === 4, 'invalid_package', 'The packaged ASAR header is invalid.');
    const headerBytes = prefix.readUInt32LE(4), jsonBytes = prefix.readUInt32LE(12);
    check(headerBytes <= 16_000_000 && headerBytes >= 8 && jsonBytes > 0 && jsonBytes <= headerBytes - 8, 'invalid_package', 'The packaged ASAR header is outside the read bound.');
    const json = Buffer.alloc(jsonBytes); check((await file.read(json, 0, jsonBytes, 16)).bytesRead === jsonBytes, 'invalid_package', 'The packaged ASAR header is incomplete.');
    let entry = JSON.parse(json.toString('utf8'));
    for (const part of name.split('/')) entry = entry?.files?.[part];
    check(entry && !entry.link && !entry.unpacked && Number.isSafeInteger(entry.size) && entry.size > 0 && entry.size <= limit && /^\d+$/.test(entry.offset), 'invalid_package', 'A required packaged Renulus file is unavailable or exceeds its bound.');
    const bytes = Buffer.alloc(entry.size); const offset = 8 + headerBytes + Number(entry.offset);
    check(Number.isSafeInteger(offset) && (await file.read(bytes, 0, bytes.length, offset)).bytesRead === bytes.length, 'invalid_package', 'A required packaged Renulus file is incomplete.');
    return bytes.toString('utf8');
  } finally { await file.close(); }
}
export async function launchContract(config) {
  const desktop = path.join(config.repo, 'apps/desktop');
  const executable = config.executable ?? path.join(desktop, 'node_modules/electron/dist/electron.exe');
  const python = config.executable ? path.join(path.dirname(executable), 'resources/backend/python/python.exe') : config.python;
  check(python && (await lstat(executable)).isFile() && (await lstat(python)).isFile(), 'missing_runtime', 'The fixed Electron executable and its source/bundled Python must already exist. No dependencies or browsers are installed at startup.');
  let main, metadata;
  if (config.executable) {
    const archive = path.join(path.dirname(executable), 'resources/app.asar');
    metadata = JSON.parse(await asarText(archive, 'package.json'));
    main = await asarText(archive, 'dist-electron/main.cjs');
  } else {
    metadata = await boundedJson(path.join(desktop, 'package.json'));
    const mainFile = path.join(desktop, 'dist-electron/main.cjs');
    check((await lstat(mainFile)).size <= 4_000_000, 'oversize_file', 'The compiled main bundle exceeds the preflight read bound.');
    main = await readFile(mainFile, 'utf8');
    check((await lstat(path.join(desktop, 'dist/index.html'))).isFile(), 'missing_build', 'Build the renderer and Electron source with the parent before using this controller.');
  }
  check(metadata.name === 'renulus-desktop' && metadata.main === 'dist-electron/main.cjs', 'wrong_app', 'Only the fixed Renulus app is supported.');
  const markers = ['RENULUS_BACKGROUND_TEST', 'RENULUS_BACKGROUND_OWNER_PID', 'RENULUS_BACKGROUND_EVENT', 'window-shown', 'window-focused', 'native-dialog-blocked', 'managed backend'];
  check(markers.every(marker => main.includes(marker)) && /skipTaskbar\s*:/.test(main) && /focusable\s*:/.test(main) && /backgroundThrottling\s*:/.test(main), 'background_build_required', 'This compiled app lacks the required hidden background contract. The frozen 02cd88e1 package must not be launched by this controller.');
  return { executable, cwd: config.executable ? path.dirname(executable) : desktop, args: config.executable ? [] : ['.'], mainSha256: createHash('sha256').update(main).digest('hex') };
}

export function remainingOwned(owners, rows) {
  return owners.filter(owner => rows.some(row => row.pid === owner.pid && (!row.created || !row.executable || row.created === owner.created && samePath(row.executable, owner.executable))));
}
export async function inspectProcesses(pids, env, timeout = 2_000) {
  check(pids.length && pids.length <= 32 && pids.every(pid => Number.isSafeInteger(pid) && pid > 0), 'invalid_pid', 'Only observed owned process IDs can be queried.');
  check(process.platform === 'win32', 'windows_only', 'Native Renulus control is Windows only.');
  const filter = pids.map(pid => 'ProcessId = ' + pid).join(' OR ');
  const script = "$ErrorActionPreference='Stop'; $rows=@(Get-CimInstance Win32_Process -Filter '" + filter + "' | ForEach-Object { [pscustomobject]@{ pid=[int]$_.ProcessId; parentPid=[int]$_.ParentProcessId; executable=$_.ExecutablePath; created=$_.CreationDate.ToUniversalTime().ToString('o') } }); ConvertTo-Json -InputObject $rows -Compress";
  const { stdout } = await execFileAsync(path.join(env.SystemRoot ?? env.SYSTEMROOT ?? 'C:\Windows', 'System32/WindowsPowerShell/v1.0/powershell.exe'), ['-NoProfile', '-NonInteractive', '-Command', script], { env, windowsHide: true, timeout: Math.max(1, Math.min(2_000, timeout)), encoding: 'utf8', maxBuffer: 64_000 });
  const result = JSON.parse(stdout.trim() || '[]');
  return Array.isArray(result) ? result : [result];
}

// Only these fixed functions run in our Electron main process. Clients cannot supply code.
function installObservation({ app, BrowserWindow }) {
  const key = '__renulusDevelopmentControl';
  if (globalThis[key]) return;
  const state = { violations: [], seen: 0, watched: new Set(), children: new Map() };
  function violation(kind, id) {
    if (state.violations.length < 64) state.violations.push({ kind, id });
    console.error('RENULUS_CONTROL_VIOLATION ' + JSON.stringify({ kind, id }));
    app.quit();
  }
  function watch(window) {
    if (window.isDestroyed() || state.watched.has(window.id)) return;
    state.watched.add(window.id); state.seen++;
    window.on('show', () => violation('window-shown', window.id));
    window.on('focus', () => violation('window-focused', window.id));
    const preferences = window.webContents.getLastWebPreferences();
    const backgroundThrottling = window.webContents.getBackgroundThrottling();
    console.error('RENULUS_CONTROL_WINDOW ' + JSON.stringify({ id: window.id, visible: window.isVisible(), focused: window.isFocused(), focusable: window.isFocusable(), backgroundThrottling, preferenceBackgroundThrottling: preferences.backgroundThrottling ?? null }));
    if (window.isVisible() || window.isFocused() || window.isFocusable() || backgroundThrottling !== false) violation('unsafe-window', window.id);
  }
  state.watch = watch; globalThis[key] = state;
  app.on('browser-window-created', (_event, window) => watch(window));
  for (const window of BrowserWindow.getAllWindows()) watch(window);
}
function readObservation({ app, BrowserWindow }) {
  const state = globalThis.__renulusDevelopmentControl;
  for (const handle of process._getActiveHandles()) {
    if (handle.constructor.name !== 'ChildProcess' || !handle.pid) continue;
    state.children.set(handle.pid, handle);
  }
  const windows = BrowserWindow.getAllWindows().filter(w => !w.isDestroyed()).map(w => {
    state.watch(w);
    const url = w.webContents.getURL(); const prefs = w.webContents.getLastWebPreferences();
    return { id: w.id, url: url.startsWith('data:') ? 'data:startup' : url.split(/[?#]/)[0], visible: w.isVisible(), focused: w.isFocused(), focusable: w.isFocusable(),
      backgroundThrottling: w.webContents.getBackgroundThrottling(), sandbox: prefs.sandbox, contextIsolation: prefs.contextIsolation, nodeIntegration: prefs.nodeIntegration };
  });
  return { name: app.getName(), pid: process.pid, parentPid: process.ppid, ownerPid: process.env.RENULUS_BACKGROUND_OWNER_PID, executable: process.execPath, background: process.env.RENULUS_BACKGROUND_TEST === '1',
    attachedBackend: !!process.env.RENULUS_BACKEND_URL, profile: process.env.RENULUS_PROFILE, userData: app.getPath('userData'), packaged: app.isPackaged,
    windows, seen: state.seen, violations: state.violations, children: [...state.children.values()].map(handle => {
      const profileIndex = handle.spawnargs?.indexOf('--profile') ?? -1;
      return { pid: handle.pid, executable: handle.spawnfile, profile: profileIndex >= 0 ? handle.spawnargs[profileIndex + 1] : null, exited: handle.exitCode !== null || handle.signalCode !== null };
    }) };
}
function captureHidden(window) { return window.capturePage(undefined, { stayHidden: true, stayAwake: false }).then(image => image.toPNG().toString('base64')); }
async function freshFrame() {
  let timer;
  try {
    await Promise.race([
      (async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); })(),
      new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('The hidden renderer did not produce a fresh frame within five seconds.')), 5_000); }),
    ]);
  } finally { clearTimeout(timer); }
}
function elementDescription(element) {
  return { tag: element.tagName, type: element.getAttribute('type'), hint: [element.getAttribute('name'), element.id, element.getAttribute('aria-label'), element.getAttribute('autocomplete'), element.getAttribute('placeholder')].filter(Boolean).join(' ') };
}

class Budget {
  constructor(timeout, external, reserve) {
    this.deadline = Date.now() + timeout;
    this.reserve = reserve ?? Math.min(timeout / 4, timeout > LIMITS.operation ? LIMITS.lifecycle : 3_000);
    this.abort = new AbortController();
    this.signal = external ? AbortSignal.any([external, this.abort.signal]) : this.abort.signal;
    this.timer = setTimeout(() => this.abort.abort(new ControlError('operation_timeout', 'The operation exceeded its finite action budget.')), timeout - this.reserve);
    this.timer.unref?.();
  }
  left() { return Math.max(1, this.deadline - Date.now()); }
  actionTime() { this.signal.throwIfAborted(); return Math.max(1, this.left() - this.reserve); }
  async wait(promise) {
    if (this.signal.aborted) { Promise.resolve(promise).catch(() => {}); throw this.signal.reason; }
    let stop;
    const cancelled = new Promise((_, reject) => { stop = () => reject(this.signal.reason); this.signal.addEventListener('abort', stop, { once: true }); });
    try { return await Promise.race([promise, cancelled]); } finally { this.signal.removeEventListener('abort', stop); }
  }
  dispose() { clearTimeout(this.timer); }
}
async function bounded(promise, milliseconds, message) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new ControlError('shutdown_timeout', message)), Math.max(1, milliseconds)); })]); }
  finally { clearTimeout(timer); }
}

async function defaultLaunch(options) { const { _electron } = await import('playwright'); return _electron.launch(options); }

export class RenulusController {
  constructor(config, dependencies = {}) {
    this.config = { ...config, repo: absolute(config.repo, '--repo'), ...(config.python ? { python: absolute(config.python, '--python') } : {}), stateRoot: absolute(config.stateRoot ?? path.join(os.tmpdir(), 'rn-c'), '--state-root') };
    check(config.python || config.executable, 'invalid_cli', 'Source mode requires --python; packaged mode uses its fixed bundled interpreter.');
    for (const key of ['executable', 'helperAssets']) if (config[key]) this.config[key] = absolute(config[key], '--' + key);
    this.launch = dependencies.launch ?? defaultLaunch;
    this.preflight = dependencies.preflight ?? launchContract;
    this.inspect = dependencies.inspect ?? inspectProcesses;
    this.kill = dependencies.kill ?? (pid => process.kill(pid, 'SIGKILL'));
    this.operationTimeout = dependencies.operationTimeout ?? LIMITS.operation;
    this.lifecycleTimeout = dependencies.lifecycleTimeout ?? LIMITS.lifecycle;
    this.startTimeout = dependencies.startTimeout ?? LIMITS.start;
    check(this.operationTimeout > 0 && this.operationTimeout <= LIMITS.operation && this.lifecycleTimeout > 0 && this.lifecycleTimeout <= LIMITS.lifecycle && this.startTimeout > 0 && this.startTimeout <= LIMITS.start, 'invalid_timeout', 'Controller bounds cannot exceed 15 seconds for actions, 45 seconds for lifecycle close, or 360 seconds for launch.');
    this.queue = Promise.resolve(); this.lifetime = new AbortController(); this.stopping = false;
    this.application = null; this.page = null; this.pendingLaunch = null; this.owners = []; this.logs = []; this.filled = []; this.launches = []; this.closes = [];
    this.fault = null; this.session = null; this.origin = null; this.observer = null; this.observing = null;
    this.outputSequence = 0; this.backgroundEvents = {};
    this.seenEvents = new Set();
  }
  log(kind, message) {
    this.logs.push({ at: new Date().toISOString(), kind, message: String(redact(message, this.filled)).slice(0, LIMITS.line) });
    if (this.logs.length > LIMITS.logs) this.logs.splice(0, this.logs.length - LIMITS.logs);
  }
  async prepare(signal) {
    if (this.session) return;
    const stateRoot = this.config.stateRoot;
    check(independent(stateRoot, this.config.repo) && (!this.config.python || independent(stateRoot, path.dirname(this.config.python))), 'unsafe_state', 'Controller state must be separate from repository and dependency directories.');
    // Evidence such as the parent's native-* receipts can share a state-root. Only
    // our marked c/ namespace is adopted; it is never an Electron profile input.
    const root = path.join(stateRoot, 'c');
    const personal = [process.env.LOCALAPPDATA, process.env.APPDATA].filter(Boolean).flatMap(base => [path.join(base, 'Renulus'), path.join(base, 'renulus-desktop')]);
    check(!personal.some(profile => inside(profile, stateRoot)), 'unsafe_state', 'A normal personal application profile cannot be selected as the controller state root.');
    await noLinks(root, true); await outsideGit(root);
    check(process.platform !== 'win32' || path.join(root, 's-12345678', 'p').length <= 60, 'long_state_path', 'Use a short state root so the synthetic profile stays within the native helper path bound (60 characters).');
    await mkdir(root, { recursive: true });
    const marker = path.join(root, ROOT_MARKER);
    const entries = await readdir(root);
    if (entries.length === 0) await writeFile(marker, JSON.stringify({ format: 'renulus-control-root-v1', syntheticOnly: true }), { flag: 'wx' });
    else {
      const record = await boundedJson(marker).catch(() => null);
      check(record?.format === 'renulus-control-root-v1' && record.syntheticOnly === true, 'unowned_state', 'An existing directory without a controller ownership marker cannot be adopted. Never select a normal Renulus profile.');
    }
    const directory = path.join(root, 's-' + randomBytes(4).toString('hex'));
    await mkdir(directory);
    this.session = { directory, profile: path.join(directory, 'p'), temporary: path.join(directory, 't'), outputs: path.join(directory, 'out') };
    for (const child of [this.session.profile, this.session.temporary, this.session.outputs]) await mkdir(child);
    await writeFile(path.join(directory, 'session.json'), JSON.stringify({ format: 'renulus-control-session-v1', syntheticOnly: true, profile: this.session.profile }), { flag: 'wx' });
    if (this.config.helperAssets) this.helpers = await seedHelpers(this.config.repo, this.config.helperAssets, this.session.profile, signal);
    this.log('session', 'Created a fresh owned synthetic profile.');
  }
  run(name, args = {}, { signal } = {}) {
    const task = this.queue.then(async () => {
      check(!this.stopping, 'controller_stopping', 'This controller is shutting down.');
      const timeout = name === 'renulus_start' ? this.startTimeout : name === 'renulus_restart' ? this.startTimeout + this.lifecycleTimeout : name === 'renulus_close' ? this.lifecycleTimeout : this.operationTimeout;
      const budget = new Budget(timeout, AbortSignal.any([this.lifetime.signal, ...(signal ? [signal] : [])]), ['renulus_close', 'renulus_start', 'renulus_restart'].includes(name) ? 0 : undefined);
      try {
        budget.signal.throwIfAborted();
        const result = await this.perform(name, args, budget);
        if (name === 'renulus_close') { budget.dispose(); await this.persist(); }
        else await budget.wait(this.persist());
        if (name === 'renulus_screenshot') { const { data, ...metadata } = result; return { ...redact(metadata), data }; }
        return redact(result);
      } catch (error) {
        this.log('operation-error', error?.message ?? 'The operation failed.');
        // Invalid locators/arguments do not end a healthy session; cancellation and
        // uncertain native state do. Closing also interrupts any stale locator action.
        if (name !== 'renulus_close' && error?.code !== 'shutdown_incomplete' && (budget.signal.aborted || this.fault || name === 'renulus_start' || name === 'renulus_restart')) {
          try { await this.closeOwned(this.lifecycleTimeout, 'operation-failed'); }
          catch (closing) { this.log('cleanup-error', closing.message); throw new ControlError('cleanup_failed', 'The operation failed and owned shutdown is incomplete. Inspect the external receipt.'); }
        }
        await this.persist().catch(() => {});
        throw error instanceof ControlError ? error : new ControlError(budget.signal.aborted ? 'operation_cancelled' : 'operation_failed', String(redact(error?.message ?? 'The operation failed.', this.filled)).slice(0, LIMITS.line));
      } finally { budget.dispose(); }
    });
    this.queue = task.catch(() => {});
    return task;
  }
  async perform(name, args, budget) {
    if (name === 'renulus_start') return this.start(budget);
    if (name === 'renulus_restart') {
      await this.closeOwned(this.lifecycleTimeout, 'restart');
      const launchBudget = new Budget(this.startTimeout, budget.signal, 0);
      try { return await this.start(launchBudget); } finally { launchBudget.dispose(); }
    }
    if (name === 'renulus_close') return this.closeOwned(budget.left(), 'requested');
    if (name === 'renulus_errors') {
      const limit = args.limit ?? 100; check(Number.isInteger(limit) && limit >= 1 && limit <= 200, 'invalid_argument', 'Error log limit must be between 1 and 200.');
      if (this.application && !this.fault) await budget.wait(this.observe());
      return { logs: this.logs.slice(-limit), boundedTo: LIMITS.logs, events: this.backgroundEvents, fault: this.fault?.code ?? null, receipt: this.session ? path.join(this.session.outputs, 'receipt.json') : null };
    }
    check(this.application && this.page && !this.fault, 'not_running', 'Start a healthy controller-owned Renulus instance first.');
    await budget.wait(this.observe());
    check(this.page.url().startsWith(this.origin + '/'), 'wrong_page', 'Actions are restricted to the owned loopback Flow page.');
    if (name === 'renulus_snapshot') {
      const snapshot = await budget.wait(this.page.locator('body').ariaSnapshot({ timeout: budget.actionTime(), signal: budget.signal }));
      await budget.wait(this.observe());
      return { url: this.page.url().split(/[?#]/)[0], snapshot: redact(snapshot).slice(0, LIMITS.snapshot), truncated: snapshot.length > LIMITS.snapshot, locator: 'Exact role/name, or pure CSS; every action requires exactly one match.' };
    }
    if (name === 'renulus_screenshot') {
      await budget.wait(bounded(this.page.evaluate(freshFrame), Math.min(5_100, budget.actionTime()), 'Fresh hidden frame preparation exceeded its deadline.'));
      await budget.wait(this.observe());
      const handle = await budget.wait(this.application.browserWindow(this.page));
      let encoded;
      try { encoded = await budget.wait(handle.evaluate(captureHidden)); } finally { await handle.dispose().catch(() => {}); }
      const image = Buffer.from(encoded, 'base64');
      check(image.length > 8 && image.length <= LIMITS.image && image.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'capture_failed', 'The hidden capture was empty, invalid or exceeded its size bound.');
      await budget.wait(this.observe());
      const file = path.join(this.session.outputs, 'capture-' + String(++this.outputSequence).padStart(4, '0') + '.png');
      await budget.wait(writeFile(file, image, { flag: 'wx' }));
      return { file, bytes: image.length, mimeType: 'image/png', stayHidden: true, data: encoded };
    }
    if (name === 'renulus_wait') {
      const state = args.state ?? 'visible', timeoutMs = args.timeoutMs ?? 5_000;
      check(['visible', 'hidden', 'attached', 'detached'].includes(state) && Number.isInteger(timeoutMs) && timeoutMs > 0 && timeoutMs <= 12_000, 'invalid_argument', 'Wait supports a locator state and a timeout from 1 to 12000 ms.');
      const locator = this.buildLocator(args.locator);
      check(await budget.wait(locator.count()) <= 1, 'locator_not_unique', 'Wait requires a unique locator, or a currently absent element.');
      await budget.wait(locator.waitFor({ state, timeout: Math.min(timeoutMs, budget.actionTime()), signal: budget.signal }));
      await budget.wait(this.observe());
      return { state, reached: true };
    }
    check(['renulus_click', 'renulus_fill', 'renulus_press', 'renulus_select'].includes(name), 'unknown_tool', 'This operation is not exposed by the Renulus controller.');
    const locator = await this.uniqueLocator(args.locator, budget);
    const description = await budget.wait(locator.evaluate(elementDescription));
    check(description.type !== 'file', 'native_input_blocked', 'Native file input is disabled in this bounded controller.');
    const input = ['INPUT', 'TEXTAREA', 'SELECT'].includes(description.tag);
    check(!input || description.type !== 'password' && !/(?:password|token|secret|credential|api.?key|account|email|login|authorization|one.?time.?code)/i.test(description.hint), 'credential_input_blocked', 'Account and credential fields are outside the synthetic controller scope.');
    const options = { timeout: budget.actionTime(), signal: budget.signal };
    if (name === 'renulus_click') await budget.wait(locator.click(options));
    if (name === 'renulus_fill') {
      check(typeof args.value === 'string' && args.value.length <= 4_096 && !/(?:\bsk-[\w-]+|\bBearer\s+[\w.-]+)/i.test(args.value), 'invalid_argument', 'Fill accepts up to 4096 characters of synthetic text.');
      this.filled.push(args.value); if (this.filled.length > 100) this.filled.shift();
      await budget.wait(locator.fill(args.value, options));
    }
    if (name === 'renulus_press') {
      check(['Enter', 'Space', 'Escape', 'Tab', 'Shift+Tab', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'Backspace', 'Delete', 'Home', 'End', 'PageUp', 'PageDown', 'Control+A'].includes(args.key), 'invalid_key', 'Only bounded in-page editing/navigation keys are supported.');
      await budget.wait(locator.press(args.key, options));
    }
    if (name === 'renulus_select') {
      check((typeof args.value === 'string') !== (typeof args.label === 'string') && (args.value ?? args.label).length <= 512, 'invalid_argument', 'Select requires exactly one short option value or label.');
      await budget.wait(locator.selectOption(args.label !== undefined ? { label: args.label } : { value: args.value }, options));
    }
    await budget.wait(this.observe());
    return { performed: name, unique: true, hidden: true };
  }
  buildLocator(spec) {
    check(spec && typeof spec === 'object' && !Array.isArray(spec), 'invalid_locator', 'Supply an exact role/name or pure CSS locator.');
    const keys = Object.keys(spec).sort().join(',');
    let locator;
    if (keys === 'name,role') {
      check(typeof spec.role === 'string' && /^[a-z]+$/.test(spec.role) && typeof spec.name === 'string' && spec.name.length <= 512, 'invalid_locator', 'Role and exact accessible name must be strings.');
      locator = this.page.getByRole(spec.role, { name: spec.name, exact: true });
    } else {
      check(keys === 'css' && typeof spec.css === 'string' && spec.css.length > 0 && spec.css.length <= 512 && !/(?:>>|\/\/|:has-text\(|:text|:visible|:nth-match|\u0000)/.test(spec.css), 'invalid_locator', 'Use pure CSS, without selector engines, text extensions or custom code.');
      locator = this.page.locator('css=' + spec.css);
    }
    return locator;
  }
  async uniqueLocator(spec, budget) {
    const locator = this.buildLocator(spec);
    const count = await budget.wait(locator.count());
    check(count === 1, 'locator_not_unique', 'The locator matched ' + count + ' elements; use the current snapshot to select exactly one.');
    return locator;
  }
  async start(budget) {
    check(!this.application && !this.pendingLaunch && !this.owners.length, 'already_running', 'Close the owned app before starting another instance.');
    this.fault = null; this.origin = null;
    await budget.wait(this.prepare(budget.signal));
    const contract = await budget.wait(this.preflight(this.config));
    this.env = isolatedEnvironment(process.env, this.config, this.session);
    const started = Date.now();
    if (this.launch === defaultLaunch) this.captureLaunchLogs();
    // Electron.launch 1.62.1 has no AbortSignal option. Bound handle acquisition
    // separately; backend/Flow readiness has the remaining 360-second budget.
    const pending = this.launch({ executablePath: contract.executable, args: contract.args, cwd: contract.cwd, env: this.env, timeout: Math.min(10_000, budget.actionTime()), artifactsDir: this.session.outputs, acceptDownloads: false, chromiumSandbox: true });
    this.pendingLaunch = pending;
    pending.then(app => { this.application = app; this.pendingLaunch = null; }, () => { this.pendingLaunch = null; });
    this.application = await budget.wait(pending);
    this.attachLogs(this.application);
    await budget.wait(this.application.evaluate(installObservation));
    const context = this.application.context();
    context.setDefaultTimeout(Math.min(this.operationTimeout, 10_000));
    this.attachPages();
    this.observer = setInterval(() => {
      if (!this.observing && this.application && !this.fault) {
        this.observing = this.observe().catch(error => { this.fault = error; this.log('safety-failure', error.message); void this.application?.close().catch(() => {}); }).finally(() => { this.observing = null; });
      }
    }, 150);
    this.observer.unref?.();
    while (true) {
      budget.signal.throwIfAborted();
      await budget.wait(this.observe());
      const pages = this.application.windows().filter(page => !page.isClosed() && isFlowUrl(page.url()));
      check(pages.length <= 1, 'ambiguous_flow', 'More than one Flow page is present in the owned app.');
      if (pages.length === 1) {
        const page = pages[0];
        const navigation = page.getByRole('navigation', { name: 'Main navigation', exact: true });
        if (await budget.wait(navigation.count()) === 1 && await budget.wait(navigation.isVisible())) {
          const origin = new URL(page.url()).origin;
          check(!this.origin || this.origin === origin, 'wrong_page', 'The Flow origin differs from the initially owned renderer origin.');
          this.page = page; this.origin = origin;
          check(this.owners.some(owner => owner.kind === 'backend'), 'backend_unverified', 'The managed backend child must be physically verified before Flow is accepted.');
          await budget.wait(this.observe());
          // The initial navigation can precede its Playwright Frame. The app's
          // own session filter covers startup; add our exact-origin filter only
          // after Flow and its managed backend have been verified.
          await budget.wait(context.route('**/*', async route => {
            try {
              const request = route.request();
              if (requestAllowed(request.url(), request.method(), this.origin)) return await route.continue();
              this.log('request-blocked', request.method() + ' ' + request.url());
              if (isFlowUrl(request.url()) && new URL(request.url()).pathname.startsWith('/api/')) return await route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: { code: 'controller_scope', message: 'This operation is outside the synthetic controller scope.', retryable: false } }) });
              await route.abort('blockedbyclient');
            } catch (error) {
              if (!this.application || this.stopping) return;
              this.log('route-error', error.message);
              this.fault = new ControlError('route_failed', 'The owned renderer request filter failed. Inspect the external logs.');
              void this.application.close().catch(() => {});
            }
          }));
          const receipt = { profile: this.session.profile, mainSha256: contract.mainSha256, readySeconds: (Date.now() - started) / 1_000, origin: this.origin, hidden: true,
            seenWindows: this.lastObservation.seen, ownedPids: this.owners.map(owner => ({ pid: owner.pid, kind: owner.kind })), ownedProcesses: this.owners.map(owner => ({ ...owner })) };
          this.launches.push(receipt); this.log('ready', 'Hidden loopback Flow navigation and owned backend are ready.');
          return { ...receipt, outputs: this.session.outputs, helpers: this.helpers ?? 'No helper seed supplied; development startup needs already provisioned public helpers or --helper-assets.' };
        }
      }
      await budget.wait(delay(100, undefined, { signal: budget.signal }));
    }
  }
  attachLogs(application) {
    const child = application.process();
    this.mainProcess = child;
    for (const [name, stream] of [['main-stderr', child.stderr], ['main-stdout', child.stdout]]) {
      let pending = '';
      stream?.on('data', chunk => {
        pending += chunk.toString('utf8');
        const lines = pending.split(/\r?\n/); pending = lines.pop().slice(-8_192);
        for (const line of lines) this.ingestLog(name, line);
      });
      stream?.on('end', () => { if (pending) this.log(name, pending); });
    }
    application.on('console', message => { if (['error', 'warning', 'warn'].includes(message.type())) this.log('main-console', message.text()); });
  }
  ingestLog(kind, raw) {
    const line = raw.replace(/\x1b\[[0-9;]*m/g, '');
    const match = line.match(/RENULUS_BACKGROUND_EVENT (\{.*\})/);
    if (match) {
      try {
        const event = JSON.parse(match[1]);
        if (!/^[a-z-]{1,64}$/.test(event.kind)) return;
        const identity = canonical(event);
        if (this.seenEvents.has(identity)) return; // PW launch log + owned stderr can overlap.
        this.seenEvents.add(identity); if (this.seenEvents.size > LIMITS.logs) this.seenEvents.delete(this.seenEvents.values().next().value);
        this.backgroundEvents[event.kind] = (this.backgroundEvents[event.kind] ?? 0) + 1;
        if (['window-shown', 'window-focused'].includes(event.kind)) this.fault = new ControlError('visible_window', 'An owned window became visible or focused.');
        if (event.kind === 'error') this.fault = new ControlError('app_error', 'The background app reported an error.');
        this.log('background-event', JSON.stringify(redact(event, this.filled)));
        if (this.fault && this.application) void this.application.close().catch(() => {});
        return;
      } catch { /* A malformed diagnostic remains a bounded redacted log line. */ }
    }
    this.log(kind, line);
  }
  captureLaunchLogs() {
    if (this.restoreLaunchLogs) return;
    // DEBUG=pw:browser is Playwright's documented launch diagnostic channel.
    // Capture it before import/launch so even the first native show/focus event
    // is checked. This dedicated dev stdio process never forwards raw diagnostics.
    const previousDebug = process.env.DEBUG, previousWrite = process.stderr.write;
    process.env.DEBUG = 'pw:browser';
    let pending = '';
    process.stderr.write = (chunk, encoding, callback) => {
      pending += Buffer.isBuffer(chunk) ? chunk.toString('utf8') : String(chunk);
      const lines = pending.split(/\r?\n/); pending = lines.pop().slice(-8_192);
      for (const line of lines) this.ingestLog('launch-stderr', line);
      const complete = typeof encoding === 'function' ? encoding : callback;
      if (complete) queueMicrotask(complete);
      return true;
    };
    this.restoreLaunchLogs = () => {
      if (pending) this.ingestLog('launch-stderr', pending);
      process.stderr.write = previousWrite;
      if (previousDebug === undefined) delete process.env.DEBUG; else process.env.DEBUG = previousDebug;
      this.restoreLaunchLogs = null;
    };
  }
  attachPages() {
    const attach = page => {
      if (page.__renulusControlAttached) return;
      page.__renulusControlAttached = true;
      page.on('console', message => { if (['error', 'warning', 'warn'].includes(message.type())) this.log('renderer-console', message.text()); });
      page.on('pageerror', error => this.log('renderer-error', error.message));
      page.on('filechooser', chooser => {
        // Listener interception covers labels/buttons that programmatically click
        // a file input, as well as direct inputs. Do not leave a chooser pending.
        const cancellation = chooser.setFiles([], { timeout: Math.min(5_000, this.operationTimeout) });
        cancellation.then(() => this.log('filechooser-cancelled', 'The owned app file chooser was cancelled with an empty file list.'), error => {
          this.log('filechooser-error', error.message);
          this.fault = new ControlError('filechooser_cancel_failed', 'The owned file chooser did not complete cancellation.');
          void this.application?.close().catch(() => {});
        });
      });
      page.on('dialog', dialog => { this.log('dialog-blocked', 'An app JavaScript dialog was dismissed.'); void dialog.dismiss().catch(() => {}); });
    };
    this.application.on('window', attach); for (const page of this.application.windows()) attach(page);
  }
  observe() {
    if (!this.observePending) this.observePending = this.observeNow().catch(error => { this.fault = error; throw error; }).finally(() => { this.observePending = null; });
    return this.observePending;
  }
  async observeNow() {
    if (this.fault) throw this.fault;
    const application = this.application;
    check(application, 'not_running', 'There is no owned Electron application.');
    const state = await application.evaluate(readObservation);
    const launcherPid = application.process().pid;
    // Playwright 1.62 launches Electron through cmd.exe on Windows. The owned
    // launcher handle and the real Electron main process have different PIDs.
    const shellLaunch = state.pid !== launcherPid;
    check(state.name === 'Renulus' && Number.isSafeInteger(state.pid) && state.pid > 0 && state.ownerPid === String(process.pid) && state.background && !state.attachedBackend && samePath(state.profile, this.session.profile) && samePath(state.userData, path.join(this.session.profile, 'desktop')), 'ownership_mismatch', 'The launched app does not have the expected synthetic profile, owner/main PID and managed background mode.');
    check(state.violations.length === 0 && state.windows.every(window => !window.visible && !window.focused && !window.focusable && window.backgroundThrottling === false && window.sandbox && window.contextIsolation && !window.nodeIntegration), 'visible_window', 'An owned window was visible, focused or lacked the required background isolation.');
    check(state.packaged === !!this.config.executable, 'ownership_mismatch', 'The launched source/package mode differs from the fixed CLI configuration.');
    for (const child of state.children) check(samePath(child.profile, this.session.profile), 'backend_unverified', 'An unexpected managed child has no controller-owned profile.');
    const expectedBackend = this.config.executable ? path.join(path.dirname(this.config.executable), 'resources/backend/python/python.exe') : this.config.python;
    const launcher = shellLaunch ? [{ pid: launcherPid, executable: path.join(this.env.SystemRoot ?? this.env.SYSTEMROOT ?? 'C:\Windows', 'System32/cmd.exe'), kind: 'launcher' }] : [];
    const fresh = [...launcher, { pid: state.pid, executable: state.executable, kind: 'main' }, ...state.children.map(child => ({ ...child, kind: 'backend' }))].filter(item => !this.owners.some(owner => owner.pid === item.pid));
    if (fresh.length) {
      const rows = await this.inspect(fresh.map(item => item.pid), this.env);
      for (const claim of fresh) {
        const row = rows.find(item => item.pid === claim.pid);
        const expectedExecutable = claim.kind === 'backend' ? expectedBackend : claim.executable;
        const expectedParent = claim.kind === 'launcher' ? process.pid : claim.kind === 'main' ? (shellLaunch ? launcherPid : process.pid) : state.pid;
        check(row?.executable && row.created && samePath(row.executable, expectedExecutable) && row.parentPid === expectedParent && (claim.kind !== 'backend' || samePath(claim.executable, expectedBackend)), 'backend_unverified', 'Physical process identity or managed backend parentage could not be verified.');
        this.owners.push({ ...row, kind: claim.kind });
      }
    }
    check(state.children.filter(child => !child.exited).length <= 1, 'backend_unverified', 'More than one live managed backend child was observed.');
    if (this.page) check(state.children.some(child => !child.exited), 'backend_unverified', 'The owned backend exited while Flow was in use.');
    this.lastObservation = state;
    return state;
  }
  async closeOwned(timeout = LIMITS.lifecycle, reason = 'requested') {
    const deadline = Date.now() + Math.max(1, Math.min(timeout, LIMITS.lifecycle));
    clearInterval(this.observer); this.observer = null;
    if (this.pendingLaunch) await bounded(this.pendingLaunch.catch(() => {}), Math.max(1, deadline - Date.now()), 'A cancelled owned launch did not settle.');
    if (this.observePending) await bounded(this.observePending.catch(() => {}), Math.min(2_000, Math.max(1, deadline - Date.now())), 'Pending observation exceeded the close deadline.');
    const application = this.application;
    if (!application && !this.owners.length) return { closed: true, alreadyClosed: true };
    const receipt = { reason, normal: false, forcedPids: [], remainingPids: [], startedAt: new Date().toISOString() };
    // Official ElectronApplication.close requests app.quit and waits for application exit.
    const closing = application ? application.close() : Promise.resolve();
    let closeFinished = !application, closeError;
    closing.then(() => { closeFinished = true; }, error => { closeError = error; this.log('close-error', error.message); });
    let remaining = [...this.owners];
    let lastRows = [], inspectedAt = 0;
    while (Date.now() < deadline) {
      try {
        if (this.observePending) await bounded(this.observePending.catch(() => {}), Math.min(2_000, Math.max(1, deadline - Date.now())), 'Pending observation exceeded the close deadline.');
        const rows = this.owners.length ? await this.inspect(this.owners.map(owner => owner.pid), this.env, Math.min(2_000, Math.max(1, deadline - Date.now()))) : [];
        lastRows = rows; inspectedAt = Date.now();
        remaining = remainingOwned(this.owners, rows);
        if (closeFinished && !closeError && !remaining.length && (!this.mainProcess || this.mainProcess.exitCode !== null || this.mainProcess.signalCode !== null)) { receipt.normal = true; break; }
      } catch (error) { this.log('close-observation-error', error.message); }
      if (Date.now() < deadline) await delay(Math.min(150, Math.max(1, deadline - Date.now())));
    }
    if (!receipt.normal) {
      // No time is reserved away from normal shutdown. Essential cleanup begins
      // only at the actual lifecycle deadline. Unknown/reused identities are never killed.
      try {
        for (const owner of [...this.owners].reverse()) {
          const row = lastRows.find(item => item.pid === owner.pid);
          if (Date.now() - inspectedAt < 500 && row && row.created === owner.created && samePath(row.executable, owner.executable)) { this.kill(owner.pid); receipt.forcedPids.push(owner.pid); }
        }
        if (application && !this.owners.some(owner => owner.kind === 'main') && this.mainProcess?.exitCode === null && this.mainProcess?.signalCode === null) {
          this.mainProcess.kill('SIGKILL'); receipt.forcedPids.push(this.mainProcess.pid);
        }
      } catch (error) { this.log('cleanup-error', error.message); }
    }
    receipt.remainingPids = remaining.map(owner => owner.pid); receipt.remainingObservedAt = inspectedAt ? new Date(inspectedAt).toISOString() : null; receipt.finishedAt = new Date().toISOString();
    this.closes.push(receipt); this.log('closed', JSON.stringify(receipt));
    if (!remaining.length && (!this.mainProcess || this.mainProcess.exitCode !== null || this.mainProcess.signalCode !== null)) {
      this.application = null; this.page = null; this.owners = []; this.mainProcess = null;
    }
    await this.persist();
    check(receipt.normal, 'shutdown_incomplete', 'Normal owned shutdown failed' + (receipt.remainingPids.length ? '; owned processes survived the normal deadline.' : '; essential cleanup was required.') + ' See the external receipt; forced cleanup is not a normal-close pass.');
    return { closed: true, normal: true, profile: this.session?.profile, receipt: this.session ? path.join(this.session.outputs, 'receipt.json') : null };
  }
  async persist() {
    if (!this.session) return;
    const files = { 'logs.ndjson': this.logs.map(item => JSON.stringify(redact(item, this.filled))).join('\n') + '\n',
      'receipt.json': JSON.stringify(redact({ format: 'renulus-control-receipt-v1', syntheticOnly: true, profile: this.session.profile, launches: this.launches, closes: this.closes, events: this.backgroundEvents, fault: this.fault?.code ?? null }), null, 2) };
    for (const [name, content] of Object.entries(files)) {
      const file = path.join(this.session.outputs, name); await writeFile(file + '.writing', content); await rename(file + '.writing', file);
    }
  }
  shutdown(reason = 'disconnect') {
    if (this.shutdownPromise) return this.shutdownPromise;
    this.stopping = true; this.lifetime.abort(new ControlError('controller_stopping', 'The MCP connection ended; the owned lifecycle is closing.'));
    this.shutdownPromise = this.queue.then(() => this.closeOwned(this.lifecycleTimeout, reason)).finally(() => this.restoreLaunchLogs?.());
    return this.shutdownPromise;
  }
}
