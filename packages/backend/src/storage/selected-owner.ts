// SPDX-License-Identifier: MIT
/** Final selected ownership. This never manufactures a synthetic selector. */
import { closeSync, existsSync, fstatSync, fsyncSync, lstatSync, openSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs';
import { createHash, randomUUID } from 'node:crypto';
import { join, resolve } from 'node:path';
import { canonical } from './schema.ts';
import { owned } from './ownership.ts';
import { reject } from './contracts.ts';

export interface SelectedWriterAuthority {
  contract: 'renulus-selected-writer/1';
  profileRoot: string;
  generationRoot: string;
  selectorSha256: string | null;
  authorityEpoch: number;
  ownerGeneration: string;
  predecessorGeneration: string | null;
  ownerReceiptSha256: string;
  nodePid: number;
  nodeCreationFiletime: string;
  supervisorPid: number;
  supervisorCreationFiletime: string;
  nonceSha256: string;
}
const hash = (bytes: string | Buffer) => createHash('sha256').update(bytes).digest('hex');
function metadata(file: string) {
  const stat = lstatSync(file);
  if (!stat.isFile() || stat.size > 32768 || stat.nlink !== 1) reject('selected_owner_invalid');
  return readFileSync(file);
}

/** Issued only from the private supervisor pipe before importing the app. */
export function readSelectedOwnerLaunch(): SelectedWriterAuthority {
  const key = Symbol.for('renulus.selected-owner.launch');
  const global = globalThis as unknown as Record<symbol, { authority: SelectedWriterAuthority; nonce: string } | undefined>;
  const launch = global[key]; delete global[key];
  if (!launch || typeof launch.nonce !== 'string' || hash(launch.nonce) !== launch.authority.nonceSha256)
    reject('selected_owner_launch_required');
  verifySelectedAuthority(launch.authority);
  return Object.freeze({ ...launch.authority });
}

export function verifySelectedAuthority(authority: SelectedWriterAuthority) {
  if (!authority || authority.contract !== 'renulus-selected-writer/1' || authority.nodePid !== process.pid ||
      authority.supervisorPid !== process.ppid || !/^[0-9]+$/.test(authority.supervisorCreationFiletime) ||
      !/^[0-9]+$/.test(authority.nodeCreationFiletime) || !/^[0-9a-f]{32}$/.test(authority.ownerGeneration) ||
      resolve(authority.profileRoot) !== authority.profileRoot || resolve(authority.generationRoot) !== authority.generationRoot)
    reject('selected_owner_native_proof_invalid');
  const root = authority.profileRoot;
  const receiptFile = owned(root, join(root, '.renulus-profile-owner.json'));
  const receiptBytes = metadata(receiptFile);
  if (hash(receiptBytes) !== authority.ownerReceiptSha256) reject('selected_owner_native_proof_changed');
  // FILETIME is a decimal string in the pipe. JSON parsing cannot safely retain
  // the journal's uint64; compare its exact decimal bytes, not a rounded Number.
  const receiptText = receiptBytes.toString('utf8');
  const receipt = JSON.parse(receiptText);
  if (receipt.generation !== authority.ownerGeneration || receipt.job_policy !== 'kill_on_close_no_breakaway_v1' ||
      receipt.python.pid !== authority.supervisorPid ||
      !receiptText.includes('"creation_filetime":' + authority.supervisorCreationFiletime) ||
      !receipt.native.some((item: { process: { pid: number } }) => item.process.pid === authority.nodePid) ||
      !receiptText.includes('"creation_filetime":' + authority.nodeCreationFiletime)) reject('selected_owner_native_proof_invalid');
  try { process.kill(authority.supervisorPid, 0); } catch { reject('selected_owner_supervisor_lost'); }
  const proof = JSON.parse(metadata(owned(root, join(root, '.renulus-selected-owner.json'))).toString('utf8'));
  if (canonical(proof) !== canonical(authority)) reject('selected_owner_native_proof_changed');
}

export function acquireSelectedOwner(options: { profileRoot: string; expectedSchemaHash: string; selectedAuthority: SelectedWriterAuthority }) {
  const authority = options.selectedAuthority;
  verifySelectedAuthority(authority);
  const root = authority.profileRoot, generation = authority.generationRoot;
  if (options.profileRoot !== generation) reject('selected_owner_generation_mismatch');
  owned(root, generation);
  const selectorPath = owned(root, join(root, '.renulus-backend-selector.json'));
  const selectedBytes = metadata(selectorPath);
  const selected = JSON.parse(selectedBytes.toString('utf8'));
  const databasePath = owned(generation, join(generation, 'state/renulus.sqlite3'));
  const databaseIdentity = lstatSync(databasePath);
  function checkSelection() {
    verifySelectedAuthority(authority);
    if (hash(metadata(selectorPath)) !== authority.selectorSha256 || selected.writer !== 'ts' || selected.state !== 'active' ||
        selected.authorityEpoch !== authority.authorityEpoch || selected.schemaHash !== options.expectedSchemaHash ||
        resolve(root, selected.generationPath) !== generation) reject('selected_owner_selector_stale');
    const manifest = owned(generation, join(generation, '.renulus-complete-generation.json'));
    if (hash(metadata(manifest)) !== selected.manifestSha256) reject('selected_owner_generation_changed');
    const current = lstatSync(owned(generation, databasePath));
    if (current.dev !== databaseIdentity.dev || current.ino !== databaseIdentity.ino) reject('selected_owner_database_changed');
    for (const suffix of ['-wal', '-shm', '-journal']) owned(generation, databasePath + suffix);
  }
  checkSelection();
  const owner = owned(generation, join(generation, 'state/storage-owner.json'));
  if (existsSync(owner)) {
    // Only the native supervisor's exact predecessor settlement can reclaim an
    // old file. No PID/age heuristics and no reclamation of an unknown writer.
    const previous = JSON.parse(metadata(owner).toString('utf8'));
    if (!authority.predecessorGeneration || previous.ownerGeneration !== authority.predecessorGeneration ||
        previous.contract !== 'renulus-selected-storage-owner/1') reject('storage_owner_busy');
    unlinkSync(owner);
  }
  const fd = openSync(owner, 'wx', 0o600), identity = fstatSync(fd);
  const token = canonical({ contract: 'renulus-selected-storage-owner/1', ownerGeneration: authority.ownerGeneration,
    authorityEpoch: authority.authorityEpoch, nodePid: authority.nodePid, nonce: randomUUID() });
  function check() {
    checkSelection();
    const current = lstatSync(owned(generation, owner));
    if (current.dev !== identity.dev || current.ino !== identity.ino || metadata(owner).toString('utf8') !== token)
      reject('storage_owner_stale');
  }
  const release = () => {
    closeSync(fd);
    if (existsSync(owner)) {
      const current = lstatSync(owned(generation, owner));
      if (current.dev === identity.dev && current.ino === identity.ino && metadata(owner).toString('utf8') === token) unlinkSync(owner);
    }
  };
  try { writeFileSync(fd, token); fsyncSync(fd); check(); }
  catch (error) { release(); throw error; }
  return { databasePath, check, release };
}
