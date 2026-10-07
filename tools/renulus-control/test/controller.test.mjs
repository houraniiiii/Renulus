import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { mkdir, mkdtemp, writeFile, readFile, lstat, symlink } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { RenulusController, parseCli, isolatedEnvironment, requestAllowed, remainingOwned, seedHelpers, launchContract, redact, LIMITS, FIXTURES } from '../controller.mjs';

// All fixtures and receipts are outside Git. No Electron/Python/provider is launched.
const testParent = process.platform === 'win32' ? 'C:/rn-control' : os.tmpdir();
if (!process.env.RENULUS_CONTROL_TEST_ROOT) await mkdir(testParent, { recursive: true });
const root = process.env.RENULUS_CONTROL_TEST_ROOT ?? await mkdtemp(path.join(testParent, 'unit-'));
if (process.env.RENULUS_CONTROL_TEST_ROOT) await mkdir(root); // Fresh evidence only.
let slot = 0;
const png = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), Buffer.from('mock painted frame')]);

async function fixture(overrides = {}) {
  const base = path.join(root, String(++slot)), repo = path.join(base, 'repo'), python = path.join(base, 'runtime/python.exe'), stateRoot = path.join(root, 's' + slot);
  await mkdir(repo, { recursive: true }); await mkdir(path.dirname(python)); await writeFile(python, 'synthetic interpreter placeholder');
  const config = { repo, python, stateRoot };
  if (overrides.fixtures) {
    config.fixtureRoot = path.join(base, 'fixtures'); await mkdir(config.fixtureRoot);
    for (const [name, bytes] of Object.entries(overrides.fixtures)) await writeFile(path.join(config.fixtureRoot, name), bytes);
    await writeFile(path.join(config.fixtureRoot, FIXTURES.marker), JSON.stringify({ format: 'renulus-control-fixtures-v1', syntheticOnly: true,
      files: Object.entries(overrides.fixtures).map(([name, bytes]) => ({ path: name, size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') })) }));
  }
  const calls = [], elements = new Map();
  let options, closed = false, app, applicationNumber = 0;
  const rows = new Map();
  const mainExe = path.join(repo, 'apps/desktop/node_modules/electron/dist/electron.exe');
  const state = { windows: [{ id: 1, url: 'data:startup', visible: false, focused: false, focusable: false, backgroundThrottling: false, sandbox: true, contextIsolation: true, nodeIntegration: false }], seen: 2, violations: [] };
  const fileElement = entry => ({ tagName: entry.tag, type: entry.type, id: entry.id ?? 'synthetic-input', name: entry.hint ?? '', accept: entry.accept ?? '.pdf,.png,.jpg,.jpeg', labels: [{ textContent: entry.label ?? 'Choose a study document' }], matches: () => entry.disabled ?? false, hasAttribute: () => entry.directory ?? false, getAttribute: () => null });
  const getElement = key => {
    if (!elements.has(key)) elements.set(key, { count: 1, tag: 'BUTTON', type: null, hint: '', snapshot: '- heading "Synthetic learning"', visible: true });
    const entry = elements.get(key);
    return {
      count: async () => entry.count,
      isVisible: async () => entry.visible,
      ariaSnapshot: async () => entry.snapshot,
      evaluateAll: async fn => {
        const inputs = key === 'input[type="file"]' ? [...elements.values()].filter(element => element.type === 'file') : Array.from({ length: entry.count }, () => entry);
        return fn(inputs.map(fileElement));
      },
      evaluate: async fn => fn({ tagName: entry.tag, id: '', getAttribute: name => name === 'type' ? entry.type : name === 'aria-label' ? entry.hint : null }),
      setInputFiles: async (payload, opts) => { assert.ok(opts.timeout <= LIMITS.operation); calls.push(['upload', payload]); if (overrides.onUpload) await overrides.onUpload({ payload, state, signal: opts.signal }); },
      click: async () => { calls.push('click:' + key + ':begin'); await delay(5); calls.push('click:' + key + ':end'); },
      fill: async (_value, operation) => { calls.push('fill'); if (overrides.blockFill) await new Promise((_, reject) => operation.signal.addEventListener('abort', () => reject(operation.signal.reason), { once: true })); },
      press: async key => { calls.push('press:' + key); },
      selectOption: async value => { calls.push(['select', value]); },
      waitFor: async ({ state: waitState }) => { calls.push('wait:' + waitState); entry.count = ['detached', 'hidden'].includes(waitState) ? 0 : 1; },
    };
  };
  const page = new EventEmitter();
  page.isClosed = () => closed;
  page.url = () => overrides.earlyNavigation && !calls.includes('observe') ? 'data:startup' : 'http://127.0.0.1:43123/';
  page.locator = selector => getElement(selector);
  page.getByRole = (role, opts) => { assert.equal(opts.exact, true); return getElement(role + ':' + opts.name); };
  page.evaluate = async fn => { calls.push(fn.name); if (overrides.failFrame) throw new Error('No fresh frame'); };
  const launch = async launchOptions => {
    options = launchOptions; closed = false; applicationNumber++;
    app = new EventEmitter();
    const child = { pid: 100 + applicationNumber * 10, exitCode: null, signalCode: null, stderr: new PassThrough(), stdout: new PassThrough(), kill: () => { child.exitCode = 1; calls.push('direct-main-kill'); } };
    const mainPid = overrides.shellLaunch ? child.pid + 1 : child.pid;
    const mainParent = overrides.shellLaunch ? child.pid : process.pid;
    const backendPid = mainPid + 1;
    if (overrides.shellLaunch) rows.set(child.pid, { pid: child.pid, parentPid: overrides.launcherParent ?? process.pid, executable: path.join(launchOptions.env.SystemRoot ?? launchOptions.env.SYSTEMROOT ?? 'C:/Windows', 'System32/cmd.exe'), created: 'synthetic-launcher-' + applicationNumber });
    rows.set(mainPid, { pid: mainPid, parentPid: mainParent, executable: mainExe, created: 'synthetic-main-' + applicationNumber });
    rows.set(backendPid, { pid: backendPid, parentPid: mainPid, executable: python, created: 'synthetic-backend-' + applicationNumber });
    app.process = () => child;
    app.windows = () => [page];
    app.context = () => ({ setDefaultTimeout: timeout => assert.ok(timeout <= LIMITS.operation), route: async (_pattern, handler) => {
      calls.push('route'); app.route = handler;
      if (overrides.earlyNavigation) await handler({ request: () => ({ url: () => 'http://127.0.0.1:43123/', method: () => 'GET', isNavigationRequest: () => true, frame: () => { throw new Error('Navigation frame does not exist yet'); } }), continue: async () => calls.push('early-navigation-continued') });
    } });
    app.evaluate = async fn => {
      if (fn.name === 'installObservation') { calls.push('observer'); return; }
      assert.equal(fn.name, 'readObservation'); calls.push('observe');
      return { name: 'Renulus', pid: mainPid, parentPid: mainParent, ownerPid: String(process.pid), executable: mainExe, background: true, attachedBackend: false, packaged: false, profile: options.env.RENULUS_PROFILE,
        userData: path.join(options.env.RENULUS_PROFILE, 'desktop'), ...state,
        children: [{ pid: backendPid, executable: python, profile: options.env.RENULUS_PROFILE, exited: false }] };
    };
    let windowSize = [1400, 960];
    app.browserWindow = async target => { assert.equal(target, page); return { evaluate: async (fn, arg) => fn({
      isDestroyed: () => closed, isVisible: () => state.windows[0].visible, isFocused: () => state.windows[0].focused, isFocusable: () => state.windows[0].focusable,
      setSize: (width, height, animate) => { assert.equal(animate, false); calls.push(['resize', width, height]); windowSize = overrides.clampResize ? [800, 600] : [width, height]; if (overrides.focusOnResize) state.windows[0].focused = true; },
      getSize: () => windowSize, getContentSize: () => [windowSize[0] - 16, windowSize[1] - 39],
      capturePage: async (rect, opts) => { assert.equal(rect, undefined); assert.equal(opts.stayHidden, true); assert.equal(opts.stayAwake, false); calls.push('capturePage'); return { toPNG: () => png }; },
    }, arg), dispose: async () => { calls.push('dispose'); } }; };
    app.close = async () => {
      calls.push('close'); if (overrides.closeDelay) await delay(overrides.closeDelay);
      closed = true; child.exitCode = 0; rows.delete(child.pid); rows.delete(mainPid);
      if (!overrides.surviveBackend) rows.delete(backendPid);
      else if (overrides.reusePid) rows.set(backendPid, { ...rows.get(backendPid), created: 'unrelated-new-process' });
    };
    return app;
  };
  const controller = new RenulusController(config, { launch, preflight: async () => ({ executable: mainExe, cwd: repo, args: ['.'], mainSha256: 'synthetic-main-hash' }),
    inspect: async pids => pids.map(pid => rows.get(pid)).filter(Boolean), kill: pid => { calls.push('kill:' + pid); if (!overrides.resistKill) rows.delete(pid); },
    operationTimeout: 5_000, lifecycleTimeout: overrides.lifecycleTimeout ?? 1_500, startTimeout: 5_000 });
  return { controller, config, calls, elements, state, rows, options: () => options, app: () => app };
}

test('Windows shell launcher validates controller to cmd to Electron to backend ownership', async t => {
  const f = await fixture({ shellLaunch: true }); t.after(() => f.controller.shutdown());
  const ready = await f.controller.run('renulus_start');
  assert.deepEqual(ready.ownedPids.map(owner => owner.kind), ['launcher', 'main', 'backend']);
  assert.notEqual(ready.ownedPids[0].pid, ready.ownedPids[1].pid);
  assert.equal((await f.controller.run('renulus_close')).normal, true);
  assert.equal(f.rows.size, 0);
});

test('initial Electron navigation needs no unavailable request frame', async t => {
  const f = await fixture({ earlyNavigation: true }); t.after(() => f.controller.shutdown());
  const ready = await f.controller.run('renulus_start');
  assert.equal(ready.hidden, true);
  assert.ok(f.calls.indexOf('route') > f.calls.indexOf('observe'));
  assert.ok(f.calls.includes('early-navigation-continued'));
});

test('Windows shell launcher rejects an unrelated launcher parent', async () => {
  const f = await fixture({ shellLaunch: true, launcherParent: process.pid + 9999 });
  await assert.rejects(f.controller.run('renulus_start'), error => error.code === 'backend_unverified');
  assert.equal(f.rows.size, 0);
});

test('CLI has fixed absolute configuration, packaged Python is optional, and no attach/profile/eval flag', () => {
  const repo = path.join(root, 'repo'), python = path.join(root, 'python.exe'), executable = path.join(root, 'Renulus.exe');
  assert.equal(parseCli(['--repo', repo, '--python', python]).python, python);
  assert.equal(parseCli(['--repo', repo, '--executable', executable]).python, undefined);
  for (const argv of [['--repo', 'relative', '--python', python], ['--repo', repo], ['--repo', repo, '--python', python, '--profile', root], ['--repo', repo, '--python', python, '--repo', repo]]) assert.throws(() => parseCli(argv));
});

test('environment does not inherit accounts, backend attachment or credential directories', () => {
  const env = isolatedEnvironment({ SystemRoot: 'C:\Windows', OPENAI_API_KEY: 'synthetic-do-not-forward', RENULUS_BACKEND_URL: 'http://127.0.0.1:1234', RENULUS_SESSION_TOKEN: 'synthetic-token', USERPROFILE: 'synthetic-private', CODEX_HOME: 'synthetic-account', NODE_OPTIONS: '--eval bad', PATH: 'synthetic-private-bin' }, { python: path.join(root, 'python.exe') }, { profile: path.join(root, 'p'), temporary: path.join(root, 't') });
  for (const key of ['OPENAI_API_KEY', 'RENULUS_BACKEND_URL', 'RENULUS_SESSION_TOKEN', 'USERPROFILE', 'CODEX_HOME', 'NODE_OPTIONS']) assert.equal(env[key], undefined);
  assert.equal(env.RENULUS_BACKGROUND_TEST, '1'); assert.equal(env.HF_HUB_OFFLINE, '1');
  assert.equal(env.RENULUS_BACKGROUND_OWNER_PID, String(process.pid));
});

test('all normal product routes reach exact owned origin; no local mutation or inference firewall', () => {
  const origin = 'http://127.0.0.1:43123';
  for (const [method, route] of [['POST', '/cases/sessions'], ['POST', '/cases/sessions/case_test/save'], ['POST', '/memory/facts'], ['PATCH', '/memory/facts/fact_test'], ['POST', '/learn/threads'], ['PUT', '/study/goals'], ['PATCH', '/study/plan/task_test'], ['GET', '/data/backup'], ['GET', '/data/export'], ['POST', '/data/backup/preview']]) assert.equal(requestAllowed(origin + '/api/v1' + route, method, origin), true, route);
  for (const route of ['/connections/codex/login', '/connections/opencode-go', '/connections/codex/refresh', '/runtime/runs', '/runtime/context/compact', '/learn/ask', '/cases/sessions/case_test/discuss', '/assessment/practice/generate', '/library/import/text', '/retrieval/discover', '/updates/sources/source_test/check', '/memory/captures']) assert.equal(requestAllowed(origin + '/api/v1' + route, 'POST', origin), true, route);
  assert.equal(requestAllowed('https://example.invalid/', 'GET', origin), false);
  assert.equal(requestAllowed('http://127.0.0.1:1234/', 'GET', origin), false);
  assert.equal(requestAllowed(origin + '/api/v2/meta', 'GET', origin), false);
  assert.equal(requestAllowed(origin + '/api/v1/meta', 'GET', null), false);
});

test('start accepts hidden Flow DOM navigation and verifies parent/profile/interpreter ownership', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown());
  const result = await f.controller.run('renulus_start');
  assert.equal(result.hidden, true); assert.equal(result.ownedPids.length, 2);
  assert.equal(f.options().env.RENULUS_BACKGROUND_TEST, '1'); assert.ok(f.options().timeout <= 10_000);
  assert.notEqual(result.profile, f.config.stateRoot); assert.ok(result.profile.startsWith(f.config.stateRoot));
  assert.equal((await f.controller.run('renulus_close')).normal, true);
});

test('new state cannot adopt an existing profile namespace or live inside Git', async () => {
  const f = await fixture(); await mkdir(path.join(f.config.stateRoot, 'c'), { recursive: true }); await writeFile(path.join(f.config.stateRoot, 'c', 'account.json'), 'synthetic private sentinel');
  await assert.rejects(f.controller.run('renulus_start'), { code: 'unowned_state' });
  const g = await fixture(); await mkdir(path.join(g.config.stateRoot, '.git'), { recursive: true });
  await assert.rejects(g.controller.run('renulus_start'), { code: 'state_in_git' });
});

test('visible/focused windows fail closed and invoke owned normal shutdown', async () => {
  const f = await fixture(); f.state.windows[0].focused = true;
  await assert.rejects(f.controller.run('renulus_start'), { code: 'visible_window' });
  assert.ok(f.calls.includes('close')); assert.equal(f.controller.application, null);
});

test('nonunique selectors fail before action; selection stays exact and client code is rejected', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  f.elements.set('button:Duplicate', { count: 2 });
  await assert.rejects(f.controller.run('renulus_click', { locator: { role: 'button', name: 'Duplicate' } }), { code: 'locator_not_unique' });
  await assert.rejects(f.controller.run('renulus_click', { locator: { css: 'button >> text=Other' } }), { code: 'invalid_locator' });
  assert.equal(f.calls.some(call => typeof call === 'string' && call.startsWith('click:button:Duplicate')), false);
  await f.controller.run('renulus_select', { locator: { role: 'combobox', name: 'Topic' }, label: 'Glomerular disease' });
  assert.deepEqual(f.calls.find(call => Array.isArray(call)), ['select', { label: 'Glomerular disease' }]);
});

test('credential/file controls and OS shortcut keys never reach input methods', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  f.elements.set('textbox:Key', { count: 1, tag: 'INPUT', type: 'password', hint: 'API key' });
  f.elements.set('css=input[type=file]', { count: 1, tag: 'INPUT', type: 'file', hint: '' });
  await assert.rejects(f.controller.run('renulus_fill', { locator: { role: 'textbox', name: 'Key' }, value: 'synthetic' }), { code: 'credential_input_blocked' });
  await assert.rejects(f.controller.run('renulus_click', { locator: { css: 'input[type=file]' } }), { code: 'native_input_blocked' });
  await assert.rejects(f.controller.run('renulus_press', { locator: { role: 'textbox', name: 'Synthetic question' }, key: 'Alt+F4' }), { code: 'invalid_key' });
  assert.equal(f.calls.includes('fill'), false); assert.equal(f.calls.includes('press:Alt+F4'), false);
});

test('every existing/new owned page cancels indirect HTML file choosers with no files', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  const existing = f.app().windows()[0], added = new EventEmitter(), selections = [];
  f.app().emit('window', added);
  for (const page of [existing, added]) {
    assert.equal(page.listenerCount('filechooser'), 1);
    page.emit('filechooser', { setFiles: async (files, options) => { selections.push(files); assert.ok(options.timeout <= 5_000); } });
  }
  await Promise.resolve();
  assert.deepEqual(selections, [[], []]);
  assert.equal(f.controller.logs.filter(row => row.kind === 'filechooser-cancelled').length, 2);
});

test('operations serialize; wait supports an initially absent unique async target', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  await Promise.all([f.controller.run('renulus_click', { locator: { role: 'button', name: 'A' } }), f.controller.run('renulus_click', { locator: { role: 'button', name: 'B' } })]);
  assert.ok(f.calls.indexOf('click:button:A:end') < f.calls.indexOf('click:button:B:begin'));
  f.elements.set('heading:New case', { count: 0 });
  assert.equal((await f.controller.run('renulus_wait', { locator: { role: 'heading', name: 'New case' }, state: 'visible', timeoutMs: 500 })).reached, true);
});

test('screenshot prepares a fresh frame, captures only its own hidden BrowserWindow and rechecks state', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start'); f.calls.length = 0;
  f.controller.filled.push('A'); // Binary payloads must never be text-redacted.
  const result = await f.controller.run('renulus_screenshot');
  assert.ok(f.calls.indexOf('freshFrame') < f.calls.indexOf('capturePage'));
  assert.ok(f.calls.lastIndexOf('observe') > f.calls.indexOf('capturePage'));
  assert.equal(result.stayHidden, true); assert.deepEqual(await readFile(result.file), png);
  assert.deepEqual(Buffer.from(result.data, 'base64'), png);
  assert.ok(result.file.startsWith(f.config.stateRoot));
});

test('a fresh-frame failure does not capture stale pixels', async t => {
  const f = await fixture({ failFrame: true }); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  await assert.rejects(f.controller.run('renulus_screenshot'));
  assert.equal(f.calls.includes('capturePage'), false);
});

test('request cancellation interrupts an active input operation and normally closes only the owned app', async () => {
  const f = await fixture({ blockFill: true }); await f.controller.run('renulus_start');
  const abort = new AbortController();
  const pending = f.controller.run('renulus_fill', { locator: { role: 'textbox', name: 'Question' }, value: 'synthetic text' }, { signal: abort.signal });
  while (!f.calls.includes('fill')) await delay(2);
  abort.abort(); await assert.rejects(pending, { code: 'operation_cancelled' });
  assert.equal(f.controller.application, null); assert.equal(f.calls.some(call => typeof call === 'string' && call.startsWith('kill:')), false);
});

test('restart uses the same synthetic profile and a new owned process', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown());
  const first = await f.controller.run('renulus_start'), next = await f.controller.run('renulus_restart');
  assert.equal(next.profile, first.profile); assert.notEqual(next.ownedPids[0].pid, first.ownedPids[0].pid);
});

test('normal close can use the full lifecycle budget without an early forced reserve', async () => {
  const f = await fixture({ closeDelay: 285, lifecycleTimeout: 350 }); await f.controller.run('renulus_start');
  assert.equal((await f.controller.run('renulus_close')).normal, true);
  assert.equal(f.calls.some(call => typeof call === 'string' && call.startsWith('kill:')), false);
});

test('backend survival is a failed close even when application.close resolves; essential kill starts at deadline', async () => {
  const f = await fixture({ surviveBackend: true, resistKill: true, lifecycleTimeout: 200 }); await f.controller.run('renulus_start');
  const started = Date.now(); await assert.rejects(f.controller.run('renulus_close'), { code: 'shutdown_incomplete' });
  assert.ok(Date.now() - started >= 190); assert.ok(f.calls.some(call => typeof call === 'string' && call.startsWith('kill:')));
  const receipt = JSON.parse(await readFile(path.join(f.controller.session.outputs, 'receipt.json'), 'utf8'));
  assert.equal(receipt.closes[0].normal, false); assert.equal(receipt.closes[0].remainingPids.length, 1);
  // Release the synthetic survivor without any real process manipulation.
  f.rows.clear(); await f.controller.shutdown();
});

test('PID reuse does not kill a different process or incorrectly retain ownership', async () => {
  const f = await fixture({ surviveBackend: true, reusePid: true }); await f.controller.run('renulus_start');
  assert.equal((await f.controller.run('renulus_close')).normal, true);
  assert.equal(f.calls.some(call => typeof call === 'string' && call.startsWith('kill:')), false);
  assert.equal(remainingOwned([{ pid: 1, created: 'old', executable: 'old.exe' }], [{ pid: 1, created: 'new', executable: 'old.exe' }]).length, 0);
});

test('bounded error logs redact credentials, emails, URL state and filled values before persistence', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  f.controller.filled.push('synthetic-private-sentinel');
  for (let i = 0; i < 1100; i++) f.controller.log('test', 'row ' + i);
  f.controller.log('test', 'Authorization: Bearer synthetic-key'); f.controller.log('test', 'user@example.invalid https://auth.example.invalid/?state=synthetic-private-sentinel');
  const result = await f.controller.run('renulus_errors', { limit: 200 });
  assert.equal(result.logs.length, 200); assert.equal(f.controller.logs.length, LIMITS.logs);
  const disk = await readFile(path.join(f.controller.session.outputs, 'logs.ndjson'), 'utf8');
  for (const privateValue of ['synthetic-key', 'user@example.invalid', 'synthetic-private-sentinel']) assert.equal(disk.includes(privateValue), false);
  assert.equal(redact({ accountId: 'synthetic-account', safe: 'fine' }).accountId, '[redacted]');
});

async function helperFixture() {
  const base = path.join(root, 'helper-' + (++slot)), repo = path.join(base, 'repo'), source = path.join(base, 'public'), profile = path.join(base, 'p');
  await mkdir(path.join(repo, 'packaging/runtime'), { recursive: true }); await mkdir(source); await mkdir(profile);
  const groups = {};
  for (const group of ['embedding', 'docling', 'ocr']) {
    const bytes = Buffer.from('synthetic public artifact: ' + group), file = group + '.bin';
    await writeFile(path.join(source, file), bytes);
    groups[group] = { revision: 'synthetic-reviewed', source_url: 'https://example.invalid/public', files: [{ path: file, size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') }] };
  }
  const manifest = { version: 1, groups };
  await writeFile(path.join(repo, 'packaging/runtime/helper-assets.json'), JSON.stringify(manifest)); await writeFile(path.join(source, 'manifest.json'), JSON.stringify(manifest));
  return { repo, source, profile, manifest };
}

test('public seeding validates reviewed equality/hashes and never copies undeclared account state', async () => {
  const f = await helperFixture(); await writeFile(path.join(f.source, 'account.json'), 'synthetic-do-not-copy');
  assert.equal((await seedHelpers(f.repo, f.source, f.profile)).files, 3);
  await assert.rejects(lstat(path.join(f.profile, 'helpers/account.json')), { code: 'ENOENT' });
  assert.deepEqual(JSON.parse(await readFile(path.join(f.profile, 'helpers/manifest.json'), 'utf8')), f.manifest);
  const mismatch = await helperFixture(); mismatch.manifest.groups.ocr.revision = 'unreviewed'; await writeFile(path.join(mismatch.source, 'manifest.json'), JSON.stringify(mismatch.manifest));
  await assert.rejects(seedHelpers(mismatch.repo, mismatch.source, mismatch.profile), { code: 'helper_contract_mismatch' });
  const corrupt = await helperFixture(); await writeFile(path.join(corrupt.source, 'ocr.bin'), 'corrupt');
  await assert.rejects(seedHelpers(corrupt.repo, corrupt.source, corrupt.profile), { code: 'helper_integrity' });
});

test('helper staging rejects a Windows junction/symlink escape', async () => {
  const f = await helperFixture(); const outside = path.join(root, 'helper-link-outside-' + (++slot)); await mkdir(outside);
  const linked = path.join(root, 'linked-public-' + (++slot)); await symlink(f.source, linked, process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(seedHelpers(f.repo, linked, f.profile), { code: 'unsafe_path' });
});

test('old source builds fail preflight before Electron can launch', async () => {
  const f = await fixture(); const desktop = path.join(f.config.repo, 'apps/desktop');
  await mkdir(path.join(desktop, 'node_modules/electron/dist'), { recursive: true }); await mkdir(path.join(desktop, 'dist-electron')); await mkdir(path.join(desktop, 'dist'));
  await writeFile(path.join(desktop, 'node_modules/electron/dist/electron.exe'), 'synthetic executable'); await writeFile(path.join(desktop, 'dist/index.html'), 'synthetic renderer');
  await writeFile(path.join(desktop, 'package.json'), JSON.stringify({ name: 'renulus-desktop', main: 'dist-electron/main.cjs' }));
  await writeFile(path.join(desktop, 'dist-electron/main.cjs'), 'window.show();');
  await assert.rejects(launchContract(f.config), { code: 'background_build_required' });
});

const uploadLocator = { css: 'input[type="file"][id="synthetic-input"]' };
const pdf = Buffer.from('%PDF-1.7\nSynthetic educational fixture\n%%EOF');
async function uploadFixture(t, overrides = {}) {
  const f = await fixture({ fixtures: { 'synthetic-study.pdf': pdf, 'synthetic-image.png': png }, ...overrides });
  t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  f.elements.set('css=' + uploadLocator.css, { count: 1, tag: 'INPUT', type: 'file' });
  return f;
}

test('upload requires observed exact input and passes only verified bytes to Playwright', async t => {
  const f = await uploadFixture(t);
  await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }), { code: 'unobserved_file_input' });
  const snapshot = await f.controller.run('renulus_snapshot');
  assert.deepEqual(snapshot.fileInputs[0].locator, uploadLocator);
  const result = await f.controller.run('renulus_upload', { locator: snapshot.fileInputs[0].locator, fixture: 'synthetic-study.pdf' });
  assert.equal(result.bytes, pdf.length); assert.equal(result.mimeType, 'application/pdf'); assert.equal(result.hidden, true);
  assert.deepEqual(f.calls.find(call => Array.isArray(call) && call[0] === 'upload')[1], { name: 'synthetic-study.pdf', mimeType: 'application/pdf', buffer: pdf });
  await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-image.png' }), { code: 'unobserved_file_input' });
  await f.controller.run('renulus_snapshot');
  assert.equal((await f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-image.png' })).mimeType, 'image/png');
  const receipt = await readFile(path.join(f.controller.session.outputs, 'logs.ndjson'), 'utf8');
  assert.ok(receipt.includes('fixture-upload')); assert.equal(receipt.includes('Synthetic educational fixture'), false);
});

test('upload stays disabled without a fixed CLI root and rejects unobserved or extra arguments', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start');
  await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }), { code: 'uploads_disabled' });
  const g = await uploadFixture(t); await g.controller.run('renulus_snapshot');
  await assert.rejects(g.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf', profile: 'other' }), { code: 'invalid_argument' });
  await assert.rejects(g.controller.run('renulus_upload', { locator: { css: 'input' }, fixture: 'synthetic-study.pdf' }), { code: 'unobserved_file_input' });
});

test('upload refuses stale, duplicate, disabled, directory, credential and backup inputs', async t => {
  const f = await uploadFixture(t), entry = f.elements.get('css=' + uploadLocator.css);
  for (const changes of [{ count: 2 }, { disabled: true }, { directory: true }, { type: 'password' }, { hint: 'api-key' }, { label: 'Choose ZIP backup or JSON export' }]) {
    await f.controller.run('renulus_snapshot'); Object.assign(entry, changes);
    await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }));
    for (const key of Object.keys(changes)) delete entry[key]; Object.assign(entry, { count: 1, tag: 'INPUT', type: 'file' });
  }
  for (const changes of [{ directory: true }, { hint: 'account' }, { label: 'Choose ZIP backup or JSON export' }]) {
    Object.assign(entry, changes);
    assert.deepEqual((await f.controller.run('renulus_snapshot')).fileInputs, []);
    for (const key of Object.keys(changes)) delete entry[key];
  }
  assert.equal(f.calls.some(call => Array.isArray(call) && call[0] === 'upload'), false);
});

test('image-only case inputs refuse PDFs and accept a declared image without opening a chooser', async t => {
  const f = await uploadFixture(t);
  Object.assign(f.elements.get('css=' + uploadLocator.css), { label: 'Image to keep in case', accept: '.png,.jpg,.jpeg' });
  await f.controller.run('renulus_snapshot');
  await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }), { code: 'file_type_not_accepted' });
  assert.equal((await f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-image.png' })).hidden, true);
  assert.equal(f.app().windows()[0].listenerCount('filechooser'), 1);
  assert.equal(f.controller.logs.some(log => log.kind === 'filechooser-cancelled'), false);
});

test('upload rejects a changed fixture and post-action visibility fails closed', async t => {
  const f = await uploadFixture(t); await f.controller.run('renulus_snapshot');
  await writeFile(path.join(f.config.fixtureRoot, 'synthetic-study.pdf'), Buffer.alloc(pdf.length, 65));
  await assert.rejects(f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }), { code: 'fixture_integrity' });
  assert.equal(f.calls.some(call => Array.isArray(call) && call[0] === 'upload'), false);
  const g = await uploadFixture(t, { onUpload: async ({ state }) => { state.windows[0].visible = true; } });
  await g.controller.run('renulus_snapshot');
  await assert.rejects(g.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }), { code: 'visible_window' });
  assert.equal(g.controller.application, null);
});

test('resize targets only the owned page, preserves hidden state and returns measured dimensions', async t => {
  const f = await fixture(); t.after(() => f.controller.shutdown()); await f.controller.run('renulus_start'); f.calls.length = 0;
  const result = await f.controller.run('renulus_resize', { width: 640, height: 540 });
  assert.deepEqual(result, { performed: 'renulus_resize', width: 640, height: 540, contentWidth: 624, contentHeight: 501, hidden: true });
  const resizeIndex = f.calls.findIndex(call => Array.isArray(call) && call[0] === 'resize');
  assert.ok(f.calls.indexOf('observe') < resizeIndex); assert.ok(f.calls.lastIndexOf('observe') > resizeIndex); assert.ok(f.calls.includes('dispose'));
  for (const args of [{ width: 639, height: 540 }, { width: 640, height: 1601 }, { width: 640.5, height: 540 }, { width: 640, height: 540, show: false }]) await assert.rejects(f.controller.run('renulus_resize', args), { code: 'invalid_argument' });
  assert.equal(f.calls.filter(call => Array.isArray(call) && call[0] === 'resize').length, 1);
});

test('cancelling an active file selection aborts Playwright and closes only the owned lifecycle', async t => {
  const abort = new AbortController(); let reached;
  const started = new Promise(resolve => { reached = resolve; });
  const f = await uploadFixture(t, { onUpload: ({ signal }) => new Promise((_, reject) => { signal.addEventListener('abort', () => reject(signal.reason), { once: true }); reached(); }) });
  await f.controller.run('renulus_snapshot');
  const pending = f.controller.run('renulus_upload', { locator: uploadLocator, fixture: 'synthetic-study.pdf' }, { signal: abort.signal });
  await started; abort.abort();
  await assert.rejects(pending, { code: 'operation_cancelled' });
  assert.equal(f.controller.application, null);
  assert.equal(f.calls.some(call => typeof call === 'string' && call.startsWith('kill:')), false);
});

test('a focused resize closes the owned lifecycle; native clamping never reports requested-size success', async t => {
  const f = await fixture({ focusOnResize: true }); await f.controller.run('renulus_start');
  await assert.rejects(f.controller.run('renulus_resize', { width: 640, height: 540 }), { code: 'visible_window' });
  assert.equal(f.controller.application, null);
  const g = await fixture({ clampResize: true }); t.after(() => g.controller.shutdown()); await g.controller.run('renulus_start');
  await assert.rejects(g.controller.run('renulus_resize', { width: 640, height: 540 }), { code: 'resize_not_applied' });
  assert.ok(g.controller.application); assert.ok(g.calls.includes('dispose'));
});
