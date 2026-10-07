import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, writeFileSync, readFileSync, symlinkSync } from 'node:fs';
import path from 'node:path';
import { nativeEvidenceRoot, assertSyntheticEvidenceDirectory, localEvidenceRoot, externalEvidenceRoot, ssdEvidenceRoot } from './native-evidence-directory.mjs';

test('only the exact existing lane or authorised C and E proof roots can be selected', () => {
  assert.equal(nativeEvidenceRoot(localEvidenceRoot), localEvidenceRoot);
  assert.equal(nativeEvidenceRoot(externalEvidenceRoot), externalEvidenceRoot);
  assert.equal(nativeEvidenceRoot(ssdEvidenceRoot), ssdEvidenceRoot);
  for (const value of ['relative', externalEvidenceRoot + '-other', ssdEvidenceRoot + '-other', path.dirname(externalEvidenceRoot), path.dirname(ssdEvidenceRoot), 'F:/Renulus-native-delivery/desktop-20261005/proofs']) assert.throws(() => nativeEvidenceRoot(value));
});

for (const evidenceRoot of [externalEvidenceRoot, ssdEvidenceRoot]) {
test('proof confinement preserves checkpoints below ' + evidenceRoot, () => {
  mkdirSync(evidenceRoot, { recursive: true });
  const directory = mkdtempSync(path.join(evidenceRoot, 'proof-root-boundary-'));
  const sentinel = path.join(directory, 'preserved.txt');
  writeFileSync(sentinel, 'synthetic preserved checkpoint');
  assert.equal(assertSyntheticEvidenceDirectory(directory), directory);
  for (const value of [localEvidenceRoot, evidenceRoot, path.join(evidenceRoot, '../../outside'), evidenceRoot + '-other/native-new']) assert.throws(() => assertSyntheticEvidenceDirectory(value));
  assert.equal(readFileSync(sentinel, 'utf8'), 'synthetic preserved checkpoint');
});

test('a real Windows junction cannot redirect a synthetic proof below ' + evidenceRoot, { skip: process.platform !== 'win32' }, () => {
  const directory = mkdtempSync(path.join(evidenceRoot, 'proof-root-junction-'));
  const target = path.join(directory, 'target');
  const junction = path.join(directory, 'junction');
  mkdirSync(target);
  symlinkSync(target, junction, 'junction');
  assert.throws(() => assertSyntheticEvidenceDirectory(path.join(junction, 'new-profile')), /reparse/);
});
}
