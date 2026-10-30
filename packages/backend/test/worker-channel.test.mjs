// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openEngineWorker } from "../src/workers/process.ts";
import { WorkerChannel } from "../src/workers/channel.ts";
import { DEFAULT_WORKER_CAPACITY } from "../src/workers/process.ts";
import { PassThrough } from "node:stream";
import { canonicalJson, decodeWorkerFrame } from "../src/contracts/worker-codec.ts";

const repository = fileURLToPath(new URL("../../..", import.meta.url));
const identity = { profile_id: "synthetic", domain_store_id: "synthetic-domain", runtime_store_id: "synthetic-native",
  authority_epoch: 1, process_generation: "synthetic-generation" };
const binding = { operation_id: "synthetic-memory", attempt_id: "attempt-1" };
const initialRevisions = () => ({ configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 });
const digest = value => createHash("sha256").update(canonicalJson(value)).digest("hex");
const turn = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
async function within(promise, milliseconds = 10_000) {
  let timer;
  try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("test_observation_timeout")), milliseconds); })]); }
  finally { clearTimeout(timer); }
}
const outputGrant = (handle = "synthetic-output") => ({ artifact_handle: handle, artifact_revision: 1,
  max_bytes: 16384, expires_at_ms: Date.now() + 120_000, reservation_id: "synthetic-reservation", intent_id: "synthetic-intent" });
function extractInput() {
  return { artifact_handle: "synthetic-source", artifact_revision: 1, offset: 0, length: 32, output: outputGrant(),
    capture_plan: { plan_id: "synthetic-plan", evidence_receipt: "synthetic-receipt", support_sha256: "a".repeat(64),
      source_sha256: "b".repeat(64), expires_at_ms: Date.now() + 120_000, max_calls: 1 } };
}
function reply(command, outcome = "accepted_pending", lease = "synthetic-lease") {
  return { protocol: "renulus-worker/1", kind: "reply",
    identity: Object.fromEntries([...Object.keys(identity), "operation_id", "attempt_id", "request_id"].map(key => [key, command[key]])),
    request_sha256: command.payload_sha256,
    revisions: { configuration: command.configuration_revision, grant: command.grant_revision, context: command.context_epoch,
      deletion: command.deletion_epoch, cancellation: command.cancellation_epoch }, outcome,
    result: { tag: "state", active: outcome === "accepted_pending" ? 1 : 0, closing: false },
    settlement: { worker_lease: lease, state: outcome === "accepted_pending" ? "pending" : "settled" } };
}
function generation(command) {
  const admission = reply(command);
  const frame = { protocol: "renulus-worker/1", kind: "generation_request", target: {
    identity: admission.identity, request_sha256: admission.request_sha256, worker_lease: admission.settlement.worker_lease },
    revisions: admission.revisions, retention: command.retention, capture_plan: command.input.capture_plan,
    messages: [{ role: "user", content: "Synthetic AKI and transplant learning. Unicode: α 🩺" }] };
  return { ...frame, callback_id: "synthetic-callback", generation_sha256: digest(frame), action: "generate" };
}
async function channelFixture(generate, capacity = {}) {
  const input = new PassThrough(), output = new PassThrough(), sent = [], revisions = initialRevisions();
  output.on("data", bytes => sent.push(...bytes.toString().trim().split("\n").map(JSON.parse)));
  const limits = { ...DEFAULT_WORKER_CAPACITY, ...capacity };
  const channel = new WorkerChannel(input, output, identity, 123, limits, () => revisions, "saved", generate);
  const send = frame => input.write(JSON.stringify(frame) + "\n");
  const hello = channel.hello("synthetic-token-abcdefghijklmnopqrstuvwxyz");
  send({ protocol: "renulus-worker/1", kind: "ready", identity, pid: 123, parent_pid: 100,
    process: { launcher_pid: 123, actual_pid: 123, launcher_creation_filetime: "10", actual_creation_filetime: "10", ancestry_depth: 0 },
    capacity: limits, supported_commands: ["worker.settle", "memory.extract"], unavailable_commands: [] });
  await hello;
  return { channel, send, sent, revisions };
}

test("missing generation handler rejects extraction before admission or data lifetime consumption", async () => {
  const f = await channelFixture(undefined, { request_count: 1 });
  assert.throws(() => f.channel.submit("memory.extract", extractInput(), binding), /worker_generation_handler_required/);
  assert.equal(f.channel.state().retained, 0);
  assert.equal(f.sent.length, 1);
  const call = f.channel.submit("native.inspect", {}, binding);
  assert.equal(f.sent.at(-1).request_id, call.requestId);
  f.channel.disconnect();
});

test("bound submit uses channel-minted identity before hashing and shares strict admission and capacity", async () => {
  const f = await channelFixture(undefined, { request_count: 1 });
  const factoryFailure = new Error("synthetic-factory-failure");
  assert.throws(() => f.channel.submitBound("native.inspect", () => { throw factoryFailure; }, binding), factoryFailure);
  assert.throws(() => f.channel.submitBound("native.inspect", () => ({ unexpected: true }), binding));
  assert.equal(f.channel.state().retained, 0);
  let minted;
  const call = f.channel.submitBound("native.inspect", (requestIdentity, revisions) => {
    minted = structuredClone(requestIdentity);
    assert.deepEqual(revisions, f.revisions);
    requestIdentity.request_id = "caller-must-not-replace-it";
    revisions.grant = 99;
    return {};
  }, binding);
  assert.deepEqual(minted, reply(f.sent.at(-1)).identity);
  assert.equal(minted.request_id, call.requestId);
  assert.equal(f.sent.at(-1).payload_sha256, digest({}));
  assert.equal(f.sent.at(-1).grant_revision, 1);
  let called = false;
  assert.throws(() => f.channel.submitBound("native.inspect", () => { called = true; return {}; }, binding), /worker_overloaded/);
  assert.equal(called, false);
  f.channel.disconnect();
});

test("bound transport plan is the exact input and binds its minted request identity/revisions before digesting", async () => {
  const f = await channelFixture();
  const call = f.channel.submitBound("transport.execute", (requestIdentity, revisions) => {
    const body = Buffer.from('{"model":"gpt-6.1-sol","stream":true,"input":[],"max_output_tokens":32}');
    // In-memory pipe fixture only; this test never opens a transport.
    const serialized_request = { method: "POST", url: "https://api.openai.com/v1/responses",
      headers: [{ name: "content-type", value: "application/json" }], body_base64: body.toString("base64") };
    return { permit_id: "synthetic-permit-".repeat(2), admission_receipt: "synthetic-admission", identity: requestIdentity,
      revisions, retention: "saved", route: { provider_id: "codex", model_id: "gpt-6.1-sol", wire_model_id: "gpt-6.1-sol",
        endpoint: serialized_request.url, protocol: "openai-responses", credential_ref: "synthetic-reference", credential_revision: 1 },
      native_manifest_sha256: "a".repeat(64), registry_sha256: "b".repeat(64),
      request_sha256: createHash("sha256").update(body).digest("hex"), request_bytes: body.length,
      envelope_sha256: digest(serialized_request), max_output_tokens: 32, expires_at_ms: Date.now() + 60_000,
      output: outputGrant(), serialized_request };
  }, binding);
  const command = f.sent.at(-1);
  assert.deepEqual(command.input.identity, reply(command).identity);
  assert.deepEqual(command.input.revisions, f.revisions);
  assert.equal(command.input.identity.request_id, call.requestId);
  assert.equal(command.input.retention, command.retention);
  assert.equal(command.payload_sha256, digest(command.input));
  assert.equal(command.input.permit_id, "synthetic-permit-".repeat(2));
  assert.equal(command.input.plan, undefined);
  f.channel.disconnect();
});

test("reverse dispatch checks retained identity, digest, lease, revisions and capture plan before calling host", async () => {
  const mutations = [
    ...[...Object.keys(identity), "operation_id", "attempt_id", "request_id"].map(key => frame => {
      frame.target.identity[key] = key === "authority_epoch" ? 2 : "different";
    }),
    frame => { frame.target.request_sha256 = "c".repeat(64); },
    frame => { frame.target.worker_lease = "different-lease"; },
    ...Object.keys(initialRevisions()).map(key => frame => { frame.revisions[key]++; }),
    frame => { frame.retention = "temporary"; },
    ...["plan_id", "evidence_receipt", "support_sha256", "source_sha256", "expires_at_ms"].map(key => frame => {
      frame.capture_plan[key] = key === "expires_at_ms" ? Date.now() + 1000 : key.endsWith("sha256") ? "c".repeat(64) : "different";
    }),
  ];
  for (const mutate of [...mutations, null]) {
    let calls = 0;
    const f = await channelFixture(async () => { calls++; return { status: "completed", output: "{}" }; });
    const call = f.channel.submit("memory.extract", extractInput(), binding);
    const command = f.sent.at(-1), admitted = reply(command);
    f.send(admitted);
    await call.admission;
    const frame = structuredClone(generation(command));
    if (mutate) {
      mutate(frame);
      const { generation_sha256: _digest, callback_id: _callback, action: _action, ...payload } = frame;
      frame.generation_sha256 = digest(payload);
    } else frame.messages[0].content += " tampered";
    f.send(frame);
    await assert.rejects(call.terminal, /worker_generation_mismatch/);
    assert.equal(calls, 0);
    assert.equal(f.channel.state().retained, 1);
    assert.deepEqual(f.channel.observe(call.requestId).reply, admitted);
    assert.throws(() => f.channel.release(call.requestId), /worker_settlement_pending/);
  }
});

test("reverse lane may overtake admission, dispatches once, and returns exact host settlement", async () => {
  const host = deferred(); let calls = 0;
  const f = await channelFixture(async request => {
    calls++;
    request.target.worker_lease = "host-copy-only";
    return host.promise;
  }, { request_count: 1 });
  const call = f.channel.submit("memory.extract", extractInput(), binding), command = f.sent.at(-1);
  const request = generation(command);
  f.send(request);
  await turn();
  assert.equal(calls, 0);
  f.send(reply(command));
  await turn();
  assert.equal(calls, 1);
  host.resolve({ status: "completed", output: '{"memory":[{"text":"Synthetic fact"}]}' });
  await turn();
  const settlement = f.sent.at(-1);
  assert.equal(settlement.command, "worker.settle");
  assert.deepEqual(settlement.input, { action: "generation", target: request.target, generation: {
    callback_id: request.callback_id, plan_id: request.capture_plan.plan_id, generation_sha256: request.generation_sha256,
    status: "completed", output: '{"memory":[{"text":"Synthetic fact"}]}' } });
  assert.equal(settlement.payload_sha256, digest(settlement.input));
  f.send(reply(settlement));
  f.send(reply(command, "committed_reference"));
  await call.terminal;
  f.channel.release(call.requestId);
  await turn();
  assert.equal(f.channel.state().retained, 0);
  assert.equal(calls, 1);
  f.channel.disconnect();
});

test("cancellation retains host promise while controls drain, then settles under acknowledged current revisions", async () => {
  const host = deferred(); let signal;
  const f = await channelFixture(async (_request, cancellation) => { signal = cancellation; return host.promise; },
    { request_count: 1, control_slots: 1 });
  const call = f.channel.submit("memory.extract", extractInput(), binding), command = f.sent.at(-1);
  const request = generation(command);
  f.send(reply(command)); f.send(request); await turn();
  f.send({ ...request, action: "cancel", messages: [] });
  assert.equal(signal.aborted, true);
  let settled = false;
  void call.terminal.then(() => { settled = true; });
  const query = f.channel.submit("worker.settle", { action: "query", target: request.target }, binding);
  const queryCommand = f.sent.at(-1);
  host.resolve({ status: "cancelled", output: null });
  await turn();
  assert.equal(f.sent.at(-1), queryCommand); // Occupied control slot keeps the settlement queued.
  f.revisions.deletion++;
  f.send(reply(queryCommand));
  await query.terminal; f.channel.release(query.requestId);
  assert.equal(settled, false);
  assert.equal(f.sent.at(-1), queryCommand); // Current authority must be acknowledged before delivery.
  const revoked = f.channel.revoke(binding), revokeCommand = f.sent.at(-1);
  f.send(reply(revokeCommand));
  await revoked; await turn();
  const settlement = f.sent.at(-1);
  assert.equal(settlement.input.action, "generation");
  assert.equal(settlement.deletion_epoch, 2);
  assert.deepEqual(settlement.input.target, request.target);
  assert.equal(settlement.input.generation.status, "cancelled");
  assert.equal(settlement.input.generation.output, null);
  f.send(reply(settlement));
  assert.equal(settled, false);
  f.send(reply(command, "cancelled_settled"));
  assert.equal((await call.terminal).current, false);
  f.channel.release(call.requestId);
  await turn();
  assert.equal(f.channel.state().retained, 0);
  f.channel.disconnect();
});

test("duplicate callback and disconnect retain the original lease without false settlement or redispatch", async () => {
  const host = deferred(); let calls = 0, signal;
  const f = await channelFixture(async (_request, cancellation) => { calls++; signal = cancellation; return host.promise; });
  const call = f.channel.submit("memory.extract", extractInput(), binding), command = f.sent.at(-1);
  const request = generation(command);
  f.send(reply(command)); f.send(request); await turn();
  f.send(request);
  await assert.rejects(call.terminal, /worker_generation_mismatch/);
  assert.equal(signal.aborted, true);
  host.resolve({ status: "cancelled", output: null }); await turn();
  assert.equal(calls, 1);
  assert.equal(f.sent.filter(frame => frame.input?.action === "generation").length, 0);
  assert.equal(f.channel.observe(call.requestId).reply.settlement.worker_lease, request.target.worker_lease);
  assert.equal(f.channel.state().unsettled, 1);
});

test("settled host failure reports failed, while refused worker delivery retains the original admission", async () => {
  const f = await channelFixture(async () => { throw new Error("synthetic host failure after closure"); });
  const call = f.channel.submit("memory.extract", extractInput(), binding), command = f.sent.at(-1);
  const admitted = reply(command);
  f.send(admitted); f.send(generation(command)); await turn();
  const settlement = f.sent.at(-1);
  assert.equal(settlement.input.action, "generation");
  assert.equal(settlement.input.generation.status, "failed");
  assert.equal(settlement.input.generation.output, null);
  f.send(reply(settlement, "rejected_before_admission"));
  await assert.rejects(call.terminal, /worker_generation_settlement_held/);
  assert.deepEqual(f.channel.observe(call.requestId).reply, admitted);
  assert.throws(() => f.channel.release(call.requestId), /worker_settlement_pending/);
});

test("shared Effect worker codec rejects unknown fields, nonfinite numbers and malformed identity", () => {
  for (const input of [{ protocol: "renulus-worker/2" }, { kind: "ready", extra: true }, { kind: "reply", identity: { authority_epoch: Infinity } }])
    assert.throws(() => decodeWorkerFrame(input));
});

test("worker channel rejects a false protocol before readiness and retains uncertain leases on disconnect", async () => {
  const input = new PassThrough(), output = new PassThrough();
  const identity = { profile_id: "synthetic", domain_store_id: "synthetic-domain", runtime_store_id: "synthetic-native",
    authority_epoch: 1, process_generation: "synthetic-generation" };
  const revision = { configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 };
  const channel = new WorkerChannel(input, output, identity, 123, DEFAULT_WORKER_CAPACITY, () => revision, "saved");
  const hello = channel.hello("synthetic-token-abcdefghijklmnopqrstuvwxyz");
  input.write(JSON.stringify({ kind: "ready", identity, pid: 123, parent_pid: 100,
    process: { launcher_pid: 123, actual_pid: 123, launcher_creation_filetime: "10", actual_creation_filetime: "10", ancestry_depth: 0 },
    capacity: DEFAULT_WORKER_CAPACITY, supported_commands: ["worker.settle"], unavailable_commands: [] }) + "\n");
  await assert.rejects(hello, /worker_protocol_mismatch/);
  assert.equal(channel.state().connected, false);
});

test("Node host exchanges chunked artifacts with real Python worker and propagates revocation", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 45_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-bf00-worker-host-"));
  const revisions = { configuration: 1, grant: 1, context: 1, deletion: 1, cancellation: 0 };
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON,
    sourceRoot: fileURLToPath(new URL("../../..", import.meta.url)), launchRoot: root, retention: "temporary",
    identity: { profile_id: "synthetic-profile", domain_store_id: "synthetic-domain", runtime_store_id: "synthetic-native",
      authority_epoch: 1, process_generation: "synthetic-worker-1" }, current: () => ({ ...revisions }) });
  const binding = { operation_id: "synthetic-upload", attempt_id: "attempt-1" };
  const request = async (command, input) => {
    const call = worker.channel.submit(command, input, binding);
    const result = await call.terminal;
    worker.channel.release(call.requestId);
    return result;
  };
  try {
    assert.equal(worker.ready.pid, worker.pid);
    const body = Buffer.from("Synthetic AKI, glomerular disease and transplantation note. ".repeat(9000));
    const grant = { artifact_handle: "synthetic-artifact", artifact_revision: 1, artifact_sha256: createHash("sha256").update(body).digest("hex"),
      bytes: body.length, expires_at_ms: Date.now() + 60_000, rights: ["read", "extract"],
      permitted_ranges: [{ offset: 0, length: body.length }], reservation_id: "synthetic-reservation", intent_id: "synthetic-intent" };
    for (let offset = 0; offset < body.length; offset += worker.ready.capacity.max_chunk_bytes) {
      const chunk = body.subarray(offset, offset + worker.ready.capacity.max_chunk_bytes);
      const upload = await request("artifact.upload", { artifact: grant, offset, data_base64: chunk.toString("base64"), final: offset + chunk.length === body.length });
      assert.equal(upload.reply.outcome, "committed_reference");
      assert.equal(upload.current, true);
    }
    const read = await request("artifact.read", { artifact_handle: grant.artifact_handle, artifact_revision: 1, offset: 0, length: 100 });
    assert.equal(Buffer.from(read.reply.result.data_base64, "base64").toString(), body.subarray(0, 100).toString());
    revisions.grant++;
    assert.throws(() => worker.channel.submit("artifact.read", { artifact_handle: grant.artifact_handle, artifact_revision: 1, offset: 0, length: 100 }, binding), /worker_revocation_pending/);
    await worker.channel.revoke(binding);
    const revoked = await request("artifact.read", { artifact_handle: grant.artifact_handle, artifact_revision: 1, offset: 0, length: 100 });
    assert.equal(revoked.reply.outcome, "rejected_before_admission");
    assert.equal(revoked.current, true);
  } finally { await worker.close(); }
});

test("real worker request_count=1 admits its first data/control in either order and keeps controls after lifetime exhaustion", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 30_000,
}, async () => {
  for (const first of ["data", "control"]) {
    const root = await mkdtemp(path.join(tmpdir(), "renulus-worker-one-request-"));
    const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON,
      sourceRoot: repository, launchRoot: root, identity, current: initialRevisions, retention: "temporary",
      capacity: { request_count: 1, control_slots: 1 } });
    try {
      const issue = kind => kind === "data" ? worker.channel.submit("artifact.read", {
        artifact_handle: "synthetic-absent", artifact_revision: 1, offset: 0, length: 1 }, binding) :
        worker.channel.submit("worker.settle", { action: "query" }, binding);
      const one = issue(first);
      await one.terminal; // Retain this entry while admitting the other lane.
      const two = issue(first === "data" ? "control" : "data");
      const data = first === "data" ? await one.terminal : await two.terminal;
      await two.terminal;
      assert.equal(data.reply.outcome, "rejected_before_admission");
      assert.notEqual(data.reply.result.code, "overloaded");
      worker.channel.release(one.requestId); worker.channel.release(two.requestId);
      assert.throws(() => issue("data"), /worker_overloaded/);
      for (let index = 0; index < 3; index++) {
        const query = issue("control");
        assert.equal((await query.terminal).reply.outcome, "committed_reference");
        worker.channel.release(query.requestId);
      }
    } finally { await worker.close(); }
  }
});

test("real Mem0 reverse dispatch completes, then cancel/revoke retains the lease until actual host closure", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON || !process.env.RENULUS_WORKER_TEST_HELPERS, timeout: 180_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-worker-generation-"));
  const revisions = initialRevisions(), host = deferred(), started = deferred(), cancelled = deferred();
  let calls = 0;
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON, sourceRoot: repository,
    launchRoot: path.join(root, "launch"), identity, current: () => revisions, retention: "temporary",
    helpers: { helpers_root: process.env.RENULUS_WORKER_TEST_HELPERS, cache_root: path.join(root, "cache"), source_root: repository },
    derived: { root: path.join(root, "derived"), namespace: "synthetic-memory", library_tombstones: [], memory_tombstones: [] },
    generate: async (request, signal) => {
      calls++;
      assert.equal(request.capture_plan.evidence_receipt, "synthetic-receipt");
      assert.match(JSON.stringify(request.messages), /Synthetic educational learning/);
      if (calls === 1) return { status: "completed", output: '{"memory":[{"text":"Study AKI volume assessment."}]}' };
      signal.addEventListener("abort", () => cancelled.resolve(), { once: true });
      started.resolve(request);
      return host.promise;
    } });
  const request = async (command, input) => {
    const call = worker.channel.submit(command, input, binding);
    const result = await within(call.terminal, 120_000);
    worker.channel.release(call.requestId);
    return result;
  };
  async function capture(index) {
    const body = Buffer.from("Synthetic educational learning: AKI volume assessment and transplant biopsy.");
    const artifact_handle = "synthetic-source-" + index;
    const grant = { artifact_handle, artifact_revision: 1, artifact_sha256: createHash("sha256").update(body).digest("hex"),
      bytes: body.length, expires_at_ms: Date.now() + 120_000, rights: ["read"], permitted_ranges: [{ offset: 0, length: body.length }],
      reservation_id: "synthetic-reservation", intent_id: "synthetic-intent" };
    assert.equal((await request("artifact.upload", { artifact: grant, offset: 0, data_base64: body.toString("base64"), final: true })).reply.outcome,
      "committed_reference");
    const input = extractInput();
    input.artifact_handle = artifact_handle; input.length = body.length;
    input.output = outputGrant("synthetic-output-" + index);
    input.capture_plan.plan_id += "-" + index;
    input.capture_plan.source_sha256 = grant.artifact_sha256;
    return worker.channel.submit("memory.extract", input, binding);
  }
  try {
    const completed = await capture(1), done = await within(completed.terminal, 120_000);
    assert.equal(done.reply.outcome, "committed_reference");
    worker.channel.release(completed.requestId);
    const artifact = done.reply.result;
    const read = await request("artifact.read", { artifact_handle: artifact.artifact_handle, artifact_revision: artifact.artifact_revision,
      offset: 0, length: artifact.bytes });
    const extracted = JSON.parse(Buffer.from(read.reply.result.data_base64, "base64").toString());
    assert.deepEqual(extracted.facts, ["Study AKI volume assessment."]);
    assert.equal(extracted.eligible, false);
    const running = await capture(2), admission = await running.admission;
    const callback = await within(started.promise, 120_000);
    assert.deepEqual(callback.target, { identity: admission.reply.identity, request_sha256: admission.reply.request_sha256,
      worker_lease: admission.reply.settlement.worker_lease });
    assert.equal((await request("worker.settle", { action: "cancel", target: callback.target })).reply.settlement.state, "pending");
    await within(cancelled.promise);
    revisions.deletion++;
    await worker.channel.revoke(binding);
    const pending = await request("worker.settle", { action: "query", target: callback.target });
    assert.equal(pending.reply.settlement.state, "pending");
    assert.throws(() => worker.channel.release(running.requestId), /worker_settlement_pending/);
    // close must keep the reverse pipe alive while the host still owns generation.
    let closed = false;
    const closing = worker.close().then(() => { closed = true; });
    await new Promise(resolve => setTimeout(resolve, 50));
    assert.equal(closed, false);
    host.resolve({ status: "cancelled", output: null });
    const terminal = await within(running.terminal);
    assert.equal(terminal.reply.outcome, "cancelled_settled");
    assert.equal(terminal.reply.settlement.worker_lease, callback.target.worker_lease);
    assert.equal(terminal.current, false);
    await within(closing);
    assert.equal(calls, 2);
  } finally {
    host.resolve({ status: "cancelled", output: null });
    await worker.close();
  }
});

test("real owned process close times out at 30s, retains shutdown progress, then succeeds after late exit", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 60_000,
}, async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-worker-late-close-"));
  const sourceRoot = path.join(root, "source"), moduleRoot = path.join(sourceRoot, "runtime", "renulus"), workers = path.join(moduleRoot, "workers");
  await mkdir(workers, { recursive: true });
  // Scoped fixture changes only an engine's latency. The real worker protocol,
  // Windows lineage, admission, control/reply pumps and process drain still run.
  await writeFile(path.join(moduleRoot, "__init__.py"), `__path__.append(${JSON.stringify(path.join(repository, "runtime", "renulus"))})\n`);
  await writeFile(path.join(workers, "__init__.py"), `__path__.append(${JSON.stringify(path.join(repository, "runtime", "renulus", "workers"))})\n`);
  const marker = path.join(root, "observations.txt");
  await writeFile(path.join(workers, "main.py"), `import importlib.util, time
from pathlib import Path
from renulus.workers.engines import SelectedEngines
from renulus.workers.runtime import Worker
marker = Path(${JSON.stringify(marker)})
def slow_embed(self, texts, *, query):
    marker.write_text("started\\n")
    time.sleep(33)
    return {"tag":"embeddings","model_id":"synthetic","dimensions":1,"vectors":[[0]]}
SelectedEngines.embed = slow_embed
original = Worker._control
def observed_control(self, command):
    if command.input.action == "close":
        with marker.open("a") as stream:
            stream.write("close:" + str(command.limits.cpu_seconds) + "\\n")
    return original(self, command)
Worker._control = observed_control
spec = importlib.util.spec_from_file_location("renulus.workers.actual_main", ${JSON.stringify(path.join(repository, "runtime", "renulus", "workers", "main.py"))})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
raise SystemExit(module.main())
`);
  const worker = await openEngineWorker({ python: process.env.RENULUS_BACKEND_TEST_PYTHON, sourceRoot,
    launchRoot: path.join(root, "launch"), identity, current: initialRevisions, retention: "temporary" });
  try {
    const call = worker.channel.submit("embedding.embed", { texts: ["Synthetic late engine"], query: false, output: outputGrant() }, binding);
    const admission = await call.admission;
    assert.equal(admission.reply.outcome, "accepted_pending");
    await within((async () => { for (;;) {
      try { if ((await readFile(marker, "utf8")).startsWith("started")) return; } catch {}
      await new Promise(resolve => setTimeout(resolve, 10));
    } })());
    await assert.rejects(worker.close(), /worker_settlement_held/);
    assert.equal(worker.channel.state().unsettled, 1);
    assert.deepEqual(worker.channel.observe(call.requestId).reply, admission.reply);
    assert.throws(() => worker.channel.release(call.requestId), /worker_settlement_pending/);
    const terminal = await within(call.terminal);
    assert.equal(terminal.reply.outcome, "cancelled_settled");
    assert.equal(terminal.reply.settlement.worker_lease, admission.reply.settlement.worker_lease);
    await within(worker.close());
    assert.equal((await readFile(marker, "utf8")).replaceAll("\r\n", "\n"), "started\nclose:120\n");
  } finally { await worker.close(); }
});
