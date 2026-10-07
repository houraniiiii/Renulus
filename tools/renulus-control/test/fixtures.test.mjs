import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import { mkdir, mkdtemp, writeFile, symlink, link, rename, truncate } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { parseCli, loadFixtureCatalog, readSyntheticFixture, FIXTURES } from '../controller.mjs';

const parent = process.env.RENULUS_CONTROL_TEST_ROOT ? path.dirname(process.env.RENULUS_CONTROL_TEST_ROOT) : process.platform === 'win32' ? 'C:/rn-control' : os.tmpdir();
await mkdir(parent, { recursive: true });
const root = await mkdtemp(path.join(parent, 'fixtures-'));
let slot = 0;
const pdf = Buffer.from('%PDF-1.7\nSynthetic only\n%%EOF');
const name = 'synthetic-study.pdf';
const record = (file = name, bytes = pdf) => ({ path: file, size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
async function fixture(files = [record()]) {
  const fixtureRoot = path.join(root, String(++slot)); await mkdir(fixtureRoot);
  const config = { fixtureRoot, repo: path.join(root, 'repo'), python: path.join(root, 'runtime/python.exe'), stateRoot: path.join(root, 'state') };
  const manifest = { format: 'renulus-control-fixtures-v1', syntheticOnly: true, files };
  await writeFile(path.join(fixtureRoot, name), pdf);
  await writeFile(path.join(fixtureRoot, FIXTURES.marker), JSON.stringify(manifest));
  return { config, manifest, save: () => writeFile(path.join(fixtureRoot, FIXTURES.marker), JSON.stringify(manifest)) };
}

test('fixture CLI root is fixed once, local, explicit and outside personal/credential paths', () => {
  const base = ['--repo', path.join(root, 'repo'), '--python', path.join(root, 'python.exe')];
  assert.equal(parseCli([...base, '--fixture-root', root]).fixtureRoot, root);
  assert.throws(() => parseCli([...base, '--fixture-root', root, '--fixture-root', root]));
  for (const value of ['relative', 'C:/Users/synthetic/fixtures', 'C:/public/../fixtures', 'C:\\public\\..\\fixtures', 'C:/public/./fixtures', 'C:/public/fixtures.', 'C:/public/fixtures ', 'C:/public/fixtures:stream', '\\\\server\\share\\fixtures', '\\\\?\\C:\\fixtures', '//server/share/fixtures', 'C:/public/%2e%2e/fixtures', 'C:/public/.ssh/fixtures', 'C:/public/profile/fixtures', 'C:/public/Renulus-data/fixtures']) assert.throws(() => parseCli([...base, '--fixture-root', value]), value);
});

test('catalogue attests ownership, freezes declarations and uploads only requested PDF/PNG/JPEG bytes', async () => {
  const png = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10, 0]);
  const jpeg = Buffer.from([255, 216, 255, 224, 0]);
  const f = await fixture([record(), record('synthetic-image.png', png), record('synthetic-image.jpeg', jpeg)]);
  await writeFile(path.join(f.config.fixtureRoot, 'synthetic-image.png'), png); await writeFile(path.join(f.config.fixtureRoot, 'synthetic-image.jpeg'), jpeg);
  await writeFile(path.join(f.config.fixtureRoot, 'account.json'), 'unrelated synthetic sentinel');
  const catalog = await loadFixtureCatalog(f.config);
  for (const [file, bytes, mimeType] of [[name, pdf, 'application/pdf'], ['synthetic-image.png', png, 'image/png'], ['synthetic-image.jpeg', jpeg, 'image/jpeg']]) {
    const result = await readSyntheticFixture(f.config, catalog, file);
    assert.deepEqual(result.payload, { name: file, buffer: bytes, mimeType });
    assert.equal(result.receipt.sha256, createHash('sha256').update(bytes).digest('hex'));
  }
  f.manifest.files.push(record('synthetic-later.pdf')); await f.save();
  await assert.rejects(readSyntheticFixture(f.config, catalog, 'synthetic-later.pdf'), { code: 'undeclared_fixture' });
  for (const invalid of ['account.json', '../synthetic-study.pdf', '..\\synthetic-study.pdf', 'C:/synthetic-study.pdf', name + ':stream', 'synthetic-token.pdf', 'synthetic-study.pdf.', 'synthetic-study.pdf ', 'synthetic-study.PDF', '%2e%2e/synthetic-study.pdf']) await assert.rejects(readSyntheticFixture(f.config, catalog, invalid), { code: 'invalid_fixture' });
});

test('manifest refuses unclassified, malformed, duplicate, oversized and path-bearing declarations', async () => {
  for (const change of [m => { m.syntheticOnly = false; }, m => { m.extra = true; }, m => { m.files = []; }, m => { m.files.push(m.files[0]); }, m => { m.files[0].path = '../synthetic-study.pdf'; }, m => { m.files[0].path = 'synthetic-credential.pdf'; }, m => { m.files[0].size = FIXTURES.bytes + 1; }, m => { m.files[0].sha256 = 'missing'; }, m => { m.files[0].extra = 'ignored?'; }, m => { m.files = Array(33).fill(record()); }]) {
    const f = await fixture(); change(f.manifest); await f.save();
    await assert.rejects(loadFixtureCatalog(f.config), { code: 'invalid_fixture_manifest' });
  }
  const f = await fixture();
  await writeFile(path.join(f.config.fixtureRoot, FIXTURES.marker), '{broken');
  await assert.rejects(loadFixtureCatalog(f.config), { code: 'invalid_fixture_manifest' });
  await writeFile(path.join(f.config.fixtureRoot, FIXTURES.marker), ' '.repeat(FIXTURES.manifestBytes + 1));
  await assert.rejects(loadFixtureCatalog(f.config), { code: 'unsafe_fixture_file' });
});

test('fixture roots reject Git, runtime/profile overlap and junction aliases before reading payloads', async () => {
  const f = await fixture();
  for (const config of [{ ...f.config, repo: f.config.fixtureRoot }, { ...f.config, stateRoot: path.dirname(f.config.fixtureRoot), fixtureRoot: path.join(path.dirname(f.config.fixtureRoot), 'c') }, { ...f.config, python: path.join(f.config.fixtureRoot, 'python.exe') }]) await assert.rejects(loadFixtureCatalog(config), { code: 'unsafe_fixture_root' });
  await mkdir(path.join(f.config.fixtureRoot, '.git'));
  await assert.rejects(loadFixtureCatalog(f.config), { code: 'state_in_git' });
  const g = await fixture(); const alias = path.join(root, 'junction-' + slot);
  await symlink(g.config.fixtureRoot, alias, process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(loadFixtureCatalog({ ...g.config, fixtureRoot: alias }), { code: 'unsafe_path' });
});

test('hard-linked manifests and payloads, replaced roots and directory leaves are refused', async () => {
  const f = await fixture();
  await link(path.join(f.config.fixtureRoot, FIXTURES.marker), path.join(root, 'manifest-hardlink'));
  await assert.rejects(loadFixtureCatalog(f.config), { code: 'unsafe_fixture_file' });
  const g = await fixture(), catalog = await loadFixtureCatalog(g.config);
  await link(path.join(g.config.fixtureRoot, name), path.join(root, 'payload-hardlink'));
  await assert.rejects(readSyntheticFixture(g.config, catalog, name), { code: 'unsafe_fixture_file' });
  const h = await fixture(), hCatalog = await loadFixtureCatalog(h.config), moved = h.config.fixtureRoot + '-moved';
  await rename(h.config.fixtureRoot, moved);
  await symlink(moved, h.config.fixtureRoot, process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(readSyntheticFixture(h.config, hCatalog, name), { code: 'unsafe_path' });
  const i = await fixture([record('synthetic-directory.pdf')]), iCatalog = await loadFixtureCatalog(i.config);
  await mkdir(path.join(i.config.fixtureRoot, 'synthetic-directory.pdf'));
  await assert.rejects(readSyntheticFixture(i.config, iCatalog, 'synthetic-directory.pdf'), { code: 'unsafe_fixture_file' });
});

test('size, hashes and media signatures are verified with bounded reads and cancellation', async () => {
  const f = await fixture(), catalog = await loadFixtureCatalog(f.config);
  await writeFile(path.join(f.config.fixtureRoot, name), Buffer.alloc(pdf.length, 65));
  await assert.rejects(readSyntheticFixture(f.config, catalog, name), { code: 'fixture_integrity' });
  await truncate(path.join(f.config.fixtureRoot, name), FIXTURES.bytes + 1);
  await assert.rejects(readSyntheticFixture(f.config, catalog, name), { code: 'unsafe_fixture_file' });
  const g = await fixture([record(name, Buffer.from('not a PDF'))]);
  await writeFile(path.join(g.config.fixtureRoot, name), 'not a PDF');
  await assert.rejects(readSyntheticFixture(g.config, await loadFixtureCatalog(g.config), name), { code: 'fixture_type' });
  const h = await fixture(), hCatalog = await loadFixtureCatalog(h.config);
  await assert.rejects(readSyntheticFixture(h.config, hCatalog, name, AbortSignal.abort()), { name: 'AbortError' });
});
