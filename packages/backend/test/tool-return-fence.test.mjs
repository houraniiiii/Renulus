// SPDX-License-Identifier: MIT
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFile } from 'node:fs/promises';
import { DatabaseSync } from 'node:sqlite';
import { Effect } from 'effect';
import { executeDispatch } from '../src/storage/dispatch.ts';
import { defaultConfiguration, ALLOWED_MODELS } from '../src/dispatch/policy.ts';
import { digest } from '../src/storage/schema.ts';
import { createToolReturnFence } from '../src/plugins/tool-return-fence.ts';
import { createKnowledgeTools, registerKnowledgeTools } from '../src/domain/knowledge/tools.ts';
import { createMemoryTools, createMemoryPlugin } from '../src/domain/memory/tools.ts';
import { createFindTools, createFindPlugin } from '../src/domain/find/tools.ts';
import { createAssessmentTools, createAssessmentPlugin } from '../src/domain/assessment/tools.ts';
import { createStudyTools, createStudyPlugin } from '../src/domain/study/tools.ts';
import { createUpdatesTools, createUpdatesPlugin } from '../src/domain/updates/tools.ts';
import { createEvidencePlugin } from '../src/domain/evidence/tools.ts';
import { createLearningTools, createLearningPlugins } from '../src/domain/learning/tools.ts';

const migrations = await Promise.all(['002-harness-configuration.sql','004-harness-dispatch-purpose.sql'].map(name =>
  readFile(new URL('../../../runtime/renulus/runtime/migrations/' + name, import.meta.url), 'utf8')));
const cases = [
  ['renulus_source_read', 'renulus.source.read', { reference: { target: { type: 'library_revision', id: 'revision' } } }],
  ['renulus_note_read', 'renulus.note.read', { reference: { target: { type: 'note_revision', id: 'revision' } } }],
  ['renulus_note_propose', 'renulus.note.propose', { title: 'Synthetic', text: 'Synthetic CKD' }],
  ['renulus_project_read', 'renulus.project.read', { project_id: 'project' }],
  ['renulus_memory_recall', 'renulus.memory.recall', { query: 'Synthetic AKI' }],
  ['renulus_find', 'renulus.find', { query: 'Synthetic transplant' }],
  ['renulus_study_help', 'renulus.study.help', { kind: 'hint' }],
  ['renulus_practice_propose', 'renulus.practice.propose', { title: 'Synthetic', focus: 'Dialysis', count: 5 }],
  ['renulus_plan_propose', 'renulus.plan.propose', {}],
  ['renulus_updates_read', 'renulus.updates.read', {}],
  ['renulus_evidence_search', 'renulus.evidence.search', { query: 'Synthetic kidney study' }],
  ['renulus_evidence_fetch', 'renulus.evidence.fetch', { pmcid: 'PMC10001' }],
  ['renulus_context_refs', 'renulus.context.read', {}],
  ['renulus_history_range', 'renulus.history.read', { first_message_id: 'message', last_message_id: 'message' }],
];

test('registered learning tools refuse returns after own or unrelated grant revocation, with an unrevoked control', async () => {
  for (const [name, permission, input] of cases) for (const mode of ['control','own','other']) {
    const db = new DatabaseSync(':memory:');
    db.exec(migrations.join('\n') + 'CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);');
    function dispatch(command) {
      db.exec('BEGIN IMMEDIATE');
      try { const result = executeDispatch(db, command); db.exec('COMMIT'); return result; }
      catch (error) { db.exec('ROLLBACK'); throw error; }
    }
    const spec = defaultConfiguration({ provider: 'codex', credential_reference: 'synthetic', credential_revision: 1,
      selected_model: ALLOWED_MODELS.codex[0] }, digest('synthetic-registry'));
    spec.capabilities = ['text', ...cases.map(row => row[1])];
    const { version } = dispatch({ type: 'dispatch.stage', spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
    const inspection = { configuration_version: version, grant_epoch: 0, registry_hash: spec.registry_hash, loaded_inputs: spec.inputs,
      healthy: true, generation_open: false, recovery_open: false, package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false };
    dispatch({ type: 'dispatch.inspect', inspection });
    dispatch({ type: 'dispatch.activate', version, expectedEffective: null, settlement: { configuration_version: version, grant_epoch: 0,
      admission_closed: true, runtime_stopped: true, domain_settled: true } });
    dispatch({ type: 'dispatch.open', inspection });
    const fence = { profile_id: 'synthetic', domain_store_id: 'domain', runtime_store_id: 'native', authority_epoch: 1,
      process_generation: 'process', context_epoch: 0, deletion_epoch: 0, cancellation_epoch: 0 };
    dispatch({ type: 'dispatch.begin', runId: 'run', purpose: 'explain', expectedVersion: version, capabilities: spec.capabilities,
      availableModels: [...ALLOWED_MODELS.codex], operationModel: null, fence, batchSize: null });
    const entered = Promise.withResolvers(), gate = Promise.withResolvers();
    const checkpoint = { history: [{ runId: 'old' }], consumed: [], memory: [] };
    const deps = { async resolve() { entered.resolve(); await gate.promise; return { operationId: 'run', attemptId: '1', sessionId: 'session',
      grants: spec.capabilities, projectId: 'project', scope: { kind: 'study', entity_id: 'project' }, allowedRevisionIds: ['revision'],
      policyRevision: 0, contextEpoch: 0, studyAttemptId: 'study', threadId: 'thread', checkpoint }; }, check: async () => {}, consume: async () => {} };
    const storage = { async command(c) {
      if (c.type.startsWith('dispatch.')) return dispatch(c);
      if (c.type === 'updates.entries') return { entries: [] };
      if (c.type === 'assessment.attempts.get') return { mode: 'study', status: 'active', current_item: { item_id: 'item' }, policy: { revision: 1 }, draft_revision: 1 };
      if (c.type === 'assessment.attempts.help') return { context: {}, hint: 'Synthetic help', references: [] };
      return { revision: 1 };
    } };
    const learning = createLearningPlugins(createLearningTools({ ...deps,
      references: async () => [{ reference: { run_id: 'old', input_id: 'message', message_ids: ['message'], citations: [] } }],
      range: async () => ({ messages: [{ id: 'message', type: 'user', parts: [{ type: 'text', text: 'Synthetic' }] }], cursor: null }) }));
    const plugins = [
      { effect: context => registerKnowledgeTools(context, createKnowledgeTools({ ...deps, storage, knowledge: { source: async () => ({ text: 'Synthetic', dependency: {} }) } })) },
      createMemoryPlugin(createMemoryTools({ ...deps, memory: { recall: async () => ({ records: [], dependencies: [] }) } })),
      createFindPlugin(createFindTools({ ...deps, find: async () => ({ items: [] }) })),
      createAssessmentPlugin(createAssessmentTools({ ...deps, storage })),
      createStudyPlugin(createStudyTools({ ...deps, storage })), createUpdatesPlugin(createUpdatesTools({ ...deps, storage })),
      createEvidencePlugin({ ...deps, evidence: { search: async () => ({}), fetch: async () => ({ passages: [], source_restrictions_revision: 'synthetic' }), current: async () => {} } }),
      learning.context, learning.history, createToolReturnFence(storage, () => ({ operation_id: 'run', attempt_id: '1', session_id: 'session' }), () => true),
    ];
    const tools = new Map(), editor = { add(tool) { tools.set(tool.name, { ...tool, id: tool.name }); }, list: () => [...tools.values()],
      update(id, change) { change(tools.get(id)); } };
    const context = { tool: { transform: change => Effect.sync(() => change(editor)) } };
    try {
      for (const plugin of plugins) await Effect.runPromise(plugin.effect(context));
      const pending = Effect.runPromise(tools.get(name).execute(input, { sessionID: 'session', id: 'call', messageID: 'message', agent: 'renulus' }));
      const observed = pending.then(value => ({ value }), error => ({ error }));
      await entered.promise;
      if (mode !== 'control') dispatch({ type: 'dispatch.revoke', capability: mode === 'own' ? permission : 'purpose:summary' });
      gate.resolve();
      const result = await observed;
      if (mode === 'control') { assert.equal(result.error, undefined, name + ': ' + result.error); assert.ok(result.value.content, name); }
      else { assert.ok(result.error, name + ': ' + mode); assert.match(String(result.error), /tool_authority_revoked/, name); }
    } finally { gate.resolve(); db.close(); }
  }
});
