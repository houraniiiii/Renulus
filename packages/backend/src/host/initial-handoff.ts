// SPDX-License-Identifier: MIT
/** BF08 profile-wide Python -> TS authority handoff and its rollback. Runs only in a maintenance launch under
 * the native profile supervisor (`python -m renulus.workers.profile_owner --maintenance`), whose profile mutex
 * proves that the application, its hosts and workers are closed. The original Python profile is never written:
 * apply builds a NEW prepared generation and publishes the selector (`writer=ts, state=held`) last. */
import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import { constants, copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import path, { join, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import { promisify } from 'node:util';
import { DatabaseSync } from 'node:sqlite';
import { owned } from '../storage/ownership.ts';
import { reject } from '../storage/contracts.ts';
import { canonical, loadMigrationInventory, quote, rows } from '../storage/schema.ts';
import { previewStorage } from '../storage/index.ts';
import { recoveryFrontierDigest } from '../storage/recovery.ts';
import { sealGeneration, stateMarker, type GenerationMember } from '../storage/generation.ts';
import { verifySelectedAuthority, type SelectedWriterAuthority } from '../storage/selected-owner.ts';
import { SOURCE, verifyPreparedProfile, type ProfileSelection } from '../../../harness/src/manifest.ts';
import { activateSelectedGeneration, GENERATION_MANIFEST, resolveBackendSelection, retireSelection, retiredSelectorEpoch,
  selectPreparedGeneration, type HandoffGeneration, type HandoffOptions } from './handoff.ts';

export interface HandoffEnvironment {
  authority: SelectedWriterAuthority;
  /** Bundled Python and source tree: only `packaging/backend_migration.py` runs, never a service. */
  python: string; sourceRoot: string;
  verifyBinaries: HandoffOptions['verifyBinaries'];
  cohortHash: string;
}
const CANONICAL = 'state/renulus.sqlite3', NATIVE = 'state/harness/opencode.sqlite', PAIRED = 'state/harness/manifest.json';
const RECORD = 'schema/inventory.json', PLUGINS = 'plugins/inventory.json';
/** Same suffixes as runtime/renulus/workers/knowledge_io.py: a TS original handle is `original_<sha256(id:sha256)>` and its file is handle+suffix. */
const SUFFIX: Record<string, string> = { 'text/plain': '.txt', 'text/markdown': '.md', 'text/csv': '.csv', 'text/html': '.html',
  'application/xml': '.xml', 'text/xml': '.xml', 'application/pdf': '.pdf', 'image/png': '.png', 'image/jpeg': '.jpg', 'image/tiff': '.tiff',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx' };
/** The only value a TS open writes without a user action (measured): the TS-only Updates cancellation fence that
 * `updates.recover` advances; Python never reads it. Every other row, including grants, revocations and deletions,
 * is newer work that a rollback to Python would lose. */
const MACHINE_LOCAL_PREFERENCES = ['updates.cancel_revision'];
const sha = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
const posix = (value: string) => value.split(sep).join('/');
const fileSha = (file: string) => sha(readFileSync(file));

function identityOf(authority: SelectedWriterAuthority): Omit<ProfileSelection, 'root'> {
  // verifySelectedAuthority binds these exact receipt bytes to the live supervisor's scope.
  const bytes = readFileSync(owned(authority.profileRoot, join(authority.profileRoot, '.renulus-profile-owner.json')));
  if (sha(bytes) !== authority.ownerReceiptSha256) reject('selected_owner_native_proof_changed');
  const receipt = JSON.parse(bytes.toString('utf8'));
  return { profileId: receipt.profile_id, domainStoreId: receipt.domain_store_id, storeId: receipt.runtime_store_id, domainPath: CANONICAL };
}
/** No hot journal or unflushed WAL: the closed Python profile is a complete snapshot as it stands. */
function settled(file: string) {
  for (const suffix of ['-wal', '-journal']) if (existsSync(file + suffix) && statSync(file + suffix).size) reject('handoff_source_not_settled');
}
const immutable = (file: string) => new DatabaseSync(new URL(pathToFileURL(file).href + '?mode=ro&immutable=1'), { readOnly: true });
const hasTable = (db: DatabaseSync, name: string) => rows(db, "SELECT name FROM sqlite_master WHERE type='table' AND name=?", name).length === 1;
function member(root: string, role: GenerationMember['role'], file: string): GenerationMember {
  const stat = lstatSync(file);
  if (!stat.isFile() || stat.nlink !== 1) reject('handoff_member_unowned');
  return { role, path: posix(relative(root, file)), sha256: fileSha(file), bytes: stat.size };
}

interface SourceOriginal { table: 'knowledge_revisions' | 'knowledge_attachment_originals'; id: string; sha256: string; bytes: number; path: string; handle: string; file: string }
/** Closed Python-owned profile: canonical store, native store when present, and every referenced original. Read-only. */
async function snapshotSource(root: string, identity: Omit<ProfileSelection, 'root'>) {
  const database = owned(root, join(root, CANONICAL));
  if (!existsSync(database)) reject('handoff_source_missing');
  settled(database);
  const members = [member(root, 'canonical', database)];
  const originals: SourceOriginal[] = [];
  const db = immutable(database);
  try {
    if (hasTable(db, 'knowledge_index_original_publications') && rows(db, 'SELECT 1 FROM knowledge_index_original_publications LIMIT 1').length)
      reject('handoff_source_publication_debt');
    const select = [hasTable(db, 'knowledge_revisions') ? rows(db, "SELECT 'knowledge_revisions' AS t,id,sha256,bytes,media_type,'original' AS role,original_path FROM knowledge_revisions WHERE original_path IS NOT NULL") : [],
      hasTable(db, 'knowledge_attachment_originals') ? rows(db, "SELECT 'knowledge_attachment_originals' AS t,o.id,o.sha256,o.bytes,a.media_type,o.role,o.original_path FROM knowledge_attachment_originals o JOIN knowledge_attachments a ON a.id=o.attachment_id WHERE o.original_path IS NOT NULL") : []].flat();
    for (const row of select) {
      const source = String(row.original_path), suffix = SUFFIX[String(row.media_type)];
      if (row.role !== 'original') reject('handoff_original_role_unsupported');
      if (!suffix) reject('handoff_original_media_unknown');
      if (!path.isAbsolute(source) || relative(root, source).split(sep)[0] === 'generations') reject('handoff_original_path_invalid');
      const file = owned(root, resolve(source));
      if (!existsSync(file)) reject('handoff_original_missing');
      const observed = member(root, 'original', file);
      if (observed.sha256 !== row.sha256 || observed.bytes !== row.bytes) reject('handoff_original_changed');
      members.push(observed);
      const handle = 'original_' + sha(String(row.id) + ':' + String(row.sha256));
      originals.push({ table: row.t as SourceOriginal['table'], id: String(row.id), sha256: String(row.sha256), bytes: Number(row.bytes), path: file,
        handle, file: handle + suffix });
    }
  } finally { db.close(); }
  const native = owned(root, join(root, NATIVE));
  const nativePresent = existsSync(native);
  if (nativePresent) {
    settled(native);
    await verifyPreparedProfile({ root, ...identity });   // read-only identity of the Python-owned paired selection
    members.push(member(root, 'native', native));
  }
  return { members, originals, nativePresent, marker: stateMarker(members) };
}

function migrationTool(env: HandoffEnvironment, args: string[]) {
  const environment: NodeJS.ProcessEnv = { PATH: path.dirname(env.python), PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1' };
  for (const key of ['SystemRoot', 'WINDIR', 'TEMP', 'TMP']) if (process.env[key]) environment[key] = process.env[key];
  return promisify(execFile)(env.python, ['-I', '-B', '-X', 'utf8', join(env.sourceRoot, 'packaging', 'backend_migration.py'),
    '--source', env.sourceRoot, ...args], { env: environment, windowsHide: true, maxBuffer: 64 * 1024 * 1024 })
    .then(({ stdout }) => JSON.parse(stdout.trim().split('\n').at(-1)!) as { schemaVersion: number; tables: Record<string, number>;
      migrations: { name: string; checksum: string }[]; pendingMigrations: string[]; sourceSha256: string },
    (error: { stderr?: string }) => reject(/(?:ValueError|RuntimeError): ([a-z0-9_]+)\s*$/.exec(error.stderr ?? '')?.[1] ?? 'handoff_migration_failed'));
}
function contracts(env: HandoffEnvironment) {
  return { migrationToolSha256: fileSha(join(env.sourceRoot, 'packaging', 'backend_migration.py')),
    migrationInventorySha256: sha(canonical(loadMigrationInventory(env.sourceRoot))) };
}
/** Read-only, order-independent content digest of every canonical table (newer-work detection for rollback). */
function recordDigests(file: string) {
  const db = immutable(file);
  try {
    return Object.fromEntries(rows(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").map(({ name }) =>
      [String(name), sha(canonical(rows(db, `SELECT * FROM ${quote(String(name))}`)
        .filter(row => name !== 'preferences' || !MACHINE_LOCAL_PREFERENCES.includes(String(row.key))).map(row => canonical(row)).sort()))]));
  } finally { db.close(); }
}
function nativeDigest(file: string) {
  const db = immutable(file);
  try {
    return sha(canonical({ sessions: rows(db, 'SELECT id FROM session_v2 ORDER BY id').map(r => String(r.id)),
      messages: rows(db, 'SELECT id,session_id,data FROM session_message ORDER BY id').map(r => canonical(r)) }));
  } finally { db.close(); }
}
/** A killed owner may leave a WAL or hot journal; replay it into its own store before any read. */
function settleStore(file: string) {
  if (!['-wal', '-journal'].some(suffix => existsSync(file + suffix))) return;
  const db = new DatabaseSync(file, { timeout: 15000 });
  try { db.exec('PRAGMA wal_checkpoint(TRUNCATE)'); } finally { db.close(); }
}

function requireInitial(authority: SelectedWriterAuthority) {
  verifySelectedAuthority(authority);
  const current = resolveBackendSelection(authority.profileRoot);
  if (current.selection || authority.selectorSha256 !== null || authority.generationRoot !== authority.profileRoot) reject('handoff_selector_exists');
}

/** Read-only populated migration preview of the closed Python profile (schema 1 or 2), with source/contract hashes. */
export async function previewHandoff(env: HandoffEnvironment) {
  requireInitial(env.authority);
  const root = env.authority.profileRoot, identity = identityOf(env.authority);
  const source = await snapshotSource(root, identity);
  const migration = await migrationTool(env, ['--database', join(root, CANONICAL)]);
  if (migration.sourceSha256 !== source.members[0]!.sha256) reject('handoff_source_changed');
  return { profileId: identity.profileId, schemaVersion: migration.schemaVersion, tables: migration.tables, migrations: migration.migrations,
    pendingMigrations: migration.pendingMigrations, sourceSha256: migration.sourceSha256, sourceMarker: source.marker,
    nativeStore: source.nativePresent, originals: source.originals.length, contracts: contracts(env) };
}

function nextGeneration(root: string) {
  const directory = owned(root, join(root, 'generations'));
  const used = existsSync(directory) ? readdirSync(directory).map(name => /^g([0-9]{1,9})$/.exec(name)?.[1]).filter(Boolean).map(Number) : [];
  return Math.max(0, ...used) + 1;
}
function writeMember(root: string, file: string, value: unknown) {
  const target = owned(root, join(root, file));
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, canonical(value), { flag: 'wx' });
}

/** Builds generations/g<N> from the closed Python profile, seals it and publishes `writer=ts, state=held` last. */
export async function applyHandoff(env: HandoffEnvironment, expectedSourceSha256: string) {
  requireInitial(env.authority);
  const { authority } = env, root = authority.profileRoot, identity = identityOf(authority);
  const source = await snapshotSource(root, identity);
  if (source.members[0]!.sha256 !== expectedSourceSha256) reject('handoff_source_changed');
  const number = nextGeneration(root), name = 'g' + number;
  mkdirSync(owned(root, join(root, 'generations')), { recursive: true });
  const generation = owned(root, join(root, 'generations', name));
  mkdirSync(generation);   // exclusive: a crashed earlier candidate is never reused
  const database = join(generation, CANONICAL);
  const migrated = await migrationTool(env, ['--database', join(root, CANONICAL), '--target', database, '--expected-sha256', expectedSourceSha256]);
  if (migrated.pendingMigrations.length) reject('handoff_migration_incomplete');
  // Originals move to the TS native originals root under their content handles; the canonical rows follow.
  mkdirSync(join(generation, 'originals'));
  for (const original of source.originals) {
    const target = join(generation, 'originals', original.file);
    if (!existsSync(target)) copyFileSync(original.path, target, constants.COPYFILE_EXCL);
    if (fileSha(target) !== original.sha256) reject('handoff_original_changed');
  }
  const db = new DatabaseSync(database, { timeout: 15000, enableForeignKeyConstraints: true, allowExtension: false });
  try {
    db.exec('PRAGMA foreign_keys=ON; PRAGMA secure_delete=ON; BEGIN IMMEDIATE');
    try {
      // Same domain-store binding the Python activation performs (runtime/harness_activation.py).
      const bound = rows(db, 'SELECT profile_id,store_id,snapshot_generation,cohort_source FROM harness_store_identity WHERE singleton=1');
      const expected = { profile_id: identity.profileId, store_id: identity.domainStoreId, snapshot_generation: 1, cohort_source: SOURCE };
      if (bound.length && canonical(bound[0]) !== canonical(expected)) reject('harness_store_identity_mismatch');
      if (!bound.length) db.prepare('INSERT INTO harness_store_identity VALUES(1,?,?,1,?)').run(identity.profileId, identity.domainStoreId, SOURCE);
      for (const original of source.originals)
        if (db.prepare(`UPDATE ${quote(original.table)} SET original_path=? WHERE id=? AND sha256=? AND bytes=?`)
          .run(original.handle, original.id, original.sha256, original.bytes).changes !== 1) reject('handoff_original_changed');
      db.exec('COMMIT');
    } catch (error) { db.exec('ROLLBACK'); throw error; }
    db.exec('PRAGMA wal_checkpoint(TRUNCATE)');
  } finally { db.close(); }
  mkdirSync(join(generation, 'state', 'harness'), { recursive: true });
  const selection = { root: generation, ...identity };
  if (source.nativePresent) {
    copyFileSync(join(root, NATIVE), join(generation, NATIVE), constants.COPYFILE_EXCL);
    copyFileSync(join(root, PAIRED), join(generation, PAIRED), constants.COPYFILE_EXCL);
  } else {
    // A profile that never activated the native store receives a fresh one through the native owner itself.
    writeFileSync(join(generation, PAIRED), JSON.stringify({ contract_version: 'harness/1', profile_id: identity.profileId, snapshot_generation: 1,
      cohort_source: SOURCE, state: 'prepared',
      domain_store: { store_id: identity.domainStoreId, engine: 'renulus-sqlite', schema_version: 2, generation: 1, path: CANONICAL, validation: 'pending' },
      runtime_store: { store_id: identity.storeId, engine: { name: 'opencode', version: '2.0.26', source_commit: SOURCE },
        schema_version: 'source:' + SOURCE, generation: 1, path: NATIVE, validation: 'pending' } }, null, 2) + '\n', { flag: 'wx' });
    const { openHarness } = await import('../../../harness/src/host.ts');
    const host = await openHarness(selection);
    try { await host.activateStores(); } finally { await host.close(); }
    settleStore(join(generation, NATIVE));
  }
  await verifyPreparedProfile(selection);
  const preview = await previewStorage({ databasePath: database, migrations: loadMigrationInventory(env.sourceRoot) });
  if (!preview.compatible) reject(preview.issues[0] ?? 'handoff_schema_incompatible');
  const frontier = immutable(database);
  let frontierDigest: string;
  try { frontierDigest = recoveryFrontierDigest(frontier); } finally { frontier.close(); }
  writeMember(generation, PLUGINS, { contract: 'renulus-handoff-plugins/1', cohort: SOURCE, artifacts: [] });
  writeMember(generation, RECORD, { contract: 'renulus-handoff-record/1', schemaHash: preview.schemaHash, identity,
    migrations: preview.migrations, tables: Object.fromEntries(preview.tables.map(t => [t.name, t.rowCount])),
    source: { schemaVersion: migrated.schemaVersion, sourceSha256: expectedSourceSha256, marker: source.marker, members: source.members, nativeStore: source.nativePresent },
    contracts: contracts(env), records: recordDigests(database), native: nativeDigest(join(generation, NATIVE)),
    originals: source.originals.map(o => o.file).sort() });
  const manifest = sealGeneration(generation, { profileId: identity.profileId, generation: number,
    authorityEpoch: retiredSelectorEpoch(root) + 1, schemaHash: preview.schemaHash, cohortHash: env.cohortHash, frontierDigest,
    sourceMarker: source.marker }, [
    { role: 'canonical', path: CANONICAL }, { role: 'native', path: NATIVE }, { role: 'selector', path: PAIRED },
    { role: 'plugin', path: PLUGINS }, { role: 'schema', path: RECORD },
    ...source.originals.map(o => ({ role: 'original' as const, path: 'originals/' + o.file }))]) as HandoffGeneration;
  const selector = await selectPreparedGeneration({ authority, generationRoot: generation, manifest, writer: 'ts', verifyBinaries: env.verifyBinaries,
    // The Python profile is re-observed: any change since preparation makes the candidate stale.
    closeAndSnapshot: async () => ({ ...manifest, members: (await snapshotSource(root, identity)).members }) });
  return { selector, generationPath: 'generations/' + name, sourceSha256: expectedSourceSha256, schemaVersion: migrated.schemaVersion };
}

/** A separate maintenance launch flips the held selection to active; it starts no worker or provider. */
export async function activateHandoff(env: HandoffEnvironment) {
  return activateSelectedGeneration(env.authority, async selection => {
    if (selection.writer !== 'ts') reject('backend_activation_stale');
    await env.verifyBinaries(selection.writer, selection.schemaHash, selection.cohortHash);
  });
}

/** Returns authority to the untouched Python profile. Only a selection produced by the initial handoff
 * qualifies; refused (selector unchanged) whenever the TS generation holds newer work, including deletions
 * and grant revocations, which the Python profile could not reproduce. */
export async function rollbackToPython(env: HandoffEnvironment) {
  const { authority } = env;
  verifySelectedAuthority(authority);
  const root = authority.profileRoot, current = resolveBackendSelection(root);
  if (!current.selection || current.writer !== 'ts' || current.selectorSha256 !== authority.selectorSha256 ||
      current.profileRoot !== authority.generationRoot) reject('backend_rollback_stale');
  const generation = current.profileRoot;
  const manifest = JSON.parse(readFileSync(owned(generation, join(generation, GENERATION_MANIFEST)), 'utf8')) as HandoffGeneration;
  const sealed = manifest.members.find(m => m.role === 'schema' && m.path === RECORD);
  const recordFile = owned(generation, join(generation, RECORD));
  if (!sealed || !existsSync(recordFile) || fileSha(recordFile) !== sealed.sha256) reject('backend_rollback_no_python_generation');
  const record = JSON.parse(readFileSync(recordFile, 'utf8'));
  if (record.contract !== 'renulus-handoff-record/1' || !record.source) reject('backend_rollback_no_python_generation');
  // The complete compatible previous generation is the Python profile exactly as it was handed off.
  const source = await snapshotSource(root, identityOf(authority));
  if (source.marker !== record.source.marker) reject('backend_rollback_python_changed');
  // Settlement: the supervisor's mutex proves no live owner; replay what a killed one left, then compare.
  const database = owned(generation, join(generation, CANONICAL)), native = owned(generation, join(generation, NATIVE));
  settleStore(database); settleStore(native);
  const digests = recordDigests(database);
  const changed = [...new Set([...Object.keys(record.records), ...Object.keys(digests)])]
    .filter(table => record.records[table] !== digests[table]);
  // Originals are user files too (the Reader can open one in its associated app): exact sealed bytes, nothing extra.
  const originals = readdirSync(join(generation, 'originals')).sort();
  const sealedOriginals = new Map(manifest.members.filter(m => m.role === 'original').map(m => [m.path, m]));
  const editedOriginal = canonical(originals) !== canonical(record.originals) || originals.some(name => {
    const sealedMember = sealedOriginals.get('originals/' + name), observed = member(generation, 'original', owned(generation, join(generation, 'originals', name)));
    return !sealedMember || observed.sha256 !== sealedMember.sha256 || observed.bytes !== sealedMember.bytes;
  });
  if (changed.length || nativeDigest(native) !== record.native || editedOriginal)
    reject('backend_rollback_newer_work', changed.join(',') || (editedOriginal ? 'originals' : 'native'));
  await env.verifyBinaries('python', current.selection.schemaHash, current.selection.cohortHash);
  retireSelection(authority);
  return { writer: 'python' as const, retiredEpoch: current.selection.authorityEpoch, generationPath: current.selection.generationPath };
}

/** `main.mjs --handoff <action>` under a maintenance supervisor launch; prints one JSON line and exits. */
export async function runHandoffCommand(action: string, env: HandoffEnvironment, expectedSourceSha256?: string) {
  if (env.authority.profileRoot !== resolve(env.authority.profileRoot)) reject('backend_profile_absolute_required');
  switch (action) {
    case 'preview': return previewHandoff(env);
    case 'apply': return applyHandoff(env, expectedSourceSha256 && /^[a-f0-9]{64}$/.test(expectedSourceSha256) ? expectedSourceSha256 : reject('handoff_expected_source_required'));
    case 'activate': return activateHandoff(env);
    case 'rollback': return rollbackToPython(env);
    default: return reject('handoff_action_invalid');
  }
}
