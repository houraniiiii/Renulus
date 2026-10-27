// SPDX-License-Identifier: MIT
// BF03 developer plugin: synthetic files/shell/worktree/browser proofs. Hidden processes, local sockets, no owner browser.
import "../../harness/test/owned-environment.mjs";
import assert from "node:assert/strict";
import { after, test } from "node:test";
import net from "node:net";
import { DatabaseSync } from "node:sqlite";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync, existsSync, symlinkSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { executeDispatch } from "../src/storage/dispatch.ts";
import { executeCapabilityCommand, CAPABILITY_SCHEMA } from "../src/domain/capabilities/commands.ts";
import { defaultConfiguration, ALLOWED_MODELS } from "../src/dispatch/policy.ts";
import { digest } from "../src/storage/schema.ts";
import { createCapabilityAuthority } from "../src/domain/capabilities/authority.ts";
import { createBrowserTransport } from "../src/domain/capabilities/transport.ts";
import { createDeveloperRuntime } from "../../harness/src/developer-plugin.ts";
import { createNativePorts } from "../src/plugins/native.ts";
import { createToolRegistry } from "../src/plugins/registry.ts";
import { createQuestions } from "../src/plugins/questions.ts";
import { BrowserProxy } from "@opencode/plugin-browser/proxy";

const python = process.env.RENULUS_BACKEND_TEST_PYTHON ?? "C:/Renulus/dev/python/Scripts/python.exe";
const repository = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const resources = { python, sourceRoot: repository };
const root = realpathSync(mkdtempSync(join(tmpdir(), "renulus-bf03-developer-")));
const fence = { profile_id: "synthetic_profile", domain_store_id: "domain_a", runtime_store_id: "native_a", authority_epoch: 1,
  process_generation: "process_a", context_epoch: 0, deletion_epoch: 0, cancellation_epoch: 0 };
const ACTIONS = ["developer.files.read", "developer.files.write", "developer.shell", "developer.worktree", "developer.browser"];
let sequence = 0;
const databases = [];
after(() => { for (const db of databases) db.close(); rmSync(root, { recursive: true, force: true }); });

/** Real canonical dispatch + capability transactions in one synthetic SQLite database. */
function fixture(capabilities = ACTIONS) {
  const db = new DatabaseSync(join(root, `db-${++sequence}.sqlite3`), { enableForeignKeyConstraints: true }); databases.push(db);
  for (const name of ["002-harness-configuration.sql", "004-harness-dispatch-purpose.sql", "005-harness-children.sql"])
    db.exec(readFileSync(join(repository, "runtime/renulus/runtime/migrations", name), "utf8"));
  db.exec("CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT,updated_at TEXT); CREATE TABLE assessment_test_attempts(id TEXT,mode TEXT,status TEXT);");
  db.exec(CAPABILITY_SCHEMA);
  const run = c => { db.exec("BEGIN IMMEDIATE"); try {
    const result = c.type.startsWith("capability.") ? executeCapabilityCommand(db, c) : executeDispatch(db, c); db.exec("COMMIT"); return result;
  } catch (error) { db.exec("ROLLBACK"); throw error; } };
  const spec = { ...defaultConfiguration({ provider: "codex", credential_reference: "protected_reference_only", credential_revision: 1,
    selected_model: ALLOWED_MODELS.codex[0] }, digest("synthetic-registry")) };
  spec.capabilities = ["text", ...capabilities];
  const { version } = run({ type: "dispatch.stage", spec, expectedEffective: null, expectedRequested: null, grantEpoch: 0 });
  const inspection = { configuration_version: version, grant_epoch: 0, registry_hash: spec.registry_hash, loaded_inputs: spec.inputs, healthy: true,
    generation_open: false, recovery_open: false, package_acquisition_open: false, mcp_startup_open: false, live_store_writer: false };
  run({ type: "dispatch.inspect", inspection });
  run({ type: "dispatch.close", version, expectedEffective: null, grantEpoch: 0 });
  run({ type: "dispatch.activate", version, expectedEffective: null, settlement: { configuration_version: version, grant_epoch: 0, admission_closed: true, runtime_stopped: true, domain_settled: true } });
  run({ type: "dispatch.open", inspection });
  const begin = (runId, extra = {}) => run({ type: "dispatch.begin", runId, purpose: "explain", expectedVersion: version, capabilities: ["text", ...capabilities],
    availableModels: [...ALLOWED_MODELS.codex], operationModel: null, fence, batchSize: null, ...extra });
  const parent = begin("run_a");
  const envelope = (patch = {}) => ({ run_id: "run_a", root_id: parent.root_id, session_id: "session_a", call_id: "call_" + (++sequence), configuration: version,
    grant_epoch: 0, fence, retention: "saved", mode: "developer", depth: 0, ...patch });
  const lease = id => db.prepare("SELECT state,used_bytes,effect_reference FROM capability_effects WHERE id=?").get(id);
  const leases = () => db.prepare("SELECT id,action,state,used_bytes,effect_reference FROM capability_effects ORDER BY rowid").all();
  return { run, envelope, lease, leases, parent, version, storage: { execute: async command => run(command) } };
}

function workspaceFor(name) {
  const workspace = join(root, name); mkdirSync(workspace, { recursive: true });
  return { workspace, configuration: { enabled: true, workspace, actions: ACTIONS, roots: [{ path: workspace, read: true, write: true, execute: true }],
    executables: { python }, git: "C:/Program Files/Git/cmd/git.exe", endpoints: [] } };
}
const direct = (developer, f, transport) => {
  const authority = createCapabilityAuthority({ storage: f.storage, current: async (_e, action) => developer.grant(action),
    transport: transport ?? { http() { throw new Error("unused"); }, tunnelOpen() { throw new Error("unused"); }, tunnelRead() { throw new Error("unused"); },
      tunnelWrite() { throw new Error("unused"); }, tunnelClose() { throw new Error("unused"); } } });
  return { authority, ports: developer.ports(authority, async (_session, call) => f.envelope({ call_id: call })) };
};
const rejects = (promise, code) => assert.rejects(promise, error => { assert.match(String(error.code ?? error.message), code); return true; });

test("default configuration registers no developer capability and nothing can admit one", async () => {
  assert.equal(createDeveloperRuntime({ resources }), undefined);
  assert.equal(createDeveloperRuntime({ resources, configuration: { ...workspaceFor("off").configuration, enabled: false } }), undefined);
  const f = fixture(), registry = createToolRegistry();
  const ports = createNativePorts({ storage: { command: async command => f.run(command) }, root, registry, questions: createQuestions(),
    binding: () => { throw new Error("unused"); }, open: () => true });
  assert.equal(ports.developer, undefined);
  for (const action of ["developer.shell", "developer.files.read", "developer.browser"])
    await rejects(ports.authority.invoke(f.envelope(), action, {}, async () => "never"), /developer_disabled/);
  assert.deepEqual(f.leases(), []);
});

test("doctor, child and temporary envelopes can never be admitted even when a developer profile is enabled", async () => {
  const f = fixture(), { configuration } = workspaceFor("modes"), developer = createDeveloperRuntime({ resources, configuration });
  const { authority } = direct(developer, f);
  const child = f.run({ type: "dispatch.child", runId: "child_a", parentId: "run_a", purpose: "explain", capabilities: ["text", ...ACTIONS], operationModel: null, fence });
  for (const patch of [{ mode: "doctor" }, { retention: "temporary" }, { depth: 1, run_id: child.run_id }])
    await rejects(authority.invoke(f.envelope(patch), "developer.shell", {}, async () => "never"), /developer_profile_required|capability_parent_conflict|capability_invalid/);
  assert.deepEqual(f.leases(), []);
  // Disabled actions are separately selectable: an enabled developer profile still has no write grant here.
  const readOnly = createDeveloperRuntime({ resources, configuration: { ...configuration, actions: ["developer.files.read"] } });
  assert.throws(() => readOnly.grant("developer.files.write"), /developer_action_not_enabled/);
});

test("file families: roots, aliases, read-before-write revisions and receipts under a settled capability receipt", async () => {
  const f = fixture(), { workspace, configuration } = workspaceFor("files"), developer = createDeveloperRuntime({ resources, configuration });
  const { authority, ports: files } = direct(developer, f);
  const file = join(workspace, "note.txt"), outside = join(root, "outside.txt"); writeFileSync(outside, "SYNTHETIC outside");
  const guarded = (action, tool, input, work = async () => {}) => authority.invoke(f.envelope(), action, input, async (lease, signal) => {
    const guard = await files.files(lease, tool, input, signal); try { await work(); } finally { await guard.close(); } });
  await guarded("developer.files.write", "write", { path: "note.txt", content: "one" }, async () => writeFileSync(file, "one"));
  // An existing file needs the revision this session last read or wrote.
  writeFileSync(file, "changed outside the session");
  await rejects(guarded("developer.files.write", "edit", { path: "note.txt", oldString: "x", newString: "y" }), /developer_revision_required/);
  await guarded("developer.files.read", "read", { path: "note.txt" });
  await guarded("developer.files.write", "edit", { path: "note.txt", oldString: "changed", newString: "edited" }, async () => writeFileSync(file, "edited outside the session"));
  const receipts = developer.receipts();
  assert.equal(receipts.length, 2);
  assert.equal(receipts[1].before_sha256 !== receipts[1].after_sha256, true);
  assert.equal(receipts[0].before_sha256, null);
  await rejects(guarded("developer.files.read", "read", { path: outside }), /developer_root_denied/);
  await rejects(guarded("developer.files.read", "read", { path: "../outside.txt" }), /developer_root_denied/);
  await rejects(guarded("developer.files.write", "patch", { patchText: `*** Begin Patch\n*** Add File: ${outside}\n+x\n*** End Patch` }), /developer_root_denied/);
  try { symlinkSync(root, join(workspace, "alias"), "junction"); await rejects(guarded("developer.files.read", "read", { path: "alias/outside.txt" }), /developer_path_alias/); } catch (error) { if (error.code !== "EPERM") throw error; }
  assert.equal(readFileSync(outside, "utf8"), "SYNTHETIC outside");
  const settled = f.leases().filter(lease => lease.state === "settled");
  assert.equal(settled.length, 3); // each successful call has a settled capability receipt; refused guards are recorded uncertain
});

test("trusted shell: reviewed executable, minimal environment, owned descendants, accurate uncertain effects", async () => {
  const f = fixture(), { workspace, configuration } = workspaceFor("shell"), developer = createDeveloperRuntime({ resources, configuration });
  const { authority, ports } = direct(developer, f), shell = (input, envelope = f.envelope()) =>
    authority.invoke(envelope, "developer.shell", input, (lease, signal) => ports.shell(input, lease, signal));
  const script = join(root, "shell-script.py"), pidFile = join(root, "descendant.pid"), outside = join(root, "shell-outside.txt");
  const server = net.createServer(socket => socket.end()).listen(0, "127.0.0.1"); await new Promise(r => server.once("listening", r));
  writeFileSync(script, ["import os,socket,subprocess,sys","open(sys.argv[1],'w').write('SYNTHETIC trusted effect')",
    `socket.create_connection(('127.0.0.1',${server.address().port}),timeout=2).close()`,
    "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])","open(sys.argv[2],'w').write(str(child.pid))",
    "print('env='+','.join(sorted(k for k in os.environ if k in ('SystemRoot','PATH','TEMP'))))"].join("\n"));
  const result = await shell({ command: `python "${script}" "${outside}" "${pidFile}"`, workdir: "." });
  server.close();
  assert.equal(result.output.exit, 0);
  assert.match(result.output.output, /env=/);
  assert.equal(result.metadata.effects, "uncertain"); assert.equal(result.metadata.confined, false); assert.equal(result.metadata.descendants_settled, true);
  assert.equal(readFileSync(outside, "utf8"), "SYNTHETIC trusted effect"); // out-of-root effect happened and is recorded as unconfined
  const descendant = Number(readFileSync(pidFile, "utf8"));
  assert.throws(() => process.kill(descendant, 0), error => error.code === "ESRCH"); // Job Object killed the surviving child before lease release
  await rejects(shell({ command: "powershell -c exit" }), /developer_executable_unreviewed/);
  await rejects(shell({ command: "python -c pass & whoami" }), /developer_command_invalid/);
  await rejects(shell({ command: "python -c pass", workdir: "../" }), /developer_root_denied/);
  await rejects(shell({ command: "python -c pass", background: true }), /developer_shell_background_unsupported/);
  await rejects(authority.invoke(f.envelope({ mode: "doctor" }), "developer.shell", {}, async () => "never"), /developer_profile_required/);
  // Revocation of a running command: the owned family is dead before the lease settles, and the effect stays uncertain.
  const running = shell({ command: `python -c "import time;time.sleep(60)"`, timeout: 60000 }).catch(error => error);
  await new Promise(r => setTimeout(r, 1500));
  const t0 = Date.now(); await authority.stop(f.parent.root_id); await running;
  assert.ok(Date.now() - t0 < 10000);
  assert.equal(f.leases().at(-1).state, "uncertain");
  assert.equal(f.leases().filter(l => l.state === "admitted").length, 0);
  assert.equal(workspace.length > 0, true);
});

test("worktrees: owned identity is recorded, destructive removal needs exact identity and direct approval", async () => {
  const f = fixture(), { workspace, configuration } = workspaceFor("repo");
  const git = (...args) => execFileSync(configuration.git, args, { cwd: workspace, windowsHide: true, encoding: "utf8" });
  git("init", "-q"); git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--allow-empty", "-q", "-m", "synthetic");
  let approvals = 0;
  const developer = createDeveloperRuntime({ resources, configuration, approveWorktreeRemoval: async item => { approvals++; return item.force === false; } });
  const { authority, ports } = direct(developer, f), tree = (tool, input, work = async () => {}) => authority.invoke(f.envelope(), "developer.worktree", input, async (lease, signal) => {
    const guard = await ports.worktree(tool, input, lease, signal); try { await work(); } finally { await guard.close(); } });
  const owned = join(root, "worktree-owned"), foreign = join(root, "worktree-foreign");
  await rejects(tree("opencode.worktree_create", { name: "../bad" }), /developer_worktree_name_invalid/);
  await tree("opencode.worktree_create", { name: "owned" }, async () => git("worktree", "add", "-q", "-b", "owned", owned));
  assert.equal(developer.worktrees().length, 1);
  git("worktree", "add", "-q", "-b", "foreign", foreign); // not created through the plugin
  await rejects(tree("opencode.worktree_remove", { directory: foreign }), /developer_worktree_unowned/);
  await rejects(tree("opencode.worktree_remove", { directory: "owned" }), /developer_worktree_identity_required/);
  await rejects(tree("opencode.worktree_remove", { directory: owned, force: true }), /developer_worktree_removal_not_approved/);
  assert.ok(existsSync(owned));
  await tree("opencode.worktree_remove", { directory: owned }, async () => git("worktree", "remove", owned));
  assert.equal(developer.worktrees().length, 0); assert.equal(approvals, 2); assert.ok(existsSync(foreign));
  await rejects(tree("opencode.session_move", { directory: root }), /developer_root_denied/);
});

/** Local servers A (granted) and B (never granted) for the browser tunnel boundary. */
async function endpoints() {
  const seen = { a: 0, b: 0 }, sockets = [];
  const start = name => new Promise(resolveStart => { const server = net.createServer(socket => { seen[name]++; sockets.push(socket);
    socket.on("data", data => socket.write(Buffer.concat([Buffer.from("ECHO:"), data]))); socket.on("error", () => {}); }).listen(0, "127.0.0.1", () => resolveStart(server)); });
  const a = await start("a"), b = await start("b");
  return { seen, sockets, a: a.address().port, b: b.address().port, close: () => { for (const s of sockets) s.destroy(); a.close(); b.close(); } };
}
/** Synthetic owned developer browser: proof flags and counters only; Chromium itself is not launched. */
function attachment(events = []) {
  return { connection_id: "connection_a", client_generation: "generation_" + (++sequence),
    context: { identity: "synthetic_context", proxy_only: true, quic_disabled: true, webrtc_disabled: true, async close() { events.push("context.close"); } },
    async removeNativeAllow() { events.push("allow.removed"); }, async cancelPending() { events.push("pending.cancelled"); } };
}
const helperPids = () => execFileSync(process.env.SystemRoot + "\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", ["-NoProfile", "-Command",
  "(Get-CimInstance Win32_Process -Filter \"CommandLine like '%capability_transport_host%'\" | Select-Object -ExpandProperty ProcessId) -join ','"], { encoding: "utf8", windowsHide: true })
  .trim().split(",").filter(Boolean).map(Number);
/** The native proxy is the only network path of the owned client: each connection is one CONNECT through it. */
function connect(proxy, port) {
  return new Promise(resolveConnect => {
    const socket = net.connect(proxy.port, proxy.host), chunks = [];
    const auth = Buffer.from(`${proxy.credentials.username}:${proxy.credentials.password}`).toString("base64");
    socket.write(`CONNECT 127.0.0.1:${port} HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\nProxy-Authorization: Basic ${auth}\r\n\r\n`);
    socket.on("data", data => chunks.push(data)); socket.on("error", () => {});
    const finish = () => resolveConnect({ socket, text: () => Buffer.concat(chunks).toString(), closed: new Promise(r => socket.once("close", r)) });
    socket.once("data", () => setTimeout(finish, 50)); socket.once("close", finish);
  });
}

async function browserHarness({ ttl = 299_000, bytes = 100 * 1024 * 1024 } = {}, events = []) {
  const f = fixture(), servers = await endpoints();
  const transport = createBrowserTransport({ ...resources, current: async lease => { try { f.run({ type: "capability.current", id: lease.id, envelope: lease.envelope, bytes: 0, now_ms: Date.now() }); return true; } catch { return false; } } });
  const authority = createCapabilityAuthority({ storage: f.storage, transport: { ...transport },
    current: async (_e, action) => ({ actions: [action], roots: [], skills: [], max_bytes: bytes, expires_at_ms: Date.now() + ttl,
      endpoints: [{ host: "127.0.0.1", port: servers.a, private_network: true }] }) });
  const envelope = f.envelope(), owned = await authority.browser(envelope, attachment(events));
  const proxy = await BrowserProxy.make({ open: (target, signal) => owned.open(target, signal), read: (id, signal) => owned.read(id, signal),
    write: (id, data, end, signal) => owned.write(id, data, end, signal), close: id => owned.closeSocket(id) });
  const url = new URL(proxy.url);
  return { f, servers, owned, authority, proxy: { host: url.hostname, port: Number(url.port), credentials: proxy.credentials, close: () => proxy.close() }, envelope };
}

test("browser tunnel: granted endpoint A works; navigation, subresource, redirect and delayed script to ungranted B never connect", async () => {
  const events = [], h = await browserHarness({}, events);
  try {
    const a = await connect(h.proxy, h.servers.a);
    assert.match(a.text(), /^HTTP\/1\.1 200/);
    a.socket.write("SYNTHETIC page bytes"); await new Promise(r => setTimeout(r, 300));
    assert.match(a.text(), /ECHO:SYNTHETIC page bytes/);
    // From the browser each of these is a new CONNECT to B: first navigation, subresource, redirect target and a script that fires later.
    for (const _kind of ["navigation", "subresource", "redirect", "delayed-script"]) {
      if (_kind === "delayed-script") await new Promise(r => setTimeout(r, 200));
      const b = await connect(h.proxy, h.servers.b);
      assert.doesNotMatch(b.text(), /^HTTP\/1\.1 200/); b.socket.destroy();
    }
    assert.equal(h.servers.seen.b, 0);
    assert.equal(h.servers.seen.a, 1);
    a.socket.destroy();
  } finally { await h.proxy.close(); await h.owned.revoke(); h.servers.close(); }
});

test("revocation closes a live WebSocket-style tunnel and pending read; late bytes and stale reattach get no authority", async () => {
  const events = [], h = await browserHarness({}, events), pidsBefore = helperPids();
  const a = await connect(h.proxy, h.servers.a);
  a.socket.write("hello"); await new Promise(r => setTimeout(r, 300));
  const usedBefore = h.f.lease(h.owned.lease.id).used_bytes; assert.ok(usedBefore > 0);
  const pending = h.owned.read((await h.owned.open({ host: "127.0.0.1", port: h.servers.a }, new AbortController().signal)), new AbortController().signal).catch(error => error);
  await new Promise(r => setTimeout(r, 100));
  const connectionsBefore = h.servers.seen.a;
  await h.owned.revoke();
  assert.ok((await pending) instanceof Error);
  for (const socket of h.servers.sockets) socket.write("LATE_WEBSOCKET_FRAME"); // already-on-the-wire peer bytes
  await a.closed; assert.doesNotMatch(a.text(), /LATE_WEBSOCKET_FRAME/);
  const row = h.f.lease(h.owned.lease.id);
  assert.equal(row.state, "uncertain");
  assert.deepEqual(events.filter(e => e === "allow.removed"), ["allow.removed"]); assert.ok(events.includes("context.close"));
  await rejects(h.owned.open({ host: "127.0.0.1", port: h.servers.a }, new AbortController().signal), /capability_stale|browser_socket|capability_closed/);
  const late = await connect(h.proxy, h.servers.a); assert.doesNotMatch(late.text(), /^HTTP\/1\.1 200/); late.socket.destroy();
  assert.equal(h.servers.seen.a, connectionsBefore); // no new A or B connection after revoke
  // Stale reattach: the closed root refuses a fresh attachment and a saved native allow is not restored.
  await rejects(h.authority.browser(h.envelope, attachment(events)), /capability_stale/);
  assert.equal(events.filter(e => e === "allow.removed").length, 1);
  await new Promise(r => setTimeout(r, 500));
  assert.equal(h.f.lease(h.owned.lease.id).used_bytes, row.used_bytes); // no byte credit after revoke
  for (let attempt = 0; attempt < 30 && helperPids().some(pid => !pidsBefore.includes(pid)); attempt++) await new Promise(r => setTimeout(r, 200));
  assert.deepEqual(helperPids().filter(pid => !pidsBefore.includes(pid)), []); // owned transport client process is gone
  await h.proxy.close(); h.servers.close();
});

test("lease expiry and the byte limit close owned sockets; cleanup debt retains the lease until closure is acknowledged", async () => {
  const expiring = await browserHarness({ ttl: 1500 });
  const a = await connect(expiring.proxy, expiring.servers.a); assert.match(a.text(), /^HTTP\/1\.1 200/);
  await a.closed; // expiry destroys the tunnel without any command
  await new Promise(r => setTimeout(r, 300));
  assert.equal(expiring.f.lease(expiring.owned.lease.id).state, "uncertain");
  await expiring.proxy.close(); expiring.servers.close();

  const limited = await browserHarness({ bytes: 64 }), id = await limited.owned.open({ host: "127.0.0.1", port: limited.servers.a }, new AbortController().signal);
  await limited.owned.write(id, new Uint8Array(40), false, new AbortController().signal);
  await rejects(limited.owned.write(id, new Uint8Array(40), false, new AbortController().signal), /capability_limit/);
  assert.ok(limited.f.lease(limited.owned.lease.id).used_bytes <= 64);
  await limited.proxy.close(); await limited.owned.revoke(); limited.servers.close();

  // Client death: the owned context cannot confirm closure, so the lease is retained (closed, never settled) until retry succeeds.
  const events = []; let fail = true;
  const f = fixture(), servers = await endpoints();
  const authority = createCapabilityAuthority({ storage: f.storage, transport: { http() { throw new Error("unused"); }, tunnelOpen: async () => "socket_x", tunnelRead: async () => ({ data: new Uint8Array(), eof: true }), tunnelWrite: async () => {}, tunnelClose: async () => {} },
    current: async (_e, action) => ({ actions: [action], roots: [], skills: [], max_bytes: 1024, expires_at_ms: Date.now() + 60_000, endpoints: [] }) });
  const dying = attachment(events); dying.context.close = async () => { if (fail) throw new Error("client_death_unacknowledged"); events.push("context.closed"); };
  const owned = await authority.browser(f.envelope(), dying);
  await rejects(owned.revoke(), /capability_cleanup_held/);
  assert.equal(f.lease(owned.lease.id).state, "closed");
  fail = false; await owned.revoke(); assert.equal(f.lease(owned.lease.id).state, "uncertain"); assert.ok(events.includes("context.closed"));
  servers.close();
});

test("transport helper death is reported as a closed tunnel and never silently reconnects", async () => {
  const h = await browserHarness();
  const a = await connect(h.proxy, h.servers.a); assert.match(a.text(), /^HTTP\/1\.1 200/);
  for (const pid of helperPids()) try { process.kill(pid); } catch { /* another run's helper already ended */ }
  await a.closed;
  const next = await connect(h.proxy, h.servers.a); assert.doesNotMatch(next.text(), /^HTTP\/1\.1 200/); next.socket.destroy();
  await h.proxy.close(); await h.owned.revoke().catch(() => {});
  assert.equal(h.f.lease(h.owned.lease.id).state === "uncertain" || h.f.lease(h.owned.lease.id).state === "closed", true);
  h.servers.close();
});

test("a missing browser attachment is reported explicitly and no owner browser is substituted", async () => {
  const f = fixture(), { configuration } = workspaceFor("nobrowser"), developer = createDeveloperRuntime({ resources, configuration });
  const { ports } = direct(developer, f);
  await rejects(ports.browser({ sessionID: "session_a", connectionID: "connection_a" }), /browser_attachment_unavailable/);
});
