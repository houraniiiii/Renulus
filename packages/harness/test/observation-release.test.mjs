import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import readline from "node:readline";

const fixture = fileURLToPath(new URL("./fixtures/observation-release-host.mjs", import.meta.url));
const identity = { protocol: "renulus-harness/1", profile_id: "synthetic-profile",
  store_id: "synthetic-runtime", generation: "synthetic-generation", token: "synthetic-private-token" };

async function client(settings = {}) {
  const root = await mkdtemp("G:/Renulus-agent-scratch/oc-h02-h08/observation-release/node-");
  const gate = path.join(root, "writer-released");
  const boot = { ...identity, root, domain_store_id: "synthetic-domain", domain_path: "state/renulus.sqlite",
    ipc: { max_result_records: 1, max_frame_bytes: 4096, max_result_bytes: 65536 },
    fixture_gate_file: gate, ...settings };
  const child = spawn(process.execPath, [fixture], { cwd: root, windowsHide: true,
    env: { ...Object.fromEntries(["SYSTEMROOT", "WINDIR"].filter(key => process.env[key])
      .map(key => [key, process.env[key]])), PATH: path.dirname(process.execPath),
      RENULUS_HARNESS_BOOT: JSON.stringify(boot) }, stdio: ["pipe", "pipe", "pipe"] });
  let sequence = 0;
  let stderr = "";
  child.stderr.on("data", bytes => { stderr += bytes; });
  const queued = new Map();
  const pending = new Map();
  const exited = new Promise(resolve => child.once("exit", (code, signal) => resolve({ code, signal })));
  readline.createInterface({ input: child.stdout }).on("line", line => {
    const frame = JSON.parse(line);
    const key = frame.kind === "ready" ? "ready" : frame.request_id;
    const waiting = pending.get(key);
    if (waiting) { pending.delete(key); waiting(frame); }
    else { const frames = queued.get(key) ?? []; frames.push(frame); queued.set(key, frames); }
  });
  const receive = key => {
    const frames = queued.get(key);
    if (frames?.length) return Promise.resolve(frames.shift());
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(key); reject(new Error("reply_timeout: " + key + " " + stderr)); }, 1000);
      pending.set(key, frame => { clearTimeout(timer); resolve(frame); });
    });
  };
  const send = frame => child.stdin.write(JSON.stringify(frame) + "\n");
  const request = (command, payload = {}, operation = "observe") => ({ ...identity, kind: "request",
    request_id: "request-" + ++sequence, operation_id: operation, attempt_id: "1", command, payload });
  const command = async (name, payload = {}, operation) => {
    const frame = request(name, payload, operation); send(frame); return receive(frame.request_id);
  };
  const release = (request_id, overrides = {}) => send({ ...identity, kind: "observation_release", request_id, ...overrides });
  await receive("ready");
  return { gate, send, receive, request, command, release, async close() {
    await writeFile(gate, "release");
    assert.equal((await command("host.close"))["outcome"], "cancelled_settled");
    assert.deepEqual(await exited, { code: 0, signal: null });
  } };
}

test("a held replay publication retains its observation while control remains responsive", async () => {
  const pipe = await client({ fixture_hold_operation: "held-replay", fixture_hold_write: 2 });
  try {
    const frame = pipe.request("session.get", { session_id: "native-session" }, "held-replay");
    pipe.send(frame);
    const original = await pipe.receive(frame.request_id);
    pipe.send(frame);
    assert.deepEqual(await pipe.receive(frame.request_id), original);
    pipe.release(frame.request_id);
    const status = await pipe.command("host.status");
    assert.equal(status.outcome, "committed_reference");
    assert.equal(status.result.reads, 1);
    assert.equal((await pipe.command("session.get", { session_id: "native-session" })).error.code, "result_capacity");
    pipe.release(status.request_id);
    await writeFile(pipe.gate, "release");
    let next;
    for (let index = 0; index < 100; index += 1) {
      next = await pipe.command("session.get", { session_id: "native-session" });
      if (next.outcome === "committed_reference") break;
    }
    assert.equal(next.outcome, "committed_reference");
    assert.equal(next.result.session.reads, 2);
  } finally { await pipe.close(); }
});

test("release requires the exact authenticated generation and strict control shape", async () => {
  const pipe = await client();
  try {
    const first = await pipe.command("session.get", { session_id: "native-session" });
    const variants = [
      ...Object.keys(identity).map(key => ({ [key]: "foreign" })),
      { command: "session.get" }, { payload: {} }, { operation_id: "foreign" },
      { request_id: null }, { request_id: "unknown" },
    ];
    for (const variant of variants) {
      pipe.release(first.request_id, variant);
      assert.equal((await pipe.command("session.get", { session_id: "native-session" })).error.code, "result_capacity");
    }
    pipe.release(first.request_id);
    pipe.release(first.request_id);
    const next = await pipe.command("session.get", { session_id: "native-session" });
    assert.equal(next.outcome, "committed_reference");
    assert.equal(next.result.session.reads, 2);
    assert.equal((await pipe.command("host.status")).result.dispatches, 0);
  } finally { await pipe.close(); }
});

test("writes, uncertain reads and a read released before its terminal reply retain replay", async () => {
  const pipe = await client({ ipc: { max_result_records: 3, max_frame_bytes: 4096, max_result_bytes: 65536 } });
  try {
    const write = pipe.request("session.create", { title: "Synthetic" });
    pipe.send(write);
    const written = await pipe.receive(write.request_id);
    pipe.release(write.request_id);
    pipe.send(write);
    assert.deepEqual(await pipe.receive(write.request_id), written);
    const uncertain = pipe.request("session.get", { session_id: "uncertain" });
    pipe.send(uncertain);
    const unknown = await pipe.receive(uncertain.request_id);
    assert.equal(unknown.outcome, "uncertain_after_disconnect");
    pipe.release(uncertain.request_id);
    pipe.send(uncertain);
    assert.deepEqual(await pipe.receive(uncertain.request_id), unknown);
    const pending = pipe.request("session.get", { session_id: "held-read" });
    pipe.send(pending);
    pipe.release(pending.request_id);
    const status = await pipe.command("host.status");
    assert.equal(status.result.readHeld, true);
    pipe.release(status.request_id);
    assert.equal((await pipe.command("session.cancel", { session_id: "held-read" })).outcome, "cancelled_settled");
    const completed = await pipe.receive(pending.request_id);
    pipe.send(pending);
    assert.deepEqual(await pipe.receive(pending.request_id), completed);
    assert.equal((await pipe.command("session.get", { session_id: "native-session" })).error.code, "result_capacity");
    const final = await pipe.command("host.status");
    assert.equal(final.result.reads, 2);
    assert.equal(final.result.creates, 1);
  } finally { await pipe.close(); }
});

test("release of a terminal reply is deferred until its first stdout publication settles", async () => {
  const pipe = await client({ fixture_hold_operation: "held-reply" });
  try {
    const held = await pipe.command("session.get", { session_id: "native-session" }, "held-reply");
    pipe.release(held.request_id);
    assert.equal((await pipe.command("session.get", { session_id: "native-session" })).error.code, "result_capacity");
    const status = await pipe.command("host.status");
    assert.equal(status.result.reads, 1);
    pipe.release(status.request_id);
    await writeFile(pipe.gate, "release");
    let next;
    for (let index = 0; index < 100; index += 1) {
      next = await pipe.command("session.get", { session_id: "native-session" });
      if (next.outcome === "committed_reference") break;
    }
    assert.equal(next.outcome, "committed_reference");
    assert.equal(next.result.session.reads, 2);
  } finally { await pipe.close(); }
});

test("an oversized read reply normalized to uncertainty cannot be released", async () => {
  const pipe = await client();
  try {
    const frame = pipe.request("session.get", { session_id: "oversized" });
    pipe.send(frame);
    const uncertain = await pipe.receive(frame.request_id);
    assert.equal(uncertain.outcome, "uncertain_after_disconnect");
    assert.equal(uncertain.error.code, "reply_too_large");
    pipe.release(frame.request_id);
    pipe.send(frame);
    assert.deepEqual(await pipe.receive(frame.request_id), uncertain);
    assert.equal((await pipe.command("session.get", { session_id: "native-session" })).error.code, "result_capacity");
    assert.equal((await pipe.command("host.status")).result.reads, 1);
  } finally { await pipe.close(); }
});
