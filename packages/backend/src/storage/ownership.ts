// SPDX-License-Identifier: MIT
import { closeSync, existsSync, fstatSync, fsyncSync, lstatSync, openSync, readFileSync, realpathSync, unlinkSync, writeFileSync } from 'node:fs';
import { isAbsolute, join, relative, resolve, sep } from 'node:path';
import { randomUUID } from 'node:crypto';
import { canonical } from './schema.ts';
import { exact, integer, reject, text } from './contracts.ts';
import type { SyntheticSelector, WriterOptions } from './contracts.ts';
import { acquireSelectedOwner } from './selected-owner.ts';

export const MARKER = '.renulus-synthetic-storage.json';
export const SELECTOR = 'state/storage-selector.json';
export const OWNER = 'state/storage-owner.json';

/** No traversal, junctions, symlinks or pre-existing hardlink aliases. */
export function owned(root: string, path: string): string {
  const full = resolve(path), part = relative(root, full);
  if (!part || part.startsWith('..' + sep) || part === '..' || isAbsolute(part)) reject('storage_path_unowned');
  let current = root;
  for (const component of part.split(sep)) {
    current = join(current, component);
    if (existsSync(current)) {
      const stat = lstatSync(current);
      if (stat.isSymbolicLink() || realpathSync(current).toLowerCase() !== current.toLowerCase() ||
          (stat.isFile() && stat.nlink !== 1)) reject('storage_path_alias');
    }
  }
  return full;
}

function metadata(path: string): string {
  if (!lstatSync(path).isFile() || lstatSync(path).size > 16384) reject('storage_owner_invalid');
  return readFileSync(path, 'utf8');
}

export function validateSelector(value: unknown): asserts value is SyntheticSelector {
  exact(value, ['contract', 'isolation', 'profileId', 'generation', 'authorityEpoch', 'writer', 'state', 'ownerId', 'database']);
  if (value.contract !== 'renulus-storage-selector/1' || value.isolation !== 'synthetic' ||
      !['python', 'ts'].includes(String(value.writer)) || !['prepared', 'active', 'recovery'].includes(String(value.state)) ||
      value.database !== 'state/renulus.sqlite3') reject('storage_selector_invalid');
  text(value.profileId, 1, 120); text(value.ownerId, 1, 120); integer(value.generation, 1); integer(value.authorityEpoch, 1);
}

export function acquireOwner(options: WriterOptions): { databasePath: string; check: () => void; release: () => void } {
  if (options.selectedAuthority) return acquireSelectedOwner({ profileRoot: options.profileRoot,
    expectedSchemaHash: options.expectedSchemaHash, selectedAuthority: options.selectedAuthority });
  validateSelector(options.selection);
  if (!isAbsolute(options.profileRoot)) reject('storage_profile_absolute_required');
  const root = resolve(options.profileRoot);
  if (realpathSync(root).toLowerCase() !== root.toLowerCase()) reject('storage_path_alias');
  const marker = owned(root, join(root, MARKER));
  const markerBytes = metadata(marker);
  const identity = JSON.parse(markerBytes);
  exact(identity, ['contract', 'profileId']);
  if (identity.contract !== 'renulus-synthetic-storage/1' || identity.profileId !== options.selection.profileId) reject('storage_profile_mismatch');
  const selection = options.selection;
  const selector = owned(root, join(root, SELECTOR));
  const owner = owned(root, join(root, OWNER));
  const databasePath = owned(root, join(root, selection.database));
  if (!lstatSync(databasePath).isFile()) reject('storage_database_missing');
  const databaseIdentity = lstatSync(databasePath);
  function checkSelection() {
    owned(root, marker); owned(root, selector); owned(root, databasePath);
    if (metadata(marker) !== markerBytes) reject('storage_profile_changed');
    const actual = JSON.parse(metadata(selector));
    validateSelector(actual);
    if (canonical(actual) !== canonical(selection)) reject('storage_selector_stale');
    if (actual.writer !== 'ts' || actual.state !== 'active') reject('storage_writer_not_selected');
    const current = lstatSync(databasePath);
    if (current.dev !== databaseIdentity.dev || current.ino !== databaseIdentity.ino) reject('storage_database_changed');
    for (const suffix of ['-wal', '-shm', '-journal']) owned(root, databasePath + suffix);
  }
  checkSelection();
  let fd: number;
  try { fd = openSync(owner, 'wx', 0o600); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'EEXIST') reject('storage_owner_busy');
    throw error;
  }
  const token = canonical({ contract: 'renulus-storage-owner/1', selection, nonce: randomUUID() });
  const lockIdentity = fstatSync(fd);
  function check() {
    checkSelection(); owned(root, owner);
    const current = lstatSync(owner);
    if (current.dev !== lockIdentity.dev || current.ino !== lockIdentity.ino || metadata(owner) !== token) reject('storage_owner_stale');
  }
  function release() {
    // Never remove a successor's or an ambiguous lock. Crash reclamation belongs to BF08.
    closeSync(fd);
    if (existsSync(owner)) {
      const current = lstatSync(owner);
      if (current.dev === lockIdentity.dev && current.ino === lockIdentity.ino && metadata(owner) === token) unlinkSync(owner);
    }
  }
  try { writeFileSync(fd, token); fsyncSync(fd); check(); }
  catch (error) { release(); throw error; }
  return { databasePath, check, release };
}
