// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { canonical, digest } from '../src/storage/schema.ts';
import { executeMemoryCommand, queueMemoryCapture, reconcileMemorySupport } from '../src/storage/memory.ts';

test('restore capture barrier survives automatic/global retry and failed revalidation; explicit capture consumes only its own barrier once', () => {
  const db = new DatabaseSync(':memory:');
  db.exec(`PRAGMA foreign_keys=ON;
    CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT);
    CREATE TABLE deletion_ledger(entity_type TEXT,entity_id TEXT,deleted_at TEXT,PRIMARY KEY(entity_type,entity_id));
    CREATE TABLE learning_evidence(id TEXT PRIMARY KEY,kind TEXT,topic_id TEXT,entity_id TEXT,payload_json TEXT,created_at TEXT);
    CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);`);
  for (const name of ['learn/schema.sql', 'memory/schema.sql', 'memory/migrations/002.sql']) db.exec(readFileSync(new URL('../../../runtime/renulus/' + name, import.meta.url), 'utf8'));
  const evidenceId = 'learn-answer:run_restore', barrier = 'memory.restore_barrier:' + evidenceId, stamp = 'synthetic';
  const body = 'Synthetic restored general educational learning';
  const reference = { version: 1, run_id: 'run_restore', message_id: 'message_restore', sha256: digest(body) };
  const scope = { kind: 'study', entity_id: 'thread_restore' }, manifest = { version: 1, inputs: [], dependencies: [] };
  const evidence = { id: evidenceId, kind: 'study-answer', topic_id: 'aki', entity_id: scope.entity_id,
    payload_json: canonical({ scope, answer_reference: reference }), created_at: stamp };
  const publication = digest(canonical({ evidence, manifest, project_id: null }));
  db.prepare("INSERT INTO learn_threads VALUES('thread_restore','Synthetic restore','aki','direct',?,?)").run(stamp, stamp);
  db.prepare("INSERT INTO learn_runs VALUES('run_restore','thread_restore','synthetic-key','completed',NULL,?,?)").run(stamp, stamp);
  db.prepare("INSERT INTO learn_messages VALUES('message_restore','thread_restore','run_restore','assistant',?,'[]',?)").run(body, stamp);
  db.prepare('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)').run(...Object.values(evidence));
  db.prepare("INSERT INTO memory_answer_lineage VALUES(?,?,?,'revoked',NULL,?)").run(evidenceId, publication, canonical(manifest), stamp);
  db.prepare("INSERT INTO memory_jobs VALUES('capture_restored',?,? ,?,'cancelled',4,'restore_explicit_capture',?,?)").run(evidenceId, 'old-foreign-fingerprint', canonical(scope), stamp, stamp);
  db.prepare('INSERT INTO preferences VALUES(?,?,?)').run(barrier, 'explicit-capture-required', stamp);
  db.prepare('INSERT INTO preferences VALUES(?,?,?)').run('memory.restore_barrier:another-evidence', 'explicit-capture-required', stamp);
  // Recovery reconciliation removes unsupported imported facts without turning
  // the recoverable restore quarantine into terminal user suppression.
  db.prepare("INSERT INTO memory_facts VALUES('memory_restored',?,'hash','learning-point','aki','study',1,'evidence',?,?,?)").run(body, evidenceId, stamp, stamp);
  db.prepare("INSERT INTO memory_sources VALUES(?,'memory_restored')").run('evidence:' + evidenceId);
  db.prepare("INSERT INTO memory_support_groups VALUES('group_restored','memory_restored',?,'generated','active',NULL)").run('evidence:' + evidenceId);
  const transaction = fn => {
    db.exec('BEGIN IMMEDIATE');
    try { const result = fn(); db.exec('COMMIT'); return result; }
    catch (error) { db.exec('ROLLBACK'); throw error; }
  };
  const command = c => transaction(() => executeMemoryCommand(db, c));
  try {
    transaction(() => reconcileMemorySupport(db));
    assert.equal(db.prepare('SELECT count(*) AS n FROM memory_suppression').get().n, 0);
    transaction(() => queueMemoryCapture(db, evidenceId));
    assert.equal(command({ type: 'memory.capture.claim', evidenceId, retry: false }), null);
    assert.equal(command({ type: 'memory.capture.claim', evidenceId, retry: true }), null);
    assert.equal(db.prepare('SELECT state FROM memory_jobs').get().state, 'cancelled');
    assert.equal(db.prepare('SELECT count(*) AS n FROM preferences WHERE key LIKE ?').get('memory.restore_barrier:%').n, 2);
    db.prepare("UPDATE learn_messages SET content='changed source'").run();
    assert.throws(() => command({ type: 'memory.capture.explicit', evidenceId }), { code: 'memory_evidence_invalid' });
    assert.equal(db.prepare('SELECT state FROM memory_answer_lineage').get().state, 'revoked');
    assert.equal(db.prepare('SELECT value FROM preferences WHERE key=?').get(barrier).value, 'explicit-capture-required');
    db.prepare('UPDATE learn_messages SET content=?').run(body);
    const ticket = command({ type: 'memory.capture.explicit', evidenceId });
    assert.equal(ticket.jobId, 'capture_restored'); assert.equal(ticket.attempt, 5);
    assert.equal(db.prepare('SELECT value FROM preferences WHERE key=?').get(barrier), undefined);
    assert.equal(db.prepare('SELECT count(*) AS n FROM preferences WHERE key LIKE ?').get('memory.restore_barrier:%').n, 1);
    assert.equal(db.prepare('SELECT state FROM memory_answer_lineage').get().state, 'active');
    assert.equal(command({ type: 'memory.capture.explicit', evidenceId }), null);
    assert.equal(command({ type: 'memory.capture.claim', evidenceId, retry: true }), null);
    command({ type: 'memory.capture.check', ticket });
  } finally { db.close(); }
});
