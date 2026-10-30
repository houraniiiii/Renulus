// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonical, digest } from '../src/storage/schema.ts';
import { effectiveKnowledgeMetadata } from '../src/domain/knowledge/source-status.ts';

test('source projection matches existing Python across exact acquired versions, wrong editions and publication-wide retraction', () => {
  const repository = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
  const python = 'C:/Renulus/dev/python/Scripts/python.exe';
  const env = Object.fromEntries(['SystemRoot', 'WINDIR', 'TEMP', 'TMP'].filter(k => process.env[k]).map(k => [k, process.env[k]])); env.PATH = dirname(python);
  const oracle = spawnSync(python, ['-I', '-X', 'utf8', '-c', `
import sys,json
sys.path.insert(0,sys.argv[1]+'/runtime')
from renulus.knowledge.source_status import SourceStatusJournal
from renulus.knowledge.models import SourceMetadata
base=SourceMetadata(source_id='R03',doi='10.1234/synthetic-nephrology',edition='v1',original_sha256='a'*64,publication_status='final',latest_final_verified=True,content_reviewed=True,topic_ids=['ckd'],collection_chapter='SYNTHETIC chapter',asset_role=['acquired-jats']).model_dump()
event={'contract_version':1,'event_id':'synthetic-correction','source_id':'R03','identity':{'doi':'10.1234/synthetic-nephrology','edition':'v1','original_sha256':'a'*64},'changes':{'excluded_pages':[2],'correction':'SYNTHETIC correction'},'scope':{'topic_ids':['ckd'],'locators':['SYNTHETIC chapter']}}
retraction={'contract_version':1,'event_id':'synthetic-retraction','source_id':'R03','identity':{'doi':'10.1234/synthetic-nephrology','edition':'v2','original_sha256':'b'*64},'changes':{'retracted':True}}
cases=[(base,[event]),({**base,'edition':'v0'},[event]),({**base,'doi':'10.1234/other-synthetic-publication'},[event,retraction]),(base,[event,retraction]),({**base,'topic_ids':['aki']},[event])]
journal=SourceStatusJournal.__new__(SourceStatusJournal)
print(json.dumps([{'metadata':m,'events':e,'expected':journal.effective(m,e).model_dump()} for m,e in cases]))
`, repository], { env, encoding: 'utf8', timeout: 20000 });
  assert.equal(oracle.status, 0, oracle.stderr);
  const db = new DatabaseSync(':memory:');
  try {
    db.exec('CREATE TABLE knowledge_source_status_events(id TEXT PRIMARY KEY,source_id TEXT,request_hash TEXT,payload_json TEXT,created_at TEXT)');
    for (const item of JSON.parse(oracle.stdout)) {
      db.exec('DELETE FROM knowledge_source_status_events');
      item.events.forEach((event, index) => db.prepare('INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)').run(event.event_id, event.source_id, digest(canonical(event)), JSON.stringify(event), String(index)));
      assert.deepEqual(effectiveKnowledgeMetadata(db, item.metadata), item.expected);
    }
  } finally { db.close(); }
});
