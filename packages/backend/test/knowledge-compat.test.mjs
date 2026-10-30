// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Readable } from 'node:stream';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { openIsolatedStorage, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { createKnowledgeDomain, ownNoteRights } from '../src/domain/knowledge/index.ts';
import { knowledgeCommand } from '../src/http/knowledge-commands.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
environment.PATH = dirname(python);
const hash = body => createHash('sha256').update(body).digest('hex');

/** Records the order of native/engine effects; the real worker and reader are proven by the native journey. */
function synthetic(log) {
  const stored = new Map(), results = new Map(); let n = 0;
  const engines = {
    output: max => ({ artifact_handle: 'output_' + ++n, artifact_revision: 1, max_bytes: max }),
    async upload(body) { const handle = 'upload_' + ++n; stored.set(handle, Buffer.from(body)); return { artifact_handle: handle, artifact_revision: 1, artifact_sha256: hash(body), bytes: body.byteLength }; },
    async run(command, input) {
      log.push(command); const body = input.artifact_handle ? stored.get(input.artifact_handle) : null; let result;
      if (command === 'document.extract') result = { tag: 'document', passages: [{ text: body.toString(), context_text: body.toString(), locators: [{ item_ref: '#/texts/0', char_span: [0, 1] }], headings: [] }] };
      if (command === 'library.stage') { const ids = JSON.parse(body).passages.map(p => p.passage_id); result = { tag: 'library_staged', document_id: input.document_id, revision_id: input.revision_id, eligible: false, input_sha256: hash(body), passage_ids: ids }; }
      if (command === 'library.remove') { log.push('remove:' + input.revision_ids.join(',')); result = { tag: 'removed' }; }
      const text = Buffer.from(JSON.stringify(result)); results.set(input.output.artifact_handle, text);
      return { tag: 'artifact', artifact_handle: input.output.artifact_handle, artifact_revision: 1, artifact_sha256: hash(text), bytes: text.byteLength };
    },
    async read(reference) { return results.get(reference.artifact_handle); },
    async release() {},
  };
  const native = {
    async reserve() { log.push('reserve'); }, async publish({ body }) { log.push('publish:' + hash(body)); return { original_handle: 'original_' + ++n }; },
    async settle() { log.push('settle'); },
  };
  return { engines, native };
}
const post = (body, headers) => Object.assign(Readable.from(body ? [body] : []), { method: 'POST', headers });
const raw = (body, options, filename = 'synthetic.txt') => post(body, { 'x-renulus-import-options': JSON.stringify(options), 'x-renulus-filename': encodeURIComponent(filename), 'content-length': String(body.length) });
const scope = { kind: 'personal-library', entity_id: null };
const url = path => new URL('http://127.0.0.1' + path);

test('raw-file upload and revision-free delete keep their legacy statuses over the one canonical owner', { timeout: 90_000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'renulus-knowledge-compat-'));
  let storage, knowledge;
  try {
    const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
print(json.dumps({'database':str(create_app(Path(sys.argv[2])).state.services.paths.database)}))
`, repository, root], { env: environment, encoding: 'utf8', timeout: 60000 });
    assert.equal(prepared.status, 0, prepared.stderr);
    const migrations = loadMigrationInventory(repository), db = new DatabaseSync(JSON.parse(prepared.stdout).database, { readOnly: true });
    const schemaHash = inventory(db, migrations).schemaHash; db.close();
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-knowledge-compat', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-knowledge-compat-owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
    writeFileSync(join(root, SELECTOR), JSON.stringify(selection));
    storage = await openIsolatedStorage({ profileRoot: root, selection, migrations, expectedSchemaHash: schemaHash });
    const log = [], { engines, native } = synthetic(log);
    knowledge = createKnowledgeDomain({ storage, engines, native });
    const send = (request, path = '/api/v1/library/import/file') => knowledgeCommand(request, url(path), storage, knowledge);

    const body = Buffer.from('SYNTHETIC raw upload about AKI.');
    const imported = await send(raw(body, { scope, idempotency_key: 'compat-upload-1', title: 'SYNTHETIC upload' }));
    assert.equal(imported.status, 202); assert.equal(imported.value.status, 'ready');
    assert.deepEqual(log.slice(0, 3), ['reserve', 'publish:' + hash(body), 'document.extract'], 'reservation precedes publication, publication precedes extraction');

    for (const [request, status, code] of [
      [raw(body, { scope, idempotency_key: 'k' }, 'synthetic.exe'), 415, 'unsupported_file'],
      [raw(Buffer.from('not a pdf'), { scope, idempotency_key: 'k' }, 'synthetic.pdf'), 422, 'malformed_pdf'],
      [raw(body, { scope: { kind: 'case', entity_id: 'x' }, idempotency_key: 'k' }), 422, 'import_scope_denied'],
      [raw(body, { idempotency_key: 'k' }), 422, 'invalid_import_options'],
      [post(body, { 'x-renulus-import-options': JSON.stringify({ scope, idempotency_key: 'k' }), 'x-renulus-filename': 'a.txt', 'content-length': String(64 * 1024 * 1024 + 1) }), 413, 'document_limit'],
    ]) { const refused = await send(request); assert.equal(refused.status, status); assert.equal(refused.value.error.code, code); }

    // The domain owns an immutable copy and verifies the bounded digest after the reservation, before any publication.
    log.length = 0; const source = Buffer.from('SYNTHETIC mutable source.');
    const request = { title: 'SYNTHETIC copy', media_type: 'text/plain', bytes: source.byteLength, sha256: hash(source), metadata: { source_id: 'R02', original_sha256: hash(source) },
      rights: ownNoteRights(), document_id: null, expected_revision_id: null, project_id: null, note: false, idempotency_key: 'compat-copy' };
    const pending = knowledge.importBytes(request, source); source.fill(0);
    assert.equal((await pending).state, 'ready'); assert.ok(log.includes('publish:' + request.sha256));
    log.length = 0; const wrong = Buffer.from('SYNTHETIC wrong bytes!!!!!');
    await assert.rejects(knowledge.importBytes({ ...request, bytes: wrong.byteLength, idempotency_key: 'compat-wrong' }, wrong), { code: 'original_digest_mismatch' });
    assert.deepEqual(log, ['reserve', 'settle']);

    // DELETE without an expected revision resolves the current revision inside the one canonical transaction.
    const first = imported.value, second = await send(raw(Buffer.from('SYNTHETIC second revision.'), { scope, idempotency_key: 'compat-upload-2', document_id: first.document_id, expected_revision_id: first.revision_id }));
    assert.equal(second.status, 202); assert.equal(second.value.document_id, first.document_id); assert.notEqual(second.value.revision_id, first.revision_id);
    await assert.rejects(knowledgeCommand({ method: 'DELETE', headers: { 'idempotency-key': 'compat-stale' } }, url('/api/v1/library/documents/' + first.document_id + '?expected_revision_id=' + first.revision_id), storage, knowledge), { code: 'note_revision_conflict' });
    log.length = 0;
    const removed = await knowledgeCommand({ method: 'DELETE', headers: { 'idempotency-key': 'compat-delete' } }, url('/api/v1/library/documents/' + first.document_id), storage, knowledge);
    assert.deepEqual(removed, { status: 200, value: { document_id: first.document_id, status: 'deleted', cleanup_pending: false } });
    assert.equal(log.filter(entry => entry.startsWith('remove:')).join().includes(second.value.revision_id), true);
    await assert.rejects(storage.command({ type: 'knowledge.get', documentId: first.document_id }), { code: 'document_missing' });
  } finally {
    await knowledge?.close(); await storage?.close();
    assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-knowledge-compat-/); rmSync(root, { recursive: true, force: true });
  }
});
