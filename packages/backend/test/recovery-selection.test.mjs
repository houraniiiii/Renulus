// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createHash } from 'node:crypto';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { openTargetFacade } from '../src/http/target.ts';
import { createRecoveryPort } from '../src/host/recovery-select.ts';
import { activateSelectedGeneration, resolveBackendSelection, BACKEND_SELECTOR, GENERATION_MANIFEST } from '../src/host/handoff.ts';
import { sealGeneration, validateCompleteGeneration } from '../src/storage/generation.ts';
import { canonical } from '../src/storage/schema.ts';

const token = 'synthetic-recovery-selection-token';
const hex = char => char.repeat(64);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const header = (generation, authorityEpoch) => ({ profileId: 'synthetic-bf07', generation, authorityEpoch,
  schemaHash: hex('a'), cohortHash: hex('b'), frontierDigest: hex('c') });
const MEMBERS = [
  { role: 'canonical', path: 'state/renulus.sqlite3' }, { role: 'native', path: 'state/harness/opencode.sqlite' },
  { role: 'selector', path: 'state/harness/effective-selector.json' }, { role: 'plugin', path: 'plugins/artifact.json' },
  { role: 'schema', path: 'schema/inventory.json' }, { role: 'original', path: 'originals/o1.bin' },
];
function put(root, path, text) { mkdirSync(dirname(join(root, path)), { recursive: true }); writeFileSync(join(root, path), text); }
function seal(profile, name, generation, epoch, contents = {}) {
  const root = join(profile, 'generations', name);
  for (const member of MEMBERS) put(root, member.path, contents[member.path] ?? `synthetic ${member.path}`);
  return sealGeneration(root, header(generation, epoch), MEMBERS);
}
/** A synthetic selected owner whose native proof matches this very process. */
function selected(t, { epoch = 1 } = {}) {
  const profile = realpathSync(mkdtempSync(join(tmpdir(), 'renulus-bf07-select-')));
  t.after(() => rmSync(profile, { recursive: true, force: true }));
  seal(profile, 'g0', 1, 1);
  return { profile, authority: publish(profile, 'g0', 1, epoch) };
}
function publish(profile, name, generation, epoch, state = 'active') {
  const manifestSha256 = sha(readFileSync(join(profile, 'generations', name, GENERATION_MANIFEST)));
  const selector = { contract: 'renulus-backend-selector/1', profileId: 'synthetic-bf07', generation, authorityEpoch: epoch, writer: 'ts', state,
    generationPath: `generations/${name}`, manifestSha256, schemaHash: hex('a'), cohortHash: hex('b') };
  writeFileSync(join(profile, BACKEND_SELECTOR), canonical(selector));
  const nonce = 'synthetic-nonce', ownerGeneration = '1'.repeat(32);
  writeFileSync(join(profile, '.renulus-profile-owner.json'), JSON.stringify({ generation: ownerGeneration, job_policy: 'kill_on_close_no_breakaway_v1',
    python: { pid: process.ppid, creation_filetime: 1 }, native: [{ process: { pid: process.pid, creation_filetime: 2 } }] }));
  const authority = { contract: 'renulus-selected-writer/1', profileRoot: profile, generationRoot: join(profile, 'generations', name),
    selectorSha256: sha(readFileSync(join(profile, BACKEND_SELECTOR))), authorityEpoch: epoch, ownerGeneration, predecessorGeneration: null,
    ownerReceiptSha256: sha(readFileSync(join(profile, '.renulus-profile-owner.json'))), nodePid: process.pid, nodeCreationFiletime: '2',
    supervisorPid: process.ppid, supervisorCreationFiletime: '1', nonceSha256: sha(nonce) };
  writeFileSync(join(profile, '.renulus-selected-owner.json'), canonical(authority));
  return authority;
}
async function open(t, authority, verifyBinaries = async () => {}) {
  const events = [];
  const facade = await openTargetFacade({ port: 0, token,
    storage: { command: async command => { events.push(command.type); return { records: {}, frontierDigest: hex('c'), schemaHash: hex('a') }; },
      close: async () => { events.push('storage-close'); } },
    settlePlugins: async () => { events.push('plugins-settled'); },
    recovery: createRecoveryPort({ authority, verifyBinaries }) });
  t.after(() => facade.close().catch(() => {}));
  const call = (body, headers = { 'x-renulus-token': token }) => fetch(`http://127.0.0.1:${facade.port}/api/v1/runtime/recovery/select`,
    { method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(5000) });
  const request = (authority, extra = {}) => ({ generation_path: 'generations/g1', expected_owner_generation: authority.ownerGeneration,
    expected_authority_epoch: authority.authorityEpoch, expected_selector_sha256: authority.selectorSha256, ...extra });
  return { facade, events, call, request };
}
const selectorOf = profile => readFileSync(join(profile, BACKEND_SELECTOR), 'utf8');

test('authenticated selection checks expected owner/epoch first, closes admission then publishes the candidate held, last', async t => {
  const { profile, authority } = selected(t); seal(profile, 'g1', 2, 2);
  const { facade, events, call, request } = await open(t, authority);
  assert.equal((await call(request(authority), {})).status, 401);
  const before = selectorOf(profile);
  for (const stale of [{ expected_authority_epoch: 2 }, { expected_owner_generation: '2'.repeat(32) }, { expected_selector_sha256: hex('0') }]) {
    const refused = await call(request(authority, stale));
    assert.equal(refused.status, 409); assert.equal((await refused.json()).error.code, 'recovery_owner_stale');
  }
  assert.equal(selectorOf(profile), before); assert.deepEqual(events, []);   // nothing closed by a refused request
  assert.equal((await fetch(`http://127.0.0.1:${facade.port}/api/v1/runtime/status`, { headers: { 'x-renulus-token': token } }).then(r => r.json())).admission, 'open');
  const response = await call(request(authority));
  assert.equal(response.status, 200);
  const selector = await response.json();
  assert.deepEqual([selector.state, selector.writer, selector.generation, selector.authority_epoch, selector.generation_path],
    ['held', 'ts', 2, 2, 'generations/g1']);
  // Frontier is read before the canonical writer settles; the selector is published only after settlement.
  assert.deepEqual(events, ['recovery.snapshot', 'plugins-settled', 'storage-close']);
  await facade.closed;
  const resolved = resolveBackendSelection(profile);
  assert.equal(resolved.admission, 'held'); assert.equal(resolved.selection.generationPath, 'generations/g1');
  // A later maintenance launch of the new owner is the only thing that may open writes.
  const next = publish(profile, 'g1', 2, 2, 'held');
  const active = await activateSelectedGeneration(next, async () => {});
  assert.equal(active.state, 'active');
});

test('verifier failure or missing/mismatched/incomplete members refuse selection and retain the old owner exactly', async t => {
  for (const [name, damage, verify] of [
    ['binary cohort mismatch', () => {}, async () => { throw new Error('synthetic_cohort_mismatch'); }],
    ['member bytes differ from manifest', profile => writeFileSync(join(profile, 'generations/g1/originals/o1.bin'), 'tampered'), undefined],
    ['member missing', profile => rmSync(join(profile, 'generations/g1/plugins/artifact.json')), undefined],
  ]) {
    const { profile, authority } = selected(t); seal(profile, 'g1', 2, 2); damage(profile);
    const before = selectorOf(profile);
    const { facade, call, request } = await open(t, authority, verify);
    const response = await call(request(authority));
    assert.notEqual(response.status, 200, name);
    assert.equal(selectorOf(profile), before, name);
    assert.equal(resolveBackendSelection(profile).admission, 'active', name);   // old owner retained
    await facade.closed;                                                         // writer already settled: relaunch resumes the old owner
  }
  for (const role of ['native', 'canonical', 'schema', 'plugin']) {
    const { profile } = selected(t);
    const root = join(profile, 'generations/g0');
    const manifest = JSON.parse(readFileSync(join(root, GENERATION_MANIFEST), 'utf8'));
    const incomplete = { ...manifest, members: manifest.members.filter(m => m.role !== role) };
    assert.throws(() => validateCompleteGeneration(incomplete, incomplete.members), { code: 'recovery_generation_incomplete' }, role);
    assert.throws(() => validateCompleteGeneration(manifest, incomplete.members), { code: 'recovery_generation_member_mismatch' }, role);
  }
});

test('crash before publication keeps the old selector; a stray temporary never selects; a second racer is refused', async t => {
  const { profile, authority } = selected(t); seal(profile, 'g1', 2, 2);
  const before = selectorOf(profile);
  writeFileSync(join(profile, '.backend-selector-crashed.tmp'), canonical({ contract: 'renulus-backend-selector/1', writer: 'ts', state: 'active', generationPath: 'generations/g1' }));
  assert.equal(selectorOf(profile), before);
  assert.equal(resolveBackendSelection(profile).selection.generationPath, 'generations/g0');
  const gate = Promise.withResolvers();
  const { facade, call, request } = await open(t, authority, () => gate.promise);
  const first = call(request(authority));
  await new Promise(resolveTimer => setTimeout(resolveTimer, 100));
  const racer = await call(request(authority));
  assert.equal(racer.status, 409); assert.equal((await racer.json()).error.code, 'recovery_selection_in_progress');
  gate.resolve();
  assert.equal((await first).status, 200);
  await facade.closed;
  assert.equal(resolveBackendSelection(profile).admission, 'held');
});

test('rollback is a distinct whole-generation action: complete compatible members and no newer-record loss', async t => {
  const { profile, authority } = selected(t, { epoch: 1 });
  // Current g0 holds newer work than the older backup generation.
  seal(profile, 'old', 2, 2, { 'state/renulus.sqlite3': 'older canonical bytes' });
  const before = selectorOf(profile);
  const refused = await open(t, authority);
  const response = await refused.call(refused.request(authority, { generation_path: 'generations/old', rollback: true }));
  assert.equal(response.status, 409); assert.equal((await response.json()).error.code, 'backend_rollback_newer_work');
  assert.equal(selectorOf(profile), before);
  await refused.facade.closed;
  // A complete compatible generation containing every current member unchanged is accepted.
  const second = selected(t, { epoch: 1 });
  const root = join(second.profile, 'generations/g1');
  for (const member of MEMBERS) { mkdirSync(dirname(join(root, member.path)), { recursive: true }); copyFileSync(join(second.profile, 'generations/g0', member.path), join(root, member.path)); }
  sealGeneration(root, header(2, 2), MEMBERS);
  const accepted = await open(t, second.authority);
  assert.equal((await accepted.call(accepted.request(second.authority, { rollback: true }))).status, 200);
  assert.equal(resolveBackendSelection(second.profile).selection.generation, 2);
  assert.equal(resolve(second.profile), second.profile);
});
