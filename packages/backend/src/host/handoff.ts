// SPDX-License-Identifier: MIT
/** Profile-wide publication, after BF07 closes and snapshots every owner. */
import { createHash, randomUUID } from 'node:crypto';
import { closeSync, existsSync, fsyncSync, lstatSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';
import { owned } from '../storage/ownership.ts';
import { canonical } from '../storage/schema.ts';
import { reject } from '../storage/contracts.ts';
import { stateMarker } from '../storage/generation.ts';
import { verifySelectedAuthority, type SelectedWriterAuthority } from '../storage/selected-owner.ts';
export { readSelectedOwnerLaunch } from '../storage/selected-owner.ts';

export const BACKEND_SELECTOR = '.renulus-backend-selector.json';
export const GENERATION_MANIFEST = '.renulus-complete-generation.json';
export interface BackendSelector {
  contract: 'renulus-backend-selector/1';
  profileId: string;
  generation: number;
  authorityEpoch: number;
  writer: 'python' | 'ts';
  state: 'held' | 'active';
  generationPath: string;
  manifestSha256: string;
  schemaHash: string;
  cohortHash: string;
}
export interface GenerationMember { role: 'canonical' | 'native' | 'original' | 'plugin' | 'selector' | 'schema'; path: string; sha256: string; bytes: number }
export interface HandoffGeneration {
  profileId: string; generation: number; authorityEpoch: number; schemaHash: string; cohortHash: string;
  frontierDigest: string; members: readonly GenerationMember[]; sourceMarker?: string;
}
const hash = (bytes: Buffer | string) => createHash('sha256').update(bytes).digest('hex');
function read(path: string, maximum = 16 * 1024 * 1024) {
  const info = lstatSync(path);
  if (!info.isFile() || info.nlink !== 1 || info.size > maximum) reject('backend_metadata_invalid');
  return readFileSync(path);
}
function validSelector(value: BackendSelector) {
  if (canonical(Object.keys(value).sort()) !== canonical(['contract','profileId','generation','authorityEpoch','writer','state',
    'generationPath','manifestSha256','schemaHash','cohortHash'].sort()) || value.contract !== 'renulus-backend-selector/1' ||
    !['python','ts'].includes(value.writer) || !['held','active'].includes(value.state) ||
    !Number.isSafeInteger(value.generation) || value.generation < 1 || !Number.isSafeInteger(value.authorityEpoch) || value.authorityEpoch < 1 ||
    !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(value.profileId) ||
    [value.manifestSha256,value.schemaHash,value.cohortHash].some(v=>!/^[a-f0-9]{64}$/.test(v)) ||
    !/^generations\/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(value.generationPath)) reject('backend_selector_invalid');
}

export function resolveBackendSelection(profileRoot: string) {
  const root = resolve(profileRoot);
  if (root !== profileRoot) reject('backend_profile_absolute_required');
  const selectorPath = owned(root, join(root, BACKEND_SELECTOR));
  if (!existsSync(selectorPath)) return { writer: 'python' as const, profileRoot: root, admission: 'active' as const };
  const bytes = read(selectorPath, 16384), selector = JSON.parse(bytes.toString('utf8')) as BackendSelector;
  validSelector(selector);
  const generationRoot = owned(root, resolve(root, selector.generationPath));
  const manifest = JSON.parse(read(owned(generationRoot, join(generationRoot, GENERATION_MANIFEST))).toString('utf8')) as HandoffGeneration;
  if (hash(read(join(generationRoot, GENERATION_MANIFEST))) !== selector.manifestSha256 || manifest.profileId !== selector.profileId ||
      manifest.generation !== selector.generation || manifest.schemaHash !== selector.schemaHash || manifest.cohortHash !== selector.cohortHash)
    reject('backend_generation_changed');
  return { writer: selector.writer, profileRoot: generationRoot, selection: selector, expectedSchemaHash: selector.schemaHash,
    authorityEpoch: selector.authorityEpoch, admission: selector.state, selectorSha256: hash(bytes) };
}

export function observeGeneration(generationRoot: string, manifest: HandoffGeneration): GenerationMember[] {
  const observed = manifest.members.map(member => {
    const path = owned(generationRoot, resolve(generationRoot, member.path));
    if (relative(generationRoot, path).split(sep).join('/') !== member.path) reject('backend_member_path_invalid');
    const stat = lstatSync(path);
    if (!stat.isFile() || stat.nlink !== 1) reject('backend_member_unowned');
    return { ...member, sha256: hash(readFileSync(path)), bytes: stat.size };
  });
  return observed;
}

/** BF07 validates graph closure and schema, this layer validates real bytes. */
async function validateGeneration(root: string, manifest: HandoffGeneration) {
  const { validateCompleteGeneration } = await import('../storage/generation.ts');
  validateCompleteGeneration(manifest, observeGeneration(root, manifest));
  if (new Set(manifest.members.map(m=>m.path)).size !== manifest.members.length ||
      !manifest.members.some(m=>m.role==='canonical'&&m.path==='state/renulus.sqlite3')) reject('backend_generation_incomplete');
  const bytes = read(owned(root, join(root, GENERATION_MANIFEST)));
  if (canonical(JSON.parse(bytes.toString('utf8'))) !== canonical(manifest)) reject('backend_generation_manifest_changed');
  return hash(bytes);
}

function atomicSelection(root: string, selector: BackendSelector, expected: string | null) {
  validSelector(selector);
  const target = owned(root, join(root, BACKEND_SELECTOR));
  const actual = existsSync(target) ? hash(read(target, 16384)) : null;
  if (actual !== expected) reject('backend_selector_stale');
  const temporary = owned(root, join(root, '.backend-selector-' + randomUUID() + '.tmp'));
  const fd = openSync(temporary, 'wx', 0o600);
  try { writeFileSync(fd, canonical(selector)); fsyncSync(fd); } finally { closeSync(fd); }
  try {
    if ((existsSync(target) ? hash(read(target, 16384)) : null) !== expected) reject('backend_selector_stale');
    renameSync(temporary, target);
  } finally { if (existsSync(temporary)) unlinkSync(temporary); }
}

export interface HandoffOptions {
  authority: SelectedWriterAuthority;
  generationRoot: string;
  manifest: HandoffGeneration;
  /** Must close admission, drain then close native hosts, workers and canonical
   * writer, then snapshot. No canonical/engine lock may span remote drainage. */
  closeAndSnapshot(): Promise<HandoffGeneration>;
  /** Exact compatible binary cohort proof from the local bundle verifier. */
  verifyBinaries(writer: 'python' | 'ts', schemaHash: string, cohortHash: string): Promise<void>;
}

/** Publishing held is deliberately separate from resuming admission. Crash
 * before publication retains old selection; after publication always stays held. */
export async function selectPreparedGeneration(options: HandoffOptions & { writer?: 'ts' | 'python'; rollback?: boolean }) {
  const { authority, manifest } = options;
  verifySelectedAuthority(authority);
  const root = authority.profileRoot, generationRoot = owned(root, options.generationRoot);
  const writer = options.writer ?? 'ts';
  const current = await options.closeAndSnapshot();
  verifySelectedAuthority(authority);
  const before = resolveBackendSelection(root);
  if (manifest.profileId !== current.profileId || manifest.profileId !== (before.selection?.profileId ?? manifest.profileId) ||
      manifest.authorityEpoch !== authority.authorityEpoch + 1) reject('backend_generation_identity_changed');
  if (options.rollback) {
    // A rollback candidate must include every current closed member unchanged.
    // This intentionally refuses an old backup when newer work exists. BF07 may
    // construct a reconciled current candidate for the previous compatible binary.
    const incoming = new Map(manifest.members.map(m=>[m.role + ':' + m.path, m]));
    if (current.frontierDigest !== manifest.frontierDigest || current.members.some(member => {
      if (member.role === 'selector' || member.role === 'schema' || member.role === 'plugin') return false;
      const target = incoming.get(member.role + ':' + member.path);
      return !target || target.sha256 !== member.sha256 || target.bytes !== member.bytes;
    })) reject('backend_rollback_newer_work');
  } else if (manifest.sourceMarker !== stateMarker(current.members)) {
    // The candidate was merged from an earlier state of the current generation; selecting it would drop work added since.
    reject('recovery_candidate_stale');
  }
  const manifestSha256 = await validateGeneration(generationRoot, manifest);
  await options.verifyBinaries(writer, manifest.schemaHash, manifest.cohortHash);
  verifySelectedAuthority(authority);
  const generationPath = relative(root, generationRoot).split(sep).join('/');
  const selector: BackendSelector = { contract: 'renulus-backend-selector/1', profileId: manifest.profileId,
    generation: manifest.generation, authorityEpoch: manifest.authorityEpoch, writer, state: 'held', generationPath,
    manifestSha256, schemaHash: manifest.schemaHash, cohortHash: manifest.cohortHash };
  atomicSelection(root, selector, authority.selectorSha256);
  return selector;
}

/** Called on a new native-supervised maintenance launch, after every BF gate.
 * It never starts a worker or provider. A subsequent normal launch opens writes. */
export async function activateSelectedGeneration(authority: SelectedWriterAuthority,
  verify: (selection: BackendSelector) => Promise<void>) {
  verifySelectedAuthority(authority);
  const resolved = resolveBackendSelection(authority.profileRoot);
  if (!resolved.selection || resolved.admission !== 'held' || resolved.selectorSha256 !== authority.selectorSha256)
    reject('backend_activation_stale');
  const manifest = JSON.parse(read(join(resolved.profileRoot, GENERATION_MANIFEST)).toString('utf8')) as HandoffGeneration;
  await validateGeneration(resolved.profileRoot, manifest);
  await verify(resolved.selection);
  verifySelectedAuthority(authority);
  const selector = { ...resolved.selection, state: 'active' as const };
  atomicSelection(authority.profileRoot, selector, authority.selectorSha256);
  return selector;
}
