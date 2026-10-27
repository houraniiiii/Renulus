// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { openIsolatedStorage, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { ownNoteRights } from '../src/domain/knowledge/index.ts';

const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const python = 'C:/Renulus/dev/python/Scripts/python.exe';
const environment = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]]));
environment.PATH = dirname(python);
const hash = text => createHash('sha256').update(text).digest('hex');

test('one canonical owner rolls back failed publication, fences revoked grants, and deletes project memberships without originals', { timeout: 90_000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), 'renulus-knowledge-target-'));
  let storage;
  try {
    const prepared = spawnSync(python, ['-I', '-X', 'utf8', '-c', `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
s=create_app(Path(sys.argv[2])).state.services
with s.db.transaction() as c:
 c.execute("CREATE TRIGGER knowledge_synthetic_rollback BEFORE INSERT ON knowledge_passages WHEN NEW.text='SYNTHETIC rollback' BEGIN SELECT RAISE(ABORT,'synthetic publication failure'); END")
print(json.dumps({'database':str(s.paths.database)}))
`, repository, root], { env: environment, encoding: 'utf8', timeout: 60000 });
    assert.equal(prepared.status, 0, prepared.stderr);
    const database = JSON.parse(prepared.stdout).database;
    const migrations = loadMigrationInventory(repository), db = new DatabaseSync(database, { readOnly: true });
    const schemaHash = inventory(db, migrations).schemaHash; db.close();
    const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-knowledge', generation: 1,
      authorityEpoch: 1, writer: 'ts', state: 'active', ownerId: 'synthetic-knowledge-owner', database: 'state/renulus.sqlite3' };
    writeFileSync(join(root, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
    writeFileSync(join(root, SELECTOR), JSON.stringify(selection));
    storage = await openIsolatedStorage({ profileRoot: root, selection, migrations, expectedSchemaHash: schemaHash });
    const project = await storage.command({ type: 'project.create', title: 'SYNTHETIC AKI and transplantation', idempotencyKey: 'knowledge-project-create' });
    const noteText = 'SYNTHETIC CKD follow-up study note.';
    const request = { title: 'SYNTHETIC CKD', media_type: 'text/plain', bytes: Buffer.byteLength(noteText), sha256: hash(noteText),
      metadata: { source_id: 'R02', access_class: 'user-owned', asset_role: ['study-note'], original_sha256: hash(noteText) }, rights: ownNoteRights(),
      document_id: null, expected_revision_id: null, project_id: project.id, note: true, idempotency_key: 'knowledge-import-note-1' };
    const begin = await storage.command({ type: 'knowledge.import.begin', request });
    assert.equal((await storage.command({ type: 'knowledge.list', query: '', status: null, limit: 10, offset: 0 })).total, 0, 'intent precedes canonical original publication');
    const original = await storage.command({ type: 'knowledge.import.original', intentId: begin.id, originalHandle: 'original_synthetic_ckd' });
    const ready = (i, body) => ({ type: 'knowledge.import.ready', intentId: i.id, extraction: { synthetic: true }, passages: [{ id: 'passage_' + i.revision_id, text: body, context_text: body,
      locators: [{ item_ref: '#/texts/0', page: null, char_span: [0, body.length] }], headings: [] }], embeddingModel: 'BAAI/bge-small-en-v1.5', chunkTokens: 480 });
    await assert.rejects(storage.command(ready(original, 'SYNTHETIC rollback')));
    const rolledBack = await storage.command({ type: 'knowledge.get', documentId: begin.document_id });
    assert.equal(rolledBack.active_revision, null); assert.equal(rolledBack.revisions[0].passage_count, 0);
    const published = await storage.command(ready(original, noteText)); assert.equal(published.state, 'ready');
    const notes = await storage.command({ type: 'knowledge.notes.list', projectId: project.id, limit: 20, offset: 0 }); assert.equal(notes.items[0].revision_id, begin.revision_id);
    const sourcePin = await storage.command({ type: 'knowledge.source.pin', request: { reference: { target: { type: 'note_revision', id: begin.revision_id } } }, operation: 'display' });
    const nextRequest = { ...request, title: 'SYNTHETIC edited CKD', document_id: begin.document_id, expected_revision_id: begin.revision_id, idempotency_key: 'knowledge-import-note-2' };
    const next = await storage.command({ type: 'knowledge.import.begin', request: nextRequest });
    await storage.command({ type: 'dispatch.revoke', capability: 'renulus.source.read' });
    await assert.rejects(storage.command({ type: 'knowledge.import.original', intentId: next.id, originalHandle: 'original_synthetic_stale' }), { code: 'import_stale' });
    await assert.rejects(storage.command({ type: 'knowledge.source.recheck', pin: sourcePin, operation: 'display' }), { code: 'reader_revision_conflict' });
    await storage.command({ type: 'knowledge.import.fail', intentId: next.id, code: 'synthetic_revoked' });
    const current = await storage.command({ type: 'project.get', projectId: project.id });
    const goal = await storage.command({ type: 'project.goal', projectId: project.id, expectedRevision: current.revision, goalId: null, goalRevision: null, action: 'save',
      input: { title: 'SYNTHETIC review dialysis', topic_id: null, target_date: null, status: 'active', progress: { evidence_ids: [], manual_intent: 'SYNTHETIC deliberate goal' } }, idempotencyKey: 'knowledge-project-goal' });
    assert.equal(goal.goals.length, 1);
    await storage.command({ type: 'project.change', projectId: project.id, expectedRevision: goal.revision, action: 'delete', title: null, idempotencyKey: 'knowledge-project-delete' });
    const retained = await storage.command({ type: 'knowledge.get', documentId: begin.document_id });
    assert.equal(retained.active_revision, begin.revision_id);
    const retainedPin = await storage.command({ type: 'knowledge.notes.pin', documentId: begin.document_id, revisionId: null });
    assert.equal(retainedPin.pin.original_handle, 'original_synthetic_ckd');
    assert.equal(retainedPin.summary.revision_id, begin.revision_id);
    const removed = await storage.command({ type: 'knowledge.delete', documentId: begin.document_id, expectedRevisionId: begin.revision_id, idempotencyKey: 'knowledge-note-delete', note: true });
    assert.deepEqual(removed.revision_ids, [begin.revision_id]);
    await assert.rejects(storage.command({ type: 'knowledge.source.pin', request: { reference: { target: { type: 'note_revision', id: begin.revision_id } } }, operation: 'display' }));
  } finally {
    await storage?.close(); assert.equal(dirname(root), resolve(tmpdir())); assert.match(basename(root), /^renulus-knowledge-target-/); rmSync(root, { recursive: true, force: true });
  }
});
