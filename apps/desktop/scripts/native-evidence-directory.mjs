/** Fresh synthetic proof outputs only; never moves an existing application profile. */
import { lstatSync, existsSync } from 'node:fs';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const localEvidenceRoot = path.join(desktop, 'test-results');
export const externalEvidenceRoot = path.resolve('E:/Renulus-native-delivery/desktop-20261005/proofs');
const identity = value => process.platform === 'win32' ? value.toLowerCase() : value;

function rejectReparseAncestors(value) {
  for (let cursor = value; ; cursor = path.dirname(cursor)) {
    if (existsSync(cursor) && lstatSync(cursor).isSymbolicLink()) throw new Error('Synthetic evidence may not traverse a reparse path.');
    if (cursor === path.dirname(cursor)) break;
  }
}

export function nativeEvidenceRoot(requested = process.env.RENULUS_NATIVE_EVIDENCE_ROOT) {
  if (requested && !path.isAbsolute(requested)) throw new Error('An absolute synthetic evidence root is required.');
  const root = path.resolve(requested || localEvidenceRoot);
  if (![localEvidenceRoot, externalEvidenceRoot].some(allowed => identity(allowed) === identity(root))) throw new Error('Use the desktop test-results or exact authorised E proofs root.');
  rejectReparseAncestors(root);
  return root;
}

export function assertSyntheticEvidenceDirectory(value) {
  if (!path.isAbsolute(value)) throw new Error('An absolute synthetic evidence directory is required.');
  const directory = path.resolve(value);
  if (![localEvidenceRoot, externalEvidenceRoot].some(root => {
    const relative = path.relative(root, directory);
    return relative && !relative.startsWith('..') && !path.isAbsolute(relative);
  })) throw new Error('The synthetic evidence directory must be a descendant of an owned proof root.');
  rejectReparseAncestors(directory);
  return directory;
}

export async function createNativeEvidence(kind) {
  if (!/^[a-z-]+$/.test(kind)) throw new Error('A fixed synthetic proof kind is required.');
  const root = nativeEvidenceRoot();
  await mkdir(root, { recursive: true });
  const directory = assertSyntheticEvidenceDirectory(path.join(root, kind + '-' + randomUUID().slice(0, 8)));
  await mkdir(directory);
  return directory;
}
