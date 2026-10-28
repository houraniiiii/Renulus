// SPDX-License-Identifier: MIT
/** Synchronous, local BF01 commands. The integration-owned worker starts/commits BEGIN IMMEDIATE.
 * This module opens no database/transaction, performs no IO and never waits for a host or broker. */
import type { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { exact, integer, reject, text } from './contracts.ts';
import { canonical, digest, one, rows } from './schema.ts';
import { requireAssistance } from './conversation.ts';
import { ALLOWED_MODELS, BASE_URLS, BATCH_DISPATCHES, GENERATION, boundary, fit, hash, id, inspect,
  metadataHash, purpose, requestKind, resolveRole, routeFor, strings, validateFence, validateQualification, validateSpec } from '../dispatch/policy.ts';
import type { ConfigurationSpec, DispatchCommand, DispatchResults, Fence, Permit, Purpose, RequestProof, Route, Run, Snapshot } from '../dispatch/contracts.ts';

type DBRow = NonNullable<ReturnType<typeof one>>;
type RunData = { fence: Fence; batch_size: 5 | 10 | 20 | null; proofs: Record<string, RequestProof> };
const now = () => new Date().toISOString();
const uuid = () => randomUUID().replaceAll('-', '');
const read = (db: DatabaseSync, table: 'runs' | 'attempts', column: 'run_id' | 'permit_id', value: string) => {
  id(value); const row = one(db, `SELECT * FROM harness_configuration_${table} WHERE ${column}=?`, value);
  if (!row) reject(table === 'runs' ? 'run_missing' : 'permit_missing'); return row;
};
function configuration(db: DatabaseSync, version: string): ConfigurationSpec {
  hash(version); const row = one(db, 'SELECT payload_json FROM harness_configuration_versions WHERE version=?', version);
  if (!row || digest(String(row.payload_json)) !== version) reject('configuration_hash_mismatch');
  const spec = JSON.parse(String(row.payload_json)).spec as ConfigurationSpec; validateSpec(spec); return spec;
}
function snapshot(db: DatabaseSync): Snapshot {
  const p = one(db, 'SELECT * FROM harness_configuration_pointer WHERE id=1');
  const epoch = one(db, 'SELECT epoch FROM harness_configuration_grants WHERE id=1');
  if (!p || !epoch) reject('configuration_missing');
  return { requested: p.requested as string | null, effective: p.effective as string | null, previous: p.previous as string | null,
    activating: p.activating as string | null, failed: p.failed as string | null, failure_code: p.failure_code as string | null,
    admission_open: p.admission_open === 1, grant_epoch: Number(epoch.epoch),
    revoked: rows(db, 'SELECT capability FROM harness_configuration_revocations ORDER BY capability').map(r => String(r.capability)) };
}
function runRoute(row: DBRow): { route: Route; data: RunData; raw: Record<string, unknown> } {
  const raw = JSON.parse(String(row.route_json));
  const data = raw.dispatch_target as RunData | undefined;
  if (!data || typeof data !== 'object' || !data.proofs) reject('dispatch_target_unbound');
  validateFence(data.fence);
  if (!Object.hasOwn(ALLOWED_MODELS, raw.provider) || !(ALLOWED_MODELS[raw.provider as keyof typeof ALLOWED_MODELS] as readonly string[]).includes(raw.model_id)) reject('model_not_allowed');
  const route = routeFor({ provider: raw.provider, credential_reference: raw.credential_reference, credential_revision: raw.credential_revision, selected_model: raw.model_id }, raw.model_id);
  if (raw.endpoint !== BASE_URLS[route.provider_id] || raw.protocol !== (route.provider_id === 'codex' ? 'responses' : 'chat-completions')) reject('connection_changed');
  return { route, data, raw };
}
function projection(db: DatabaseSync, row: DBRow): Run {
  const { route, data, raw } = runRoute(row);
  const revoked = new Set(snapshot(db).revoked);
  let capabilities = JSON.parse(String(row.capabilities_json)) as string[];
  if (row.parent_id) {
    const parent = projection(db, read(db, 'runs', 'run_id', String(row.parent_id)));
    capabilities = capabilities.filter(c => parent.effective_capabilities.includes(c));
  }
  return { run_id: String(row.run_id), version: String(row.version), root_id: String(row.root_id), parent_id: row.parent_id as string | null,
    purpose: row.purpose as Purpose, state: row.state as Run['state'], dispatch_limit: Number(row.dispatch_limit), output_tokens: Number(raw.output_tokens),
    effective_capabilities: capabilities.filter(c => !revoked.has(c)).sort(), route, fence: data.fence, batch_size: data.batch_size };
}
function current(db: DatabaseSync, runId: string, fence: Fence, required: string[], permitId: string | null): Run {
  validateFence(fence); strings(required); requireAssistance(db);
  const row = read(db, 'runs', 'run_id', runId), result = projection(db, row), p = snapshot(db);
  if (result.state !== 'active' || canonical(result.fence) !== canonical(fence)) reject('run_unavailable');
  if (one(db, "SELECT 1 FROM preferences WHERE key='design_c.context_epoch' AND CAST(value AS INTEGER)<>?", fence.context_epoch)) reject('context_epoch_changed');
  const revoked = new Set(p.revoked); let ancestor: DBRow | null = row;
  while (ancestor) {
    const { route } = runRoute(ancestor);
    if (ancestor.state !== 'active' || [String(ancestor.run_id), String(ancestor.purpose), route.credential_ref, route.catalog_model_id].some((v, i) =>
      revoked.has(['run:', 'purpose:', 'connection:', 'model:'][i] + v))) reject('authority_revoked');
    ancestor = ancestor.parent_id ? read(db, 'runs', 'run_id', String(ancestor.parent_id)) : null;
  }
  if (permitId !== null) {
    const a = read(db, 'attempts', 'permit_id', permitId);
    if (a.run_id !== runId || !a.dispatch_purpose) reject('permit_authority_mismatch');
    if (revoked.has('purpose:' + a.dispatch_purpose)) reject('authority_revoked');
    required = [...new Set([...required, ...JSON.parse(String(a.required_capabilities_json))])];
    // A newer grant epoch fences publication even if a different capability was revoked.
    if (a.grant_epoch !== p.grant_epoch) reject('grant_epoch_changed');
  }
  if (!required.every(c => result.effective_capabilities.includes(c))) reject('capability_revoked');
  return result;
}
function requireOpen(db: DatabaseSync, version?: string) {
  const p = snapshot(db);
  if (!p.admission_open || !p.effective || (version !== undefined && version !== p.effective) ||
      one(db, 'SELECT state FROM harness_configuration_health WHERE version=?', p.effective)?.state !== 'ready') reject('configuration_not_active');
  return p;
}
function noPinnedRuns(db: DatabaseSync) {
  if (one(db, "SELECT 1 FROM harness_configuration_runs WHERE state<>'settled' LIMIT 1") ||
      one(db, "SELECT 1 FROM harness_configuration_attempts WHERE state IN ('reserved','dispatched') LIMIT 1")) reject('harness_configuration_busy');
}
function proofFits(db: DatabaseSync, run: Run, proof: RequestProof, required: string[], outputLimit: number) {
  exact(proof, ['qualification', 'payload_hash', 'wire_sha256', 'input_manifest_sha256', 'body_bytes', 'input_tokens', 'output_tokens']);
  hash(proof.payload_hash); hash(proof.wire_sha256); hash(proof.input_manifest_sha256); integer(proof.body_bytes, 1, 32 * 1024 * 1024);
  validateQualification(proof.qualification, run.route, required);
  if (proof.output_tokens > outputLimit) reject('deployment_output_exceeds_limit');
  fit(configuration(db, run.version), proof.qualification.limits, proof.input_tokens, proof.output_tokens);
}
function permit(db: DatabaseSync, permitId: string, allowed = false): Permit {
  const a = read(db, 'attempts', 'permit_id', permitId);
  if (!a.dispatch_purpose) reject('dispatch_purpose_unavailable');
  return { permit_id: String(a.permit_id), run_id: String(a.run_id), root_id: String(a.root_id), step_id: String(a.step_id),
    payload_hash: String(a.payload_hash), request_kind: a.request_kind as Permit['request_kind'], dispatch_purpose: a.dispatch_purpose as Purpose,
    grant_epoch: Number(a.grant_epoch), output_tokens: Number(a.output_tokens), required_capabilities: JSON.parse(String(a.required_capabilities_json)),
    state: a.state as Permit['state'], result_reference: a.result_reference as string | null, failure_code: a.failure_code as string | null, dispatch_allowed: allowed };
}
function insertRun(db: DatabaseSync, c: Extract<DispatchCommand, { type: 'dispatch.begin' | 'dispatch.child' }>) {
  id(c.runId); purpose(c.purpose); validateFence(c.fence); strings(c.capabilities); requireAssistance(db);
  if (!c.capabilities.includes('text')) reject('scope_widening');
  if (one(db, 'SELECT 1 FROM harness_configuration_runs WHERE run_id=?', c.runId)) reject('run_already_exists');
  const p = requireOpen(db), spec = configuration(db, p.effective!);
  if (!c.capabilities.every(value => spec.capabilities.includes(value))) reject('scope_widening');
  let parent: Run | undefined;
  if (c.type === 'dispatch.child') {
    parent = current(db, c.parentId, c.fence, [], null);
    const row = read(db, 'runs', 'run_id', c.parentId);
    if (Number(row.depth) >= spec.children.max_depth) reject('child_depth_exhausted');
    if (Number(one(db, "SELECT count(*) AS n FROM harness_configuration_runs WHERE root_id=? AND parent_id IS NOT NULL AND state='active'", parent.root_id)!.n) >= spec.children.concurrency) reject('child_concurrency_exhausted');
    if (!c.capabilities.every(value => parent!.effective_capabilities.includes(value))) reject('scope_widening');
  } else {
    if (c.expectedVersion !== p.effective) reject('activation_conflict');
    strings(c.availableModels); if (c.operationModel !== null) text(c.operationModel, 1, 128);
    if (GENERATION.has(c.purpose) ? ![5, 10, 20].includes(c.batchSize as number) : c.batchSize !== null) reject('generation_batch_required');
  }
  const role = resolveRole(spec, c.purpose, c.type === 'dispatch.begin' ? c.availableModels : [], c.operationModel, parent?.route.catalog_model_id ?? null);
  const route = routeFor(spec.connection, role.model), batch = parent?.batch_size ?? (c.type === 'dispatch.begin' ? c.batchSize : null);
  const limit = !parent && batch !== null ? Math.min(role.limit, BATCH_DISPATCHES[batch]) : role.limit;
  const data: RunData = { fence: c.fence, batch_size: batch, proofs: {} };
  const raw = { provider: route.provider_id, credential_reference: route.credential_ref, credential_revision: route.credential_epoch,
    model_id: route.catalog_model_id, output_tokens: role.output, endpoint: BASE_URLS[route.provider_id],
    protocol: route.provider_id === 'codex' ? 'responses' : 'chat-completions', dispatch_target: data };
  db.prepare("INSERT INTO harness_configuration_runs VALUES(?,?,?,?,?,?,?,?,?,'active',?)").run(c.runId, p.effective!, parent?.root_id ?? c.runId,
    parent?.run_id ?? null, c.purpose, parent ? 1 : 0, limit, canonical([...c.capabilities].sort()), canonical(raw), now());
  return current(db, c.runId, c.fence, c.capabilities, null);
}
function dispatchPurpose(db: DatabaseSync, run: Run, c: Extract<DispatchCommand, { type: 'dispatch.reserve' }>): Purpose {
  requestKind(c.requestKind);
  if (c.requestKind === 'transport-fallback') reject('transport_fallback_unavailable');
  if (c.requestKind === 'recovery') reject('dispatch_recovery_unavailable'); // Reconciliation observes receipts; it never resends them.
  if (c.requestKind === 'child' && !run.parent_id || ['primary', 'root', 'scheduled', 'generate'].includes(c.requestKind) && run.parent_id) reject('request_kind_not_allowed');
  if (c.requestKind === 'scheduled' && !['generated-practice', 'daily_suggestions', 'updates-digest'].includes(run.purpose)) reject('request_kind_not_allowed');
  if (c.requestKind === 'tool-continuation' || c.requestKind === 'continuation') {
    if (!c.continuationOf) reject('continuation_identity_required');
    const a = read(db, 'attempts', 'permit_id', c.continuationOf);
    const latest = one(db, 'SELECT permit_id FROM harness_configuration_attempts WHERE run_id=? ORDER BY rowid DESC LIMIT 1', run.run_id);
    if (a.run_id !== run.run_id || latest?.permit_id !== a.permit_id) reject('continuation_authority_mismatch');
    if (a.state !== 'confirmed') reject('continuation_not_confirmed');
    if (!a.dispatch_purpose) reject('dispatch_purpose_unavailable');
    return a.dispatch_purpose as Purpose;
  }
  if (c.continuationOf !== null) reject('invalid_continuation');
  if (c.requestKind === 'summary-repair' || c.requestKind === 'repair') {
    const latest = one(db, 'SELECT state,dispatch_purpose,failure_code FROM harness_configuration_attempts WHERE run_id=? ORDER BY rowid DESC LIMIT 1', run.run_id);
    if (!latest || latest.state !== 'failed' || latest.failure_code !== 'summary_invalid' || latest.dispatch_purpose !== 'compaction') reject('retry_not_allowed');
    return 'compaction';
  }
  if (['summary', 'compaction', 'title'].includes(c.requestKind)) return c.requestKind as Purpose;
  return run.purpose;
}
function budget(db: DatabaseSync, run: Run, p: Purpose): number {
  const root = read(db, 'runs', 'run_id', run.root_id);
  const attempts = rows(db, 'SELECT run_id,dispatch_purpose FROM harness_configuration_attempts WHERE root_id=?', run.root_id);
  if (attempts.some(a => !a.dispatch_purpose)) reject('dispatch_purpose_unavailable');
  const role = resolveRole(configuration(db, run.version), p, [], null, run.route.catalog_model_id);
  if (role.model !== run.route.catalog_model_id) reject('auxiliary_route_requires_own_run');
  if (attempts.length >= Number(root.dispatch_limit) || attempts.filter(a => a.dispatch_purpose === p).length >= role.limit ||
      run.parent_id && attempts.filter(a => a.run_id === run.run_id).length >= run.dispatch_limit) reject('dispatch_budget_exhausted');
  return role.output;
}
function handle(db: DatabaseSync, c: DispatchCommand): unknown {
  switch (c.type) {
    case 'dispatch.snapshot': exact(c, ['type']); return snapshot(db);
    case 'dispatch.configuration': exact(c, ['type', 'version']); return configuration(db, c.version);
    case 'dispatch.stage': {
      exact(c, ['type', 'spec', 'expectedEffective', 'expectedRequested', 'grantEpoch']); validateSpec(c.spec); integer(c.grantEpoch);
      const p = snapshot(db);
      if (p.effective !== c.expectedEffective || p.requested !== c.expectedRequested || p.activating || p.grant_epoch !== c.grantEpoch) reject('activation_conflict');
      const payload = canonical({ predecessor: p.effective, spec: c.spec }), version = digest(payload);
      db.prepare('INSERT OR IGNORE INTO harness_configuration_versions VALUES(?,?,?,?)').run(version, p.effective, payload, now());
      db.prepare("INSERT OR IGNORE INTO harness_configuration_health(version,state) VALUES(?,'staged')").run(version);
      db.prepare('UPDATE harness_configuration_pointer SET requested=? WHERE id=1').run(version); return { version };
    }
    case 'dispatch.inspect': {
      exact(c, ['type', 'inspection']); const p = snapshot(db), v = c.inspection.configuration_version;
      if (p.requested !== v || p.activating) reject('activation_conflict');
      const spec = configuration(db, v);
      try { inspect(spec, v, p.grant_epoch, c.inspection); }
      catch {
        db.prepare("UPDATE harness_configuration_health SET state='failed',failure_code='candidate_validation_failed' WHERE version=?").run(v);
        db.prepare("UPDATE harness_configuration_pointer SET failed=?,failure_code='candidate_validation_failed' WHERE id=1").run(v);
        return { ready: false };
      }
      db.prepare("UPDATE harness_configuration_health SET state='ready',registry_hash=?,grant_epoch=?,failure_code=NULL WHERE version=?").run(spec.registry_hash, p.grant_epoch, v);
      return { ready: true };
    }
    case 'dispatch.close': {
      exact(c, ['type', 'version', 'expectedEffective', 'grantEpoch']); const p = snapshot(db);
      if (p.requested !== c.version || p.effective !== c.expectedEffective || p.grant_epoch !== c.grantEpoch || p.activating) reject('activation_conflict');
      db.prepare('UPDATE harness_configuration_pointer SET admission_open=0 WHERE id=1').run(); return snapshot(db);
    }
    case 'dispatch.activate': {
      exact(c, ['type', 'version', 'expectedEffective', 'settlement']); const p = snapshot(db);
      boundary(c.settlement, c.version, p.grant_epoch); noPinnedRuns(db);
      const health = one(db, 'SELECT h.*,v.predecessor FROM harness_configuration_health h JOIN harness_configuration_versions v USING(version) WHERE version=?', c.version);
      if (p.admission_open || p.requested !== c.version || p.effective !== c.expectedEffective || p.activating || health?.state !== 'ready' || health.predecessor !== c.expectedEffective || health.grant_epoch !== p.grant_epoch) reject('activation_conflict');
      db.prepare('UPDATE harness_configuration_pointer SET previous=effective,effective=?,activating=?,admission_open=0 WHERE id=1').run(c.version, c.version); return snapshot(db);
    }
    case 'dispatch.open': {
      exact(c, ['type', 'inspection']); const p = snapshot(db), v = c.inspection.configuration_version;
      if (p.admission_open || p.requested !== v || p.effective !== v || p.activating !== v) reject('activation_conflict');
      inspect(configuration(db, v), v, p.grant_epoch, c.inspection);
      const h = one(db, 'SELECT * FROM harness_configuration_health WHERE version=?', v);
      if (h?.state !== 'ready' || h.grant_epoch !== p.grant_epoch) reject('candidate_authority_stale');
      db.prepare('UPDATE harness_configuration_pointer SET previous=NULL,activating=NULL,admission_open=1 WHERE id=1').run(); return snapshot(db);
    }
    case 'dispatch.begin': exact(c, ['type', 'runId', 'purpose', 'expectedVersion', 'capabilities', 'availableModels', 'operationModel', 'fence', 'batchSize']); return insertRun(db, c);
    case 'dispatch.child': exact(c, ['type', 'runId', 'parentId', 'purpose', 'capabilities', 'operationModel', 'fence']); return insertRun(db, c);
    case 'dispatch.run': exact(c, ['type', 'runId']); return projection(db, read(db, 'runs', 'run_id', c.runId));
    case 'dispatch.current':
      exact(c, ['type', 'runId', 'fence', 'requiredCapabilities', 'permitId', ...('grantEpoch' in c ? ['grantEpoch'] : [])]);
      if ('grantEpoch' in c) {
        integer(c.grantEpoch); if (snapshot(db).grant_epoch !== c.grantEpoch) reject('grant_epoch_changed');
      }
      return current(db, c.runId, c.fence, c.requiredCapabilities, c.permitId);
    case 'dispatch.reserve': {
      exact(c, ['type', 'runId', 'stepId', 'requestKind', 'continuationOf', 'requiredCapabilities', 'fence', 'proof']); id(c.stepId); strings(c.requiredCapabilities);
      const run = current(db, c.runId, c.fence, c.requiredCapabilities, null); requireOpen(db, run.version);
      const row = read(db, 'runs', 'run_id', c.runId), { data, raw } = runRoute(row);
      const previous = one(db, 'SELECT * FROM harness_configuration_attempts WHERE run_id=? AND step_id=?', c.runId, c.stepId);
      if (previous) {
        if (previous.payload_hash !== c.proof.payload_hash || previous.request_kind !== c.requestKind || metadataHash(data.proofs[String(previous.permit_id)]) !== metadataHash(c.proof) ||
            canonical(JSON.parse(String(previous.required_capabilities_json))) !== canonical([...c.requiredCapabilities].sort())) reject('idempotency_conflict');
        if (previous.state === 'dispatched' || previous.state === 'uncertain') reject('dispatch_uncertain');
        if (previous.state !== 'reserved' && previous.state !== 'confirmed') reject('retry_not_allowed');
        return permit(db, String(previous.permit_id));
      }
      if (one(db, "SELECT 1 FROM harness_configuration_attempts WHERE root_id=? AND state IN ('dispatched','uncertain') LIMIT 1", run.root_id)) reject('dispatch_uncertain');
      const p = dispatchPurpose(db, run, c), outputLimit = budget(db, run, p);
      if (snapshot(db).revoked.includes('purpose:' + p)) reject('authority_revoked');
      proofFits(db, run, c.proof, c.requiredCapabilities, outputLimit);
      const known = Object.values(data.proofs)[0]?.qualification;
      if (known && canonical(known) !== canonical(c.proof.qualification)) reject('deployment_evidence_stale');
      if (Number(one(db, "SELECT count(*) AS n FROM harness_configuration_attempts WHERE state IN ('reserved','dispatched','uncertain')")!.n) >= 2) reject('dispatch_concurrency_exhausted');
      if (Object.keys(data.proofs).length >= 128) reject('dispatch_budget_exhausted');
      const permitId = uuid(); data.proofs[permitId] = c.proof;
      db.prepare('UPDATE harness_configuration_runs SET route_json=? WHERE run_id=?').run(canonical({ ...raw, dispatch_target: data }), run.run_id);
      db.prepare("INSERT INTO harness_configuration_attempts(permit_id,run_id,root_id,step_id,payload_hash,request_kind,required_capabilities_json,retry_number,grant_epoch,output_tokens,state,created_at,dispatch_purpose) VALUES(?,?,?,?,?,?,?,0,?,?,'reserved',?,?)").run(
        permitId, run.run_id, run.root_id, c.stepId, c.proof.payload_hash, c.requestKind, canonical([...c.requiredCapabilities].sort()), snapshot(db).grant_epoch, c.proof.output_tokens, now(), p);
      return permit(db, permitId);
    }
    case 'dispatch.admit': {
      exact(c, ['type', 'permitId', 'fence', 'proof']); const a = permit(db, c.permitId);
      if (a.state !== 'reserved') reject('dispatch_already_admitted');
      const run = current(db, a.run_id, c.fence, a.required_capabilities, null); requireOpen(db, run.version);
      // A queued reservation predates effects admitted elsewhere in the same family.
      // Check again inside the final admission transaction, including parent/child attempts.
      if (one(db, "SELECT 1 FROM harness_configuration_attempts WHERE root_id=? AND permit_id<>? AND state IN ('dispatched','uncertain') LIMIT 1", a.root_id, a.permit_id)) reject('dispatch_uncertain');
      if (snapshot(db).revoked.includes('purpose:' + a.dispatch_purpose)) reject('authority_revoked');
      const { data } = runRoute(read(db, 'runs', 'run_id', a.run_id));
      if (canonical(data.proofs[a.permit_id]) !== canonical(c.proof)) reject('deployment_proof_changed');
      proofFits(db, run, c.proof, a.required_capabilities, a.output_tokens);
      // The commit enclosing this mutation is the network admission/revocation linearization point.
      db.prepare("UPDATE harness_configuration_attempts SET state='dispatched',grant_epoch=? WHERE permit_id=?").run(snapshot(db).grant_epoch, a.permit_id);
      return permit(db, a.permit_id, true);
    }
    case 'dispatch.permit': exact(c, ['type', 'permitId']); return permit(db, c.permitId);
    case 'dispatch.complete': {
      exact(c, ['type', 'permitId', 'outcome', 'resultReference', 'failureCode']); const a = permit(db, c.permitId);
      if (!['confirmed', 'failed', 'uncertain', 'cancelled_before_send'].includes(c.outcome)) reject('invalid_dispatch_outcome');
      if (c.resultReference !== null) id(c.resultReference);
      if (c.failureCode !== null && !['transport_unavailable', 'summary_invalid', 'authentication_required', 'subscription_limit', 'model_unavailable', 'input_unsupported', 'transport_timeout', 'broker_lost'].includes(c.failureCode)) reject('invalid_failure_code');
      if (c.outcome === 'confirmed' && (!c.resultReference || c.failureCode !== null) || c.outcome !== 'confirmed' && c.resultReference !== null) reject('invalid_dispatch_outcome');
      if (a.state === c.outcome && a.result_reference === c.resultReference && a.failure_code === c.failureCode) return a;
      if (a.state === 'reserved' && c.outcome !== 'cancelled_before_send') reject('dispatch_not_started');
      if (a.state !== 'reserved' && c.outcome === 'cancelled_before_send') reject('dispatch_may_have_sent');
      // Late known receipt reconciles uncertainty without issuing another request or removing a debit.
      if (!['reserved', 'dispatched'].includes(a.state) && !(a.state === 'uncertain' && c.outcome === 'confirmed')) reject('receipt_conflict');
      db.prepare('UPDATE harness_configuration_attempts SET state=?,result_reference=?,failure_code=? WHERE permit_id=?').run(c.outcome, c.resultReference, c.failureCode, a.permit_id);
      return permit(db, a.permit_id);
    }
    case 'dispatch.revoke': {
      exact(c, ['type', 'capability']); strings([c.capability]);
      db.prepare('UPDATE harness_configuration_grants SET epoch=epoch+1 WHERE id=1').run(); const epoch = snapshot(db).grant_epoch;
      db.prepare('INSERT OR IGNORE INTO harness_configuration_revocations VALUES(?,?,?)').run(c.capability, epoch, now());
      return { epoch };
    }
    case 'dispatch.settle': {
      exact(c, ['type', 'runId', 'settlement']); const row = read(db, 'runs', 'run_id', c.runId);
      boundary(c.settlement, String(row.version), snapshot(db).grant_epoch);
      if (one(db, "SELECT 1 FROM harness_configuration_attempts WHERE run_id=? AND state IN ('reserved','dispatched')", c.runId) ||
          one(db, "SELECT 1 FROM harness_configuration_runs WHERE parent_id=? AND state='active'", c.runId)) reject('run_not_settled');
      db.prepare("UPDATE harness_configuration_runs SET state='settled' WHERE run_id=?").run(c.runId); return projection(db, read(db, 'runs', 'run_id', c.runId));
    }
    case 'dispatch.reconcile': {
      exact(c, ['type', 'settlement']); const p = snapshot(db);
      boundary(c.settlement, p.effective, p.grant_epoch);
      if (p.admission_open) reject('restart_boundary_required');
      db.prepare("UPDATE harness_configuration_attempts SET state='uncertain',failure_code='broker_lost' WHERE state='dispatched'").run();
      db.prepare("UPDATE harness_configuration_attempts SET state='cancelled_before_send' WHERE state='reserved'").run();
      // The stopped host's runs have no execution left; their possibly-sent calls stay uncertain above.
      db.prepare("UPDATE harness_configuration_runs SET state='settled' WHERE state='active'").run();
      if (p.activating) {
        db.prepare("UPDATE harness_configuration_health SET state='failed',failure_code='activation_interrupted' WHERE version=?").run(p.activating);
        db.prepare("UPDATE harness_configuration_pointer SET effective=previous,previous=NULL,failed=activating,activating=NULL,failure_code='activation_interrupted' WHERE id=1").run();
      }
      return snapshot(db);
    }
    default: reject('storage_invalid_command');
  }
}
/** Add this union/results to the integration-owned storage contract and route it in transaction(true,...).
 * The sender and worker both call validation; command-specific strict validation happens here. */
export function executeDispatch<C extends DispatchCommand>(db: DatabaseSync, command: C): DispatchResults[C['type']] {
  if (!db.isTransaction) reject('configuration_transaction_required');
  return handle(db, command) as DispatchResults[C['type']];
}
/** Shape-only check suitable for the client; the canonical transaction validates every nested value. */
export function isDispatchCommand(value: unknown): value is DispatchCommand {
  return !!value && typeof value === 'object' && 'type' in value && typeof value.type === 'string' &&
    ['dispatch.snapshot', 'dispatch.configuration', 'dispatch.stage', 'dispatch.inspect', 'dispatch.close', 'dispatch.activate', 'dispatch.open',
      'dispatch.begin', 'dispatch.child', 'dispatch.run', 'dispatch.current', 'dispatch.reserve', 'dispatch.admit',
      'dispatch.permit', 'dispatch.complete', 'dispatch.revoke', 'dispatch.settle', 'dispatch.reconcile'].includes(value.type);
}
