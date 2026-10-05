import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync, readFileSync, symlinkSync } from 'node:fs';
import path from 'node:path';
import { nativeEvidenceRoot, assertSyntheticEvidenceDirectory, localEvidenceRoot, externalEvidenceRoot } from './native-evidence-directory.mjs';

test('only the exact existing lane or authorised fresh E proof root can be selected', () => {
  assert.equal(nativeEvidenceRoot(localEvidenceRoot), localEvidenceRoot);
  assert.equal(nativeEvidenceRoot(externalEvidenceRoot), externalEvidenceRoot);
  for (const value of ['relative', externalEvidenceRoot + '-other', path.dirname(externalEvidenceRoot), 'F:/Renulus-native-delivery/desktop-20261005/proofs']) assert.throws(() => nativeEvidenceRoot(value));
});

test('proof confinement refuses the root itself and parent escapes without touching checkpoints', () => {
  mkdirSync(externalEvidenceRoot, { recursive: true });
  const directory = mkdtempSync(path.join(externalEvidenceRoot, 'proof-root-boundary-'));
  const sentinel = path.join(directory, 'preserved.txt');
  writeFileSync(sentinel, 'synthetic preserved checkpoint');
  assert.equal(assertSyntheticEvidenceDirectory(directory), directory);
  for (const value of [localEvidenceRoot, externalEvidenceRoot, path.join(externalEvidenceRoot, '../../outside'), externalEvidenceRoot + '-other/native-new']) assert.throws(() => assertSyntheticEvidenceDirectory(value));
  assert.equal(readFileSync(sentinel, 'utf8'), 'synthetic preserved checkpoint');
});

test('a real Windows junction cannot redirect a synthetic proof profile', { skip: process.platform !== 'win32' }, () => {
  const directory = mkdtempSync(path.join(externalEvidenceRoot, 'proof-root-junction-'));
  const target = path.join(directory, 'target');
  const junction = path.join(directory, 'junction');
  mkdirSync(target);
  symlinkSync(target, junction, 'junction');
  assert.throws(() => assertSyntheticEvidenceDirectory(path.join(junction, 'new-profile')), /reparse/);
});
