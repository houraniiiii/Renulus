// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { spawnSync } from 'node:child_process';
import { DatabaseSync } from 'node:sqlite';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { openIsolatedStorage, MARKER, SELECTOR } from '../src/storage/index.ts';
import { inventory, loadMigrationInventory } from '../src/storage/schema.ts';
import { createKnowledgeDomain, ownNoteRights } from '../src/domain/knowledge/index.ts';
import { openEngineWorker } from '../src/workers/process.ts';
import { createEngineArtifacts } from '../src/workers/artifacts.ts';
import { createWorkerLibrary } from '../src/workers/library.ts';
import { createWorkerKnowledgeIO } from '../src/workers/knowledge.ts';
import { createKnowledgeHandleAuthority } from '../src/workers/knowledge-handles.ts';

test('actual native selected text/PDF/image/table -> selected engines -> canonical ready -> reader/source/note revision/delete', {
  skip: !process.env.RENULUS_KNOWLEDGE_NATIVE_JOURNEY, timeout: 360_000,
}, async t => {
  const root = await mkdtemp(path.join(tmpdir(), 'renulus-knowledge-native-'));
  const repository = fileURLToPath(new URL('../../..', import.meta.url));
  const python = 'C:/Renulus/dev/python/Scripts/python.exe';
  const managed = path.join(root, 'managed'), profile = path.join(managed, 'profile'), originals = path.join(managed, 'originals');
  const selectedRoot = path.join(root, 'selected'), savedCopy = path.join(root, 'synthetic-saved-copy.txt');
  await mkdir(originals, { recursive: true }); await mkdir(selectedRoot);
  const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); env.PATH = path.dirname(python);
  const setup = spawnSync(python, ['-I', '-X', 'utf8', '-c', `
import sys,json,hashlib,runpy
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from PIL import Image,ImageDraw,ImageFont
s=create_app(Path(sys.argv[2])).state.services
root=Path(sys.argv[3]); fixtures={}
pdf=runpy.run_path(str(Path(sys.argv[1])/'tests'/'backup'/'conftest.py'))['text_pdf']
files=[('synthetic-aki.txt','text/plain',b'SYNTHETIC AKI volume assessment study. Kidney injury educational material.'),
 ('synthetic-ckd.csv','text/csv',b'Topic,Observation\\nCKD,SYNTHETIC albuminuria follow-up\\nDialysis,SYNTHETIC access review\\n'),
 ('synthetic-transplant.pdf','application/pdf',pdf('SYNTHETIC transplant rejection biopsy learning'))]
image=Image.new('RGB',(1400,400),'white'); draw=ImageDraw.Draw(image)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',42)
draw.text((30,100),'SYNTHETIC dialysis fistula flow review',fill='black',font=font)
image.save(root/'synthetic-dialysis.png'); image.close()
files.append(('synthetic-dialysis.png','image/png',(root/'synthetic-dialysis.png').read_bytes()))
for ext,fmt,media in (('jpg','JPEG','image/jpeg'),('tiff','TIFF','image/tiff')):
 image=Image.new('RGB',(1400,400),'white'); draw=ImageDraw.Draw(image)
 draw.text((30,100),'SYNTHETIC hemodialysis catheter review',fill='black',font=font)
 image.save(root/('synthetic-catheter.'+ext),fmt); image.close()
 files.append(('synthetic-catheter.'+ext,media,(root/('synthetic-catheter.'+ext)).read_bytes()))
from io import BytesIO
import docx,openpyxl,pptx
def build(save):
 buffer=BytesIO(); save(buffer); return buffer.getvalue()
document=docx.Document(); document.add_heading('SYNTHETIC glomerulonephritis review',1); document.add_paragraph('SYNTHETIC complement pathway notes for a docx reader.')
workbook=openpyxl.Workbook(); sheet=workbook.active; sheet.title='Labs'; sheet.append(['Test','Result']); sheet.append(['Urine','SYNTHETIC proteinuria quantified'])
presentation=pptx.Presentation(); slide=presentation.slides.add_slide(presentation.slide_layouts[1]); slide.shapes.title.text='SYNTHETIC peritoneal dialysis'; slide.placeholders[1].text='SYNTHETIC peritoneal membrane transport'
files+=[('synthetic-lupus.md','text/markdown',b'# SYNTHETIC Lupus\\n\\nSYNTHETIC lupus nephritis class IV study.\\n'),
 ('synthetic-potassium.html','text/html',b'<html><body><h1>SYNTHETIC potassium</h1><p>SYNTHETIC hyperkalaemia management paragraph.</p></body></html>'),
 ('synthetic-sodium.xml','application/xml',b'<root><item>SYNTHETIC hyponatraemia evaluation</item></root>'),
 ('synthetic-gn.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',build(document.save)),
 ('synthetic-labs.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',build(workbook.save)),
 ('synthetic-pd.pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation',build(presentation.save))]
for name,media,body in files:
 (root/name).write_bytes(body);fixtures[name]={'path':str(root/name),'media_type':media,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
print(json.dumps({'database':str(s.paths.database),'files':fixtures}))
`, repository, profile, selectedRoot], { encoding: 'utf8', env, timeout: 60000 });
  assert.equal(setup.status, 0, setup.stderr);
  const prepared = JSON.parse(setup.stdout), migrations = loadMigrationInventory(repository);
  const db = new DatabaseSync(prepared.database, { readOnly: true }); const schemaHash = inventory(db, migrations).schemaHash; db.close();
  const selection = { contract: 'renulus-storage-selector/1', isolation: 'synthetic', profileId: 'synthetic-knowledge-native', generation: 1, authorityEpoch: 1,
    writer: 'ts', state: 'active', ownerId: 'synthetic-knowledge-native-owner', database: 'state/renulus.sqlite3' };
  await writeFile(path.join(profile, MARKER), JSON.stringify({ contract: 'renulus-synthetic-storage/1', profileId: selection.profileId }));
  await writeFile(path.join(profile, SELECTOR), JSON.stringify(selection));
  let selectedPath = prepared.files['synthetic-aki.txt'].path;
  const handles = await createKnowledgeHandleAuthority({ root: path.join(root, 'chooser'), chooseSelection: async () => selectedPath, chooseDestination: async () => savedCopy });
  let storage, worker, knowledge;
  const revisions = { configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 };
  try {
    storage = await openIsolatedStorage({ profileRoot: profile, selection, migrations, expectedSchemaHash: schemaHash });
    worker = await openEngineWorker({ python, sourceRoot: repository, launchRoot: path.join(root, 'launch'), retention: 'saved', current: () => revisions,
      identity: { profile_id: selection.profileId, domain_store_id: 'synthetic-canonical', runtime_store_id: 'synthetic-native', authority_epoch: 1, process_generation: 'knowledge-native-journey' },
      helpers: { helpers_root: 'C:/Renulus/dev/helper-assets', cache_root: path.join(managed, 'cache'), source_root: repository },
      derived: { root: path.join(managed, 'derived'), namespace: 'knowledge-native-journey', library_tombstones: [], memory_tombstones: [] },
      native: { originals_root: originals, budget_root: managed, ...handles.launch } });
    const engines = createEngineArtifacts(worker.channel, worker.ready.capacity.max_chunk_bytes);
    knowledge = createKnowledgeDomain({ storage, engines, native: createWorkerKnowledgeIO(worker.channel, worker.ready.capacity.max_chunk_bytes) });
    const queries = { 'synthetic-aki.txt': 'kidney injury', 'synthetic-ckd.csv': 'albuminuria', 'synthetic-transplant.pdf': 'biopsy', 'synthetic-dialysis.png': 'fistula flow',
      'synthetic-catheter.jpg': 'hemodialysis catheter', 'synthetic-catheter.tiff': 'hemodialysis catheter', 'synthetic-lupus.md': 'lupus nephritis', 'synthetic-potassium.html': 'hyperkalaemia',
      'synthetic-sodium.xml': 'hyponatraemia', 'synthetic-gn.docx': 'glomerulonephritis', 'synthetic-labs.xlsx': 'proteinuria', 'synthetic-pd.pptx': 'peritoneal' };
    const library = createWorkerLibrary(worker.channel, worker.ready.capacity.max_chunk_bytes), imported = {};
    for (const [filename, file] of Object.entries(prepared.files)) {
      selectedPath = file.path; const selected = await handles.select(); assert.ok(selected);
      const request = { title: filename, media_type: file.media_type, bytes: file.bytes, sha256: file.sha256,
        metadata: { source_id: 'R02', access_class: 'user-owned', original_sha256: file.sha256 }, rights: ownNoteRights(), document_id: null, expected_revision_id: null, project_id: null, note: false, idempotency_key: 'native-import-' + filename };
      // Office/XML/Markdown originals arrive as already-read HTTP bytes; the others use the native chooser handle.
      const raw = /\.(docx|xlsx|pptx|xml|md)$/.test(filename);
      const i = raw ? await knowledge.importBytes(request, await readFile(file.path)) : await knowledge.importSelected(request, selected); assert.equal(i.state, 'ready'); imported[filename] = i;
      const reference = { target: { type: 'library_revision', id: i.revision_id } };
      const resolved = await knowledge.resolve({ reference }); assert.equal(resolved.preview_state, filename.endsWith('.pptx') ? 'unsupported' : 'ready');
      const original = await knowledge.original({ reference }); assert.equal(createHash('sha256').update(original.body).digest('hex'), file.sha256);
      const doc = await storage.command({ type: 'knowledge.get', documentId: i.document_id }); assert.ok(doc.revisions[0].passage_count > 0);
      const hits = await library.query({ query: queries[filename], limit: 3,
        revisionIds: [i.revision_id], operationId: 'query-' + i.job_id, attemptId: 'attempt_1', signal: new AbortController().signal }); assert.ok(hits.length);
      if (resolved.payload?.asset_id) assert.ok((await knowledge.asset({ reference, asset_id: resolved.payload.asset_id, original_sha256: file.sha256 })).length > 0);
      if (file.media_type === 'text/plain') {
        const source = await knowledge.source({ reference, expected_policy_revision: resolved.policy_revision, expected_context_epoch: resolved.context_epoch });
        assert.match(source.text, /SYNTHETIC AKI/); assert.equal(source.dependency.target.type, 'library_revision');
        const destination = await handles.destination(); assert.ok(destination);
        assert.equal((await knowledge.handoff({ reference }, 'save', destination)).handed_off, true);
        assert.deepEqual(await readFile(savedCopy), Buffer.from(original.body));
      }
      if (file.media_type === 'text/csv') {
        const locator = { kind: 'table', format: 'csv', sheet_name: null, first_row: 2, last_row: 2, first_column: 1, last_column: 2 };
        const located = await knowledge.resolve({ reference: { ...reference, locator } }); assert.equal(located.payload.table.first_row, 2);
        const passage = await knowledge.passage({ reference, locator, original_sha256: file.sha256, expected_policy_revision: located.policy_revision, expected_context_epoch: located.context_epoch }); assert.match(passage.text, /albuminuria/);
      }
      t.diagnostic(filename + ': native original/reader + selected extraction/index/query passed');
    }
    const note = await knowledge.saveNote({ title: 'SYNTHETIC GN note', text: 'SYNTHETIC glomerular disease complement study.', idempotency_key: 'native-note-1' });
    const edited = await knowledge.saveNote({ title: 'SYNTHETIC GN revised', text: 'SYNTHETIC glomerular disease immunology revised study.', document_id: note.document_id, expected_revision_id: note.revision_id, idempotency_key: 'native-note-2' });
    assert.notEqual(note.revision_id, edited.revision_id); assert.match((await knowledge.note(note.document_id, note.revision_id)).text, /complement/);
    assert.match((await knowledge.note(note.document_id)).text, /immunology/);
    const removed = await knowledge.delete(note.document_id, edited.revision_id, 'native-note-delete', true); assert.equal(removed.cleanup_pending, false);
    assert.deepEqual(await library.query({ query: 'immunology', limit: 3, revisionIds: [edited.revision_id], operationId: 'native-note-after-delete', attemptId: 'attempt_1', signal: new AbortController().signal }), []);
    await assert.rejects(knowledge.note(note.document_id));
    // The selected originals remain independent of managed immutable publications.
    for (const file of Object.values(prepared.files)) assert.equal(createHash('sha256').update(await readFile(file.path)).digest('hex'), file.sha256);
    assert.equal(worker.channel.state().unsettled, 0);
  } finally {
    await knowledge?.close(); await worker?.close(); await storage?.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir())); assert.match(path.basename(root), /^renulus-knowledge-native-/); await rm(root, { recursive: true, force: true });
  }
});
