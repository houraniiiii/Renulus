// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createServer } from 'node:http';
import { DatabaseSync } from 'node:sqlite';
import { spawnSync } from 'node:child_process';
import { mkdtemp, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createEvidenceDomain } from '../src/domain/evidence/index.ts';
import { createEvidenceTools } from '../src/domain/evidence/tools.ts';
import { executeEvidenceCommand } from '../src/domain/evidence/commands.ts';
import { openEngineWorker } from '../src/workers/process.ts';
import { canonical, digest } from '../src/storage/schema.ts';
const repository = fileURLToPath(new URL('../../..', import.meta.url));
const sql = await readFile(new URL('../../../runtime/renulus/runtime/migrations/007-l1b1-evidence.sql', import.meta.url), 'utf8');
const knowledgeSql = await readFile(new URL('../../../runtime/renulus/knowledge/schema.sql', import.meta.url), 'utf8');
const contentSql = await readFile(new URL('../../../runtime/renulus/content/schema.sql', import.meta.url), 'utf8');
function storageFixture() {
  const db = new DatabaseSync(':memory:');
  db.exec('CREATE TABLE retrieval_usage(provider TEXT,day TEXT,requests INTEGER,credits INTEGER,PRIMARY KEY(provider,day));' + sql);
  db.exec(knowledgeSql + contentSql + 'CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT); CREATE TABLE knowledge_source_status_events(id TEXT PRIMARY KEY,source_id TEXT,request_hash TEXT,payload_json TEXT,created_at TEXT);');
  return { db, storage: { async command(c) { db.exec('BEGIN IMMEDIATE'); try {
    const result=executeEvidenceCommand(db,c); db.exec('COMMIT'); return result;
  } catch(error) { db.exec('ROLLBACK'); throw error; } } } };
}

test('fake channel: idempotent reservation/refund/uncertainty, keyed status and tool adapters', async () => {
  const {db,storage}=storageFixture(), artifacts=new Map(), commands=[];
  let sequence=0;
  const identity={profile_id:'synthetic',domain_store_id:'domain',runtime_store_id:'native',authority_epoch:1,process_generation:'process'};
  const revisions={configuration:0,grant:0,context:0,deletion:0,cancellation:0};
  const channel={submitBound(command,factory,binding){
    const requestId='request_'+(++sequence),bound={...identity,...binding,request_id:requestId};
    const plan=factory(bound,revisions);commands.push([command,plan.action]);
    const data=Buffer.from(JSON.stringify(plan.action==='status'?{connections:[{provider:'brave',configured:true,enabled:true,selected:true,
      credential_ref:'retrieval:brave',credential_revision:1,daily_request_limit:10,daily_credit_limit:10}]}:
      {records:[],queried_at:'2026-10-27T00:00:00Z'}));
    const artifact={tag:'artifact',artifact_handle:plan.output.artifact_handle,artifact_revision:1,artifact_sha256:createHash('sha256').update(data).digest('hex'),bytes:data.length};
    artifacts.set(artifact.artifact_handle,{artifact,data});
    const observation={current:true,reply:{identity:bound,result:{tag:'http',identity:bound,admission_receipt:plan.admission_receipt,
      effect:'response_received',requests_started:plan.action==='status'?0:1,outcome:'committed_reference',artifact},settlement:{state:'settled'}}};
    return {requestId,terminal:Promise.resolve(observation),admission:Promise.resolve(observation)};
  },submit(command,input){const requestId='control_'+(++sequence);let result={};
    if(command==='artifact.read'){const a=artifacts.get(input.artifact_handle);result={artifact:a.artifact,offset:input.offset,data_base64:a.data.subarray(input.offset,input.offset+input.length).toString('base64')};}
    return {requestId,terminal:Promise.resolve({current:true,reply:{outcome:'committed_reference',result}})};
  },release(){}};
  const domain=createEvidenceDomain({storage,worker:{channel,maxChunkBytes:262144,retention:'saved'},check:async()=>{}});
  try {
    const input={query:'synthetic AKI',providers:['brave'],budget:{max_requests:1,max_credits:1},operationId:'synthetic',signal:new AbortController().signal};
    assert.equal((await domain.search(input)).brave.usage.credits,1);
    assert.deepEqual(commands,[['evidence.run','status'],['evidence.run','search']]);
    const reserve={type:'evidence.reserve',id:'synthetic-id',operation_id:'synthetic',provider:'pubmed',day:'2026-10-27',requests:2,credits:0,request_limit:2,credit_limit:0};
    await storage.command(reserve);await storage.command(reserve);
    await storage.command({type:'evidence.settle',id:reserve.id,requests_started:1,effect:'response_received'});
    assert.equal(db.prepare("SELECT requests FROM retrieval_usage WHERE provider='pubmed'").get().requests,1);
    const uncertain={...reserve,id:'uncertain',provider:'europe-pmc'};await storage.command(uncertain);
    await storage.command({type:'evidence.settle',id:'uncertain',requests_started:0,effect:'uncertain'});
    assert.equal(db.prepare("SELECT requests FROM retrieval_usage WHERE provider='europe-pmc'").get().requests,2);
    const bridge=createEvidenceTools({evidence:domain,resolve:async()=>({operationId:'synthetic',attemptId:'1',sessionId:'s',grants:['renulus.evidence.fetch']}),check:async()=>{}});
    await assert.rejects(async()=>bridge.webfetch({url:'https://example.org/PMC10001'}, {sessionID:'s',id:'c'},input.signal),{code:'evidence_url_denied'});
  } finally {db.close();}
});

test('real evidence providers: Europe PMC, PubMed, saved keyed lane, no quota fallback, refused redirect and dated fetch', {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 90_000,
}, async () => {
  const root=await mkdtemp(path.join(tmpdir(),'renulus-evidence-journey-')),profile=path.join(root,'profile');
  const python=process.env.RENULUS_BACKEND_TEST_PYTHON;
  const script=`import sys,json\nfrom pathlib import Path\nsys.path.insert(0,str(Path(sys.argv[1])/'runtime'))\nfrom renulus.retrieval.connections import RetrievalConnections\nfrom types import SimpleNamespace\np=Path(sys.argv[2]);p.mkdir(parents=True)\nc=RetrievalConnections(SimpleNamespace(root=p,state=p/'state'))\nc.configure('brave',api_key='synthetic-evidence-key',enabled=True,daily_request_limit=1,daily_credit_limit=1)\nc.select('brave')`;
  const environment=Object.fromEntries(['SystemRoot','WINDIR','TEMP','TMP'].filter(k=>process.env[k]).map(k=>[k,process.env[k]]));environment.PATH=path.dirname(python);
  const prepared=spawnSync(python,['-I','-X','utf8','-c',script,repository,profile],{env:environment,encoding:'utf8',windowsHide:true});
  assert.equal(prepared.status,0,prepared.stderr);
  const metadata={resultList:{result:[{id:'10001',source:'MED',pmid:'10001',pmcid:'PMC10001',title:'Synthetic kidney study',firstPublicationDate:'2026-09-01',isOpenAccess:'Y',license:'cc by'}]}};
  const xml=`<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article"><front><journal-meta><publisher><publisher-name>Synthetic Press</publisher-name></publisher></journal-meta><article-meta><article-id pub-id-type="pmcid">PMC10001</article-id><article-id pub-id-type="pmid">10001</article-id><title-group><article-title>Synthetic kidney study</article-title></title-group><contrib-group><contrib><name><surname>Synthetic Author</surname></name></contrib></contrib-group><pub-date pub-type="epub"><year>2026</year><month>9</month><day>1</day></pub-date><permissions><copyright-holder>Synthetic Author</copyright-holder><license><license-p><ext-link xlink:href="https://creativecommons.org/licenses/by/4.0/">CC BY</ext-link></license-p></license></permissions><abstract><p>Synthetic kidney research abstract.</p></abstract></article-meta></front><body><sec><title>Results</title><p>Synthetic kidney study observations.</p><p>Synthetic allowed glomerular research passage.</p></sec></body></article>`;
  const seen=[];let redirect=false;
  const server=createServer((req,res)=>{
    const url=new URL(req.url,'http://localhost');seen.push(url.pathname);
    if(redirect&&url.pathname==='/europe/search'){res.writeHead(302,{location:'/never-follow'});res.end();return;}
    let value;
    if(url.pathname==='/europe/search')value=metadata;
    else if(url.pathname.endsWith('/fullTextXML')){res.writeHead(200,{'content-type':'application/xml'});res.end(xml);return;}
    else if(url.pathname==='/pubmed/esearch.fcgi')value={esearchresult:{idlist:['10001']}};
    else if(url.pathname==='/pubmed/esummary.fcgi')value={result:{'10001':{title:'Synthetic PubMed kidney study',pubdate:'2026 Sep',articleids:[],authors:[],pubtype:['Journal Article']}}};
    else if(url.pathname==='/brave'){assert.equal(req.headers['x-subscription-token'],'synthetic-evidence-key');value={web:{results:[{title:'Synthetic keyed discovery',url:'https://example.org/study',description:'Synthetic result'}]}};}
    else{res.writeHead(404);res.end();return;}
    res.writeHead(200,{'content-type':'application/json'});res.end(JSON.stringify(value));
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const port=server.address().port;
  const revisions={configuration:0,grant:0,context:0,deletion:0,cancellation:0};
  const worker=await openEngineWorker({python,sourceRoot:repository,launchRoot:path.join(root,'launch'),retention:'saved',current:()=>revisions,
    identity:{profile_id:'synthetic',domain_store_id:'domain',runtime_store_id:'native',authority_epoch:1,process_generation:'process'},
    broker:{profile_root:profile,state_root:path.join(profile,'state')}});
  const {db,storage}=storageFixture();
  const endpoints=Object.fromEntries([['europe-pmc','europe'],['pubmed','pubmed'],['brave','brave']].map(([provider,p])=>[provider,{host:'127.0.0.1',port,private_network:true,base_url:`http://127.0.0.1:${port}/${p}`} ]));
  const domain=createEvidenceDomain({storage,worker:{channel:worker.channel,maxChunkBytes:worker.ready.capacity.max_chunk_bytes,retention:'saved'},check:async()=>{},endpoints});
  const input={query:'synthetic AKI',providers:['europe-pmc','pubmed','brave'],budget:{max_requests:4,max_credits:1},operationId:'synthetic-operation',signal:new AbortController().signal};
  try {
    const found=await domain.discoverDated(input);
    for(const provider of input.providers){assert.equal(found[provider].error,undefined,JSON.stringify(found));assert.equal(found[provider].records.length,1);assert.equal(found[provider].verification,'discovery-only');assert.equal(found[provider].passage_evidence,false);assert.ok(found[provider].queried_at);}
    assert.equal(found.pubmed.usage.requests,2);assert.equal(found.brave.usage.credits,1);
    const before=db.prepare('SELECT * FROM retrieval_usage ORDER BY provider').all(),calls=seen.length;
    const quota=await domain.search({...input,providers:['brave']});assert.equal(quota.brave.error,'retrieval_daily_limit');
    assert.equal(seen.length,calls);assert.deepEqual(db.prepare('SELECT * FROM retrieval_usage ORDER BY provider').all(),before);
    redirect=true;const blocked=await domain.search({...input,providers:['europe-pmc']});
    assert.equal(blocked['europe-pmc'].error,'retrieval_redirect_blocked');assert.equal(blocked['europe-pmc'].usage.requests,1);assert.ok(!seen.includes('/never-follow'));
    redirect=false;const fetched=await domain.fetch({pmcid:'PMC10001',budget:{max_requests:2,max_credits:0},operationId:input.operationId,signal:input.signal});
    assert.equal(fetched.source_restrictions_checked,true);assert.ok(fetched.passages.length>0);
    assert.equal(fetched.passages[0].publication_date,'2026-09-01');assert.ok(fetched.passages[0].retrieved_at);assert.match(fetched.passages[0].licence,/CC-BY/);
    const excluded = fetched.passages[0], allowed = fetched.passages[1];
    assert.ok(allowed, 'fixture supplies two independently checked passages');
    db.prepare('INSERT INTO content_question_versions VALUES(?,?,?,?,?)').run('synthetic-reserved',1,'synthetic-family',
      JSON.stringify({usage:'assessment_reserved',stem:excluded.text}),digest('synthetic-question'));
    const filtered=await domain.fetch({pmcid:'PMC10001',budget:{max_requests:2,max_credits:0},operationId:input.operationId,signal:input.signal});
    assert.deepEqual(filtered.passages.map(p=>p.id),[allowed.id]);
    assert.ok(!JSON.stringify(filtered).includes(excluded.text));
    const event={source_id:'L03',identity:{pmcid:'PMC10001'},changes:{repository_removed:true}};
    db.prepare('INSERT INTO knowledge_source_status_events VALUES(?,?,?,?,?)').run('synthetic-exclusion','L03',digest(canonical(event)),JSON.stringify(event),'2026-10-28');
    await assert.rejects(domain.current(filtered.source_restrictions_revision,input.signal),{code:'source_evidence_changed'});
    const withdrawn=await domain.fetch({pmcid:'PMC10001',budget:{max_requests:2,max_credits:0},operationId:input.operationId,signal:input.signal});
    assert.deepEqual(withdrawn.passages,[]);
    assert.equal(worker.channel.state().retained,0);
  } finally {await worker.close();db.close();await new Promise(resolve=>server.close(resolve));}
});
