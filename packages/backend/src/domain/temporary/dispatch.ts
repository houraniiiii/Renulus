// SPDX-License-Identifier: MIT
/** Volatile policy/permits only. Native OpenCode remains the transcript owner. */
import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { randomUUID } from 'node:crypto';
import type { ConfigurationSpec, DispatchCommand, DispatchResults, Fence, Inspection, Purpose, Run } from '../../dispatch/contracts.ts';
import type { DispatchStorage, NativeBinding } from '../../dispatch/native.ts';
import { executeDispatch } from '../../storage/dispatch.ts';
import { canonical } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';

const schemas = ['002-harness-configuration.sql', '004-harness-dispatch-purpose.sql'].map(name =>
  readFileSync(new URL('../../../../../runtime/renulus/runtime/migrations/' + name, import.meta.url), 'utf8'));

export async function createVolatileDispatchOwner(options: {
  spec: ConfigurationSpec;
  inspection: Omit<Inspection, 'configuration_version' | 'grant_epoch'>;
  identity: Fence;
  availableModels: readonly string[];
  checkCurrent?: () => Promise<void>;
}) {
  const db = new DatabaseSync(':memory:');
  db.exec('PRAGMA temp_store=MEMORY; PRAGMA foreign_keys=ON; CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);');
  for (const schema of schemas) db.exec(schema);
  const bindings = new Map<string, NativeBinding>();
  let closed = false;
  const execute = <C extends DispatchCommand>(command: C): DispatchResults[C['type']] => {
    if (closed) reject('volatile_dispatch_closed');
    db.exec('BEGIN IMMEDIATE');
    try { const result = executeDispatch(db, command); db.exec('COMMIT'); return result; }
    catch (error) { db.exec('ROLLBACK'); throw error; }
  };
  const storage: DispatchStorage = { command: async command => execute(command) };
  const { version } = execute({ type: 'dispatch.stage', spec: options.spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
  const inspection = { ...options.inspection, configuration_version: version, grant_epoch: 0 };
  try {
    if (!execute({ type: 'dispatch.inspect', inspection }).ready) reject('volatile_configuration_not_ready');
    execute({ type: 'dispatch.close', version, expectedEffective: null, grantEpoch: 0 });
    execute({ type: 'dispatch.activate', version, expectedEffective: null, settlement: {
      configuration_version: version, grant_epoch: 0, admission_closed: true, runtime_stopped: true, domain_settled: true } });
    execute({ type: 'dispatch.open', inspection });
  } catch (error) { db.close(); throw error; }
  async function begin(purpose: Purpose, capabilities = ['text'], runId = 'volatile_' + randomUUID().replaceAll('-', '')) {
    await options.checkCurrent?.();
    return execute({ type: 'dispatch.begin', runId, purpose, expectedVersion: version, capabilities,
      availableModels: [...options.availableModels], operationModel: null, fence: { ...options.identity },
      batchSize: purpose === 'fictional-test' || purpose === 'generated-practice' ? 5 : null });
  }
  async function bind(binding: NativeBinding, purpose: Purpose, capabilities = ['text']) {
    const prior = bindings.get(binding.operation_id);
    if (prior && canonical(prior) !== canonical(binding)) reject('volatile_binding_conflict');
    if (!prior) {
      await begin(purpose, capabilities, binding.operation_id);
      bindings.set(binding.operation_id, Object.freeze({ ...binding }));
    }
    return execute({ type: 'dispatch.run', runId: binding.operation_id });
  }
  async function resolve(binding: NativeBinding) {
    await options.checkCurrent?.();
    if (canonical(bindings.get(binding.operation_id)) !== canonical(binding)) reject('volatile_binding_unbound');
    const run = execute({ type: 'dispatch.run', runId: binding.operation_id }); return { runId: run.run_id, fence: run.fence };
  }
  async function checkCurrent(binding: NativeBinding, run: Run) {
    await resolve(binding);
    execute({ type: 'dispatch.current', runId: run.run_id, fence: run.fence, requiredCapabilities: [], permitId: null });
  }
  return { storage, version, begin, bind, resolve, checkCurrent,
    async cancel() { if (!closed) for (const id of bindings.keys()) execute({ type: 'dispatch.revoke', capability: 'run:' + id }); },
    /** Caller first settles native graph, callbacks and temporary worker transport. */
    close() { if (!closed) { closed = true; bindings.clear(); db.close(); } },
  };
}
