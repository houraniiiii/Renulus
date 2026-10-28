// SPDX-License-Identifier: MIT
// BF07/P07/P08: the paired recovery journey on isolated SYNTHETIC stores (real canonical SQLite through the TS
// storage worker, real OpenCode native stores, real generation files, zero inference).
import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { spawnSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, writeFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { tmpdir } from "node:os";
import path, { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Effect, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient } from "@opencode/ai";
import { OpenCode, AbsolutePath } from "@opencode/sdk/effect";
import { Session } from "@opencode/schema/session";
import { SessionMessage } from "@opencode/schema/session-message";
import { Config } from "@opencode/core/config";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { Global } from "@opencode/util/global";
import { createGraphRecovery, mergeRecoveryGraphs } from "../src/graph-recovery.ts";
import { createRecoveryOwner, publishRecoveryOriginals } from "../src/recovery-owner.ts";
import { openIsolatedStorage, loadMigrationInventory, MARKER, SELECTOR } from "../../backend/src/storage/index.ts";
import { createRecoveryCoordinator, sealGeneration } from "../../backend/src/storage/generation.ts";
import { recoveryFrontierDigest, verifyNativeClosure } from "../../backend/src/storage/recovery.ts";
import { createRecoveryPort } from "../../backend/src/host/recovery-select.ts";
import { BACKEND_SELECTOR, GENERATION_MANIFEST, resolveBackendSelection } from "../../backend/src/host/handoff.ts";
import { openEngineWorker } from "../../backend/src/workers/process.ts";
import { createWorkerKnowledgeIO } from "../../backend/src/workers/knowledge.ts";
import { canonical } from "../../backend/src/storage/schema.ts";
import { reconcileRecoveryReservations } from "../../backend/src/storage/reservations.ts";

const repository = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const python = process.env.RENULUS_STORAGE_TEST_PYTHON || "C:/Renulus/dev/python/Scripts/python.exe";
const root = realpathSync(mkdtempSync(join(tmpdir(), "renulus-bf07-journey-")));
const migrations = loadMigrationInventory(repository);
const sha = value => createHash("sha256").update(value).digest("hex");
const hex = char => char.repeat(64);
const STORE_NOW = "synthetic-store", STORE_G0 = "synthetic-store-g0", PROFILE = "synthetic-bf07";
let fixture;
const runtimes = [];   // every native runtime opened by this file: none may ever call a model

function runPython(script, ...args) {
  const environment = Object.fromEntries(["SystemRoot", "WINDIR", "TEMP", "TMP"].filter(key => process.env[key]).map(key => [key, process.env[key]]));
  environment.PATH = dirname(python);
  const result = spawnSync(python, ["-I", "-X", "utf8", "-c", script, repository, ...args], { encoding: "utf8", env: environment, timeout: 120000, maxBuffer: 24 * 1024 * 1024 });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
}

before(() => {
  assert.equal(process.versions.node, "26.4.0");
  fixture = runPython(`
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
from renulus.design_c_contracts import canonical_digest
s=create_app(Path(sys.argv[2])).state.services
threads=[s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC '+t),'bf07-create-'+t) for t in ['C1','E','X','D']]
with s.db.transaction() as c:
    c.execute("INSERT INTO preferences VALUES('study.goals','[]','now')")
    c.execute("INSERT INTO deletion_ledger VALUES('learn_thread','synthetic-removed','now')")
    c.execute("INSERT INTO learn_runs VALUES('bf00-run',?,'bf00-run-key','completed',NULL,'now','now')",(threads[0]['identity']['id'],))
    c.execute("INSERT INTO learn_messages VALUES('bf00-msg',?,'bf00-run','assistant','SYNTHETIC answer','[]','now')",(threads[0]['identity']['id'],))
    c.execute("INSERT INTO learning_evidence VALUES('bf00-evidence','synthetic','aki',?,'{}','now')",(threads[0]['identity']['id'],))
with s.db.connect() as c:
    query=lambda sql:[dict(row) for row in c.execute(sql)]
    objects=query("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")
    tables=[]
    for o in objects:
        if o['type']!='table':continue
        name=o['name'];indexes=[]
        for definition in query(f'PRAGMA index_list("{name}")'):
            indexes.append({'definition':definition,'columns':query('PRAGMA index_xinfo("'+definition['name']+'")')})
        tables.append({'name':name,'columns':query(f'PRAGMA table_xinfo("{name}")'),'foreignKeys':query(f'PRAGMA foreign_key_list("{name}")'),'indexes':indexes})
    schema_hash=canonical_digest({'objects':objects,'tables':tables})
print(json.dumps({'databasePath':str(s.paths.database),'schemaHash':schema_hash,'threads':[t['identity']['id'] for t in threads]}))
`, join(root, "python-source"));
  const db = new DatabaseSync(fixture.databasePath);
  db.exec("PRAGMA wal_checkpoint(TRUNCATE); PRAGMA journal_mode=DELETE"); db.close();
});
after(async () => {
  for (const runtime of runtimes) await runtime.close().catch(() => {});
  assert.match(path.basename(root), /^renulus-bf07-journey-/);
  // Windows may still hold a just-disposed SQLite handle; the unique temp directory is retained for diagnostics then.
  try { rmSync(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 }); } catch { /* retained */ }
});

// ---------------------------------------------------------------- native stores
async function openNative(database, scratch) {
  const workspace = join(scratch, "workspace");
  mkdirSync(workspace, { recursive: true }); mkdirSync(dirname(database), { recursive: true });
  let calls = 0;
  const denied = () => { calls++; return new AIError({ reason: new InvalidRequestError({ message: "Synthetic BF07 recovery forbids inference." }) }); };
  const client = { stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()), compact: () => Effect.fail(denied()) };
  const content = JSON.stringify({ compaction: { auto: false }, agents: { title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-bf07-recovery-test", version: "1" }, database: { path: database },
    config: { directory: join(scratch, "config"), project: false, content },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(["home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos"].map(key => [key, join(scratch, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const sdk = await runtime.runPromise(OpenCode.Service);
  const native = { sdk, database, run: effect => runtime.runPromise(effect), location: { directory: AbsolutePath.make(workspace) }, calls: () => calls,
    async close() { if (native.closed) return; native.closed = true; await runtime.dispose(); checkpoint(database); } };
  runtimes.push(native);
  return native;
}
function checkpoint(file) {
  const db = new DatabaseSync(file);
  try { db.exec("PRAGMA wal_checkpoint(TRUNCATE)"); } finally { db.close(); }
  for (const suffix of ["-wal", "-shm"]) if (existsSync(file + suffix) && statSync(file + suffix).size === 0) rmSync(file + suffix, { force: true });
}
const T0 = Date.parse("2026-10-20T10:00:00Z");
const user = (id, text, at) => ({ id, type: "user", time: { created: T0 + at }, text });
const assistant = (id, text, at, tool) => ({ id, type: "assistant", agent: "synthetic", model: { providerID: "synthetic", id: "recovery" },
  time: { created: T0 + at, completed: T0 + at + 1 },
  content: [...(tool ? [{ type: "tool", id: tool, name: "synthetic_lookup", state: { status: "completed", input: { query: "potassium" },
    content: [{ type: "text", text: "synthetic tool result" }] }, time: { created: T0 + at, completed: T0 + at } }] : []), { type: "text", text }] });
const sid = name => "ses_" + sha("session:" + name), mid = name => "msg_" + sha("message:" + name);
const S = { C1: sid("c1"), E: sid("e"), X: sid("x"), X1: sid("x-child"), D: sid("d") };
const M = { u1: mid("u1"), a1: mid("a1"), u2: mid("u2"), a2: mid("a2"), ue: mid("ue"), ae: mid("ae"), ux: mid("ux"), ax: mid("ax"), uc: mid("uc"), ac: mid("ac"), ud: mid("ud"), ad: mid("ad") };
const c1Base = () => [user(M.u1, "Synthetic: potassium 5.2 mmol/L", 0), assistant(M.a1, "Synthetic retained answer", 1000)];
const GRAPHS = {
  g0: [{ id: S.C1, title: "C1", messages: c1Base() },
    { id: S.E, title: "E", messages: [user(M.ue, "Synthetic deleted topic", 500), assistant(M.ae, "Synthetic answer to be deleted", 1500)] },
    { id: S.X, title: "X", messages: [user(M.ux, "Synthetic: explain sodium", 2000), assistant(M.ax, "Synthetic sodium answer", 3000, "call_x1")] },
    { id: S.X1, parentID: S.X, title: "X child", messages: [user(M.uc, "Synthetic child task", 3500), assistant(M.ac, "Synthetic child result", 3600)] }],
  current: [{ id: S.C1, title: "C1", messages: [...c1Base(), user(M.u2, "Synthetic: newer M2", 60000), assistant(M.a2, "Synthetic newer answer", 61000)] },
    { id: S.D, title: "D", messages: [user(M.ud, "Synthetic: new conversation D", 120000), assistant(M.ad, "Synthetic D answer", 121000)] }],
};
async function seed(native, storeId, sessions) {
  const template = await native.run(native.sdk.sessions.create({ id: Session.ID.make("ses_" + sha("template:" + storeId + randomUUID())), location: native.location,
    metadata: { synthetic: true }, permissions: [{ action: "read", resource: "*", effect: "allow" }] }));
  for (const s of sessions) {
    await native.run(native.sdk.sessions.import({ location: native.location,
      info: { ...template, id: Session.ID.make(s.id), ...(s.parentID ? { parentID: Session.ID.make(s.parentID) } : {}), title: s.title, metadata: { renulusStore: storeId, synthetic: true } },
      messages: s.messages.map(m => Schema.decodeUnknownSync(SessionMessage.Info)(m)) }));
  }
  await native.run(native.sdk.sessions.remove({ sessionID: template.id }));
}
const recoveryOf = (native, storeId = STORE_NOW, checkHeld = () => {}) => createGraphRecovery({ sdk: native.sdk, run: native.run, storeId, location: native.location, checkHeld });
async function scratchGraph(database, storeId = STORE_NOW) {
  const scratch = join(root, "scratch", randomUUID()), copy = join(scratch, "opencode.sqlite");
  mkdirSync(scratch, { recursive: true }); copyFileSync(database, copy);
  const native = await openNative(copy, join(scratch, "runtime"));
  try { return await recoveryOf(native, storeId).snapshotAll(); } finally { await native.close(); }
}
async function rejectsWith(promise, code, name = code) {
  await assert.rejects(promise, error => { assert.ok(String(error.code ?? error.message).includes(code), `${name}: got ${error.code ?? error.message}`); return true; });
}
const ids = graph => ({ sessions: new Set(graph.sessions.map(s => String(s.info.id))), messages: new Set(graph.sessions.flatMap(s => s.messages.map(m => String(m.id)))) });

// ---------------------------------------------------------------- canonical stores
function seedCanonical(file, kind) {
  const db = new DatabaseSync(file), [C1, E, X, D] = fixture.threads, store = kind === "g0" ? STORE_G0 : STORE_NOW;
  db.exec("PRAGMA foreign_keys=ON");
  const link = (thread, session) => db.prepare("INSERT INTO learn_harness_mappings VALUES(?,?,?,?,?,?,?)").run(thread, PROFILE, store, session,
    canonical({ store_id: store, session_id: session }), "create-" + thread, "synthetic-process");
  const answer = (run, thread, state, session, input) => db.prepare("INSERT INTO learn_harness_answers VALUES(?,?,?,?,?,?,?,?,?)").run(run, thread, hex("d"), state, input,
    canonical({ runtime: { store_id: store }, session_id: session, message_id: input }), null, null, "synthetic-process");
  const run = (id, thread, text) => {
    db.prepare("INSERT INTO learn_runs VALUES(?,?,?,'completed',NULL,'now','now')").run(id, thread, id + "-key");
    db.prepare("INSERT INTO learn_messages VALUES(?,?,?,'assistant',?,'[]','now')").run(id + "-msg", thread, id, text);
  };
  if (kind === "g0") {
    for (const thread of [D]) { db.prepare("DELETE FROM conversation_commands WHERE target_id=?").run(thread); db.prepare("DELETE FROM learn_threads WHERE id=?").run(thread); }
    link(C1, S.C1); link(E, S.E); link(X, S.X);
    answer("bf00-run", C1, "completed", S.C1, M.u1);
    run("x-run", X, "Synthetic sodium answer");
    answer("x-run", X, "submitted", S.X, M.ux);   // an incoming live claim: must never resume
    db.prepare("INSERT INTO learning_evidence VALUES('x-evidence','synthetic','aki',?,'{}','now')").run(X);
  } else {
    // X was lost from the current stores without a tombstone; E was deleted with a typed tombstone.
    for (const thread of [X, E]) { db.prepare("DELETE FROM conversation_commands WHERE target_id=?").run(thread); db.prepare("DELETE FROM learn_threads WHERE id=?").run(thread); }
    db.prepare("INSERT INTO deletion_ledger VALUES('learn_thread',?,'later')").run(E);
    link(C1, S.C1); link(D, S.D);
    answer("bf00-run", C1, "completed", S.C1, M.u1);
    run("attempt-a", C1, "Synthetic newer attempt A");
    answer("attempt-a", C1, "completed", S.C1, M.u2);
  }
  assert.deepEqual(db.prepare("PRAGMA foreign_key_check").all(), []);
  db.exec("PRAGMA wal_checkpoint(TRUNCATE); PRAGMA journal_mode=DELETE"); db.close();
}
function admit(profile) {
  const selection = { contract: "renulus-storage-selector/1", isolation: "synthetic", profileId: PROFILE, generation: 1, authorityEpoch: 1, writer: "ts",
    state: "active", ownerId: "synthetic-recovery-owner", database: "state/renulus.sqlite3" };
  writeFileSync(join(profile, MARKER), JSON.stringify({ contract: "renulus-synthetic-storage/1", profileId: PROFILE }));
  writeFileSync(join(profile, SELECTOR), JSON.stringify(selection));
  return { profileRoot: profile, selection, migrations, expectedSchemaHash: fixture.schemaHash };
}
const openCanonical = profile => openIsolatedStorage(admit(profile));
// ---------------------------------------------------------------- generations
const MEMBERS = ["state/renulus.sqlite3", "state/harness/opencode.sqlite", "state/harness/effective-selector.json", "plugins/artifact.json", "schema/inventory.json"];
const ROLES = { "state/renulus.sqlite3": "canonical", "state/harness/opencode.sqlite": "native", "state/harness/effective-selector.json": "selector",
  "plugins/artifact.json": "plugin", "schema/inventory.json": "schema" };
const roleOf = member => ROLES[member] ?? "original";
function put(dir, member, text) { mkdirSync(dirname(join(dir, member)), { recursive: true }); writeFileSync(join(dir, member), text); }
function frontierOf(dir) {
  const db = new DatabaseSync(join(dir, "state/renulus.sqlite3"), { readOnly: true });
  try { return recoveryFrontierDigest(db); } finally { db.close(); }
}
const header = (dir, generation, epoch) => ({ profileId: PROFILE, generation, authorityEpoch: epoch, schemaHash: fixture.schemaHash, cohortHash: hex("b"), frontierDigest: frontierOf(dir) });
const memberFiles = originals => [...MEMBERS, ...originals].map(path => ({ role: roleOf(path), path }));
function observe(dir, originals, generation = 1, epoch = 1) {
  const files = memberFiles(originals).map(m => { const bytes = readFileSync(join(dir, m.path)); return { ...m, sha256: sha(bytes), bytes: bytes.length }; });
  return { manifest: { ...header(dir, generation, epoch), members: files }, observedMembers: files };
}
function bytesOf(dir, originals) { return memberFiles(originals).reduce((n, m) => n + statSync(join(dir, m.path)).size, 0); }
function copyNoReplace(from, to) { mkdirSync(dirname(to), { recursive: true }); copyFileSync(from, to, 1); }   // COPYFILE_EXCL

/** Builds the backup generation G0 and the live CURRENT generation (newer M2, new conversation D, attempt A). */
async function world(t, { g0Originals = { "originals/o1.bin": "synthetic shared original", "originals/o2.bin": "synthetic incoming-only original" }, originalRecords = false } = {}) {
  const profile = join(root, "world-" + randomUUID().slice(0, 8)), g0 = join(profile, "backups/g0"), g1 = join(profile, "generations/g1");
  const build = async (dir, kind, sessions, storeId, originals) => {
    mkdirSync(join(dir, "state/harness"), { recursive: true });
    copyFileSync(fixture.databasePath, join(dir, "state/renulus.sqlite3")); seedCanonical(join(dir, "state/renulus.sqlite3"), kind);
    const native = await openNative(join(dir, "state/harness/opencode.sqlite"), join(profile, "scratch", kind));
    await seed(native, storeId, sessions); await native.close();
    put(dir, "state/harness/effective-selector.json", canonical({ selector: "synthetic-effective" }));
    put(dir, "plugins/artifact.json", canonical({ plugin: "synthetic-capability", cohort: hex("b") }));
    put(dir, "schema/inventory.json", canonical({ schemaHash: fixture.schemaHash }));
    for (const [member, text] of Object.entries(originals)) put(dir, member, text);
    if (originalRecords) {
      const db = new DatabaseSync(join(dir,"state/renulus.sqlite3"));
      const rights = {display:true,cache:true,index:true,embedding:true,model_input:true,derivation:true,evaluation:false,redistribution:false,licence:"synthetic",permission_reference:"synthetic",attribution:"synthetic"};
      db.prepare("INSERT INTO knowledge_documents VALUES('shared-doc','SYNTHETIC shared','synthetic','personal-library',NULL,0,'shared-rev','shared-rev',NULL,'now','now')").run();
      db.prepare("INSERT INTO knowledge_revisions(id,document_id,ordinal,status,sha256,media_type,bytes,original_path,metadata_json,rights_json,created_at) VALUES('shared-rev','shared-doc',1,'ready',?,'text/plain',?,'originals/o1.bin','{}',?,'now')").run(sha("synthetic shared original"), Buffer.byteLength("synthetic shared original"), canonical(rights));
      const add = (id,thread,file,body,allowed) => {
        db.prepare("INSERT INTO knowledge_attachments VALUES(?,'learning',?,'SYNTHETIC attachment','text/plain',1,'not_requested','not_requested','now','now')").run(id,thread);
        db.prepare("INSERT INTO knowledge_attachment_metadata(attachment_id,filename,source_id,metadata_json,rights_json) VALUES(?,'synthetic.txt','synthetic','{}',?)").run(id,canonical({...rights,cache:allowed}));
        db.prepare("INSERT INTO knowledge_attachment_originals VALUES(?,?,'original',?,?,?,'now')").run(id+'-original',id,file,sha(body),Buffer.byteLength(body));
      };
      add('shared-attachment',fixture.threads[0],'originals/o1.bin','synthetic shared original',kind==='g0');
      if(kind==='g0')add('owned-attachment',fixture.threads[2],'originals/o2.bin','synthetic incoming-only original',true);
      db.close();
    }
  };
  await build(g0, "g0", GRAPHS.g0, STORE_G0, g0Originals);
  const g0Originals_ = Object.keys(g0Originals);
  sealGeneration(g0, header(g0, 1, 1), memberFiles(g0Originals_));
  await build(g1, "current", GRAPHS.current, STORE_NOW, { "originals/o1.bin": "synthetic shared original" });
  sealGeneration(g1, header(g1, 1, 1), memberFiles(["originals/o1.bin"]));
  const live = { canonical: await openCanonical(g1), native: await openNative(join(g1, "state/harness/opencode.sqlite"), join(profile, "scratch/live")) };
  // The real native storage worker, opened on first use. Only free space is synthetic: this development volume is below the 12 GiB floor.
  let worker, io;
  const open = async () => {
    if (io) return io;
    mkdirSync(join(profile, "native-originals"), { recursive: true }); mkdirSync(join(profile, "native-grants"), { recursive: true });
    worker = await openEngineWorker({ python, sourceRoot: repository, launchRoot: join(profile, "worker-launch-storage"),
      identity: { profile_id: PROFILE, domain_store_id: "synthetic-domain", runtime_store_id: STORE_NOW, authority_epoch: 1, process_generation: randomUUID() },
      retention: "saved", current: () => ({ configuration: 0, grant: 0, context: 0, deletion: 0, cancellation: 0 }),
      native: { originals_root: join(profile, "native-originals"), budget_root: profile, grants_root: join(profile, "native-grants"), grant_token_sha256: hex("a") } });
    return io = createWorkerKnowledgeIO(worker.channel, worker.ready.capacity.max_chunk_bytes);
  };
  const storage = { async measure() { return { ...await (await open()).measure(), freeBytes: 200_000_000_000 }; }, async retire(id) { return (await open()).retire(id); } };
  const w = { profile, g0, g1, g0Originals: g0Originals_, live, events: [], remote: Promise.withResolvers(), candidates: new Map(), authority: publish(profile, "g1", 1, 1), storage };
  t.after(async () => { await live.canonical.close().catch(() => {}); await worker?.close(); });
  return w;
}
function publish(profile, name, generation, epoch) {
  const manifestSha256 = sha(readFileSync(join(profile, "generations", name, GENERATION_MANIFEST)));
  const selector = { contract: "renulus-backend-selector/1", profileId: PROFILE, generation, authorityEpoch: epoch, writer: "ts", state: "active",
    generationPath: `generations/${name}`, manifestSha256, schemaHash: fixture.schemaHash, cohortHash: hex("b") };
  writeFileSync(join(profile, BACKEND_SELECTOR), canonical(selector));
  const ownerGeneration = "1".repeat(32);
  writeFileSync(join(profile, ".renulus-profile-owner.json"), JSON.stringify({ generation: ownerGeneration, job_policy: "kill_on_close_no_breakaway_v1",
    python: { pid: process.ppid, creation_filetime: 1 }, native: [{ process: { pid: process.pid, creation_filetime: 2 } }] }));
  const authority = { contract: "renulus-selected-writer/1", profileRoot: profile, generationRoot: join(profile, "generations", name),
    selectorSha256: sha(readFileSync(join(profile, BACKEND_SELECTOR))), authorityEpoch: epoch, ownerGeneration, predecessorGeneration: null,
    ownerReceiptSha256: sha(readFileSync(join(profile, ".renulus-profile-owner.json"))), nodePid: process.pid, nodeCreationFiletime: "2",
    supervisorPid: process.ppid, supervisorCreationFiletime: "1", nonceSha256: sha("synthetic-nonce") };
  writeFileSync(join(profile, ".renulus-selected-owner.json"), canonical(authority));
  return authority;
}

/** The restore input: G0's closed generation read WITHOUT modifying it (stores are read from scratch copies). */
async function incomingOf(w) {
  const { manifest, observedMembers } = observe(w.g0, w.g0Originals);
  const profile = join(root, "scratch", randomUUID());
  mkdirSync(join(profile, "state"), { recursive: true }); copyFileSync(join(w.g0, "state/renulus.sqlite3"), join(profile, "state/renulus.sqlite3"));
  const storage = await openCanonical(profile);
  let records;
  try { records = await storage.command({ type: "recovery.snapshot" }); } finally { await storage.close(); }
  return { incoming: manifest, observedMembers, canonical: records, native: await scratchGraph(join(w.g0, "state/harness/opencode.sqlite"), STORE_G0) };
}
const originalsOf = dir => Object.fromEntries(["originals/o1.bin", "originals/o2.bin", ...(existsSync(join(dir,"owned-originals")) ? readdirSync(join(dir,"owned-originals")).filter(n=>n.startsWith("original_")).map(n=>"owned-originals/"+n) : [])].filter(m => existsSync(join(dir, m))).map(m => [m, sha(readFileSync(join(dir, m)))]));

/** Synthetic generation I/O; graph coordination runs through the production owner. */
function coordinatorOptions(w) {
  const profileLive = w.g1, events = w.events;
  const current = {
    async describe() { return { profileId: PROFILE, schemaHash: fixture.schemaHash, cohortHash: hex("b"), bytes: bytesOf(profileLive, ["originals/o1.bin"]), originals: originalsOf(profileLive) }; },
    async closeAdmission() { events.push("admission-closed"); },
    async drain() { await w.remote.promise; events.push("remote-drained"); },   // remote work first, engine guards after
    async snapshotClosed() {
      await w.live.canonical.close(); events.push("canonical-guard-closed");
      await w.live.native.close(); events.push("native-guard-closed");
      return (w.closed = observe(profileLive, ["originals/o1.bin"]));
    },
  };
  return createRecoveryOwner({
    current, storage: w.live.canonical, native: recoveryOf(w.live.native), storeId: STORE_NOW,
    nativeStorage: w.storage,
    async forkCurrent() {
      const id = "g2", dir = join(w.profile, "generations", id);
      mkdirSync(join(dir, "state/harness"), { recursive: true });
      copyNoReplace(join(profileLive, "state/renulus.sqlite3"), join(dir, "state/renulus.sqlite3"));
      const storage = await openCanonical(dir), native = await openNative(join(dir, "state/harness/opencode.sqlite"), join(w.profile, "scratch", id));
      w.candidates.set(id, { dir, storage, native });
      return { storage, candidateId: id, native: recoveryOf(native), close:()=>native.close() };
    },
    async verifyOriginals(id, incoming, records) {
      const candidate = w.candidates.get(id);
      for (const m of incoming.members.filter(member => member.role === "original")) {
        const source = join(w.g0, m.path);
        if (sha(readFileSync(source)) !== m.sha256) throw new Error("original_unavailable");
        if (existsSync(join(candidate.dir, m.path))) assert.equal(sha(readFileSync(join(candidate.dir, m.path))), m.sha256);
        else copyNoReplace(source, join(candidate.dir, m.path));
      }
      return records;
    },
    async closeCandidate(id) {
      const candidate = w.candidates.get(id);
      await candidate.native.close();
      for (const member of MEMBERS.slice(2)) copyNoReplace(join(profileLive, member), join(candidate.dir, member));
      for (const member of Object.keys(originalsOf(profileLive))) if (!existsSync(join(candidate.dir, member))) copyNoReplace(join(profileLive, member), join(candidate.dir, member));
      return observeAndSeal(candidate.dir, Object.keys(originalsOf(candidate.dir)));
    },
  });
}
function observeAndSeal(dir, originals) {
  const manifest = sealGeneration(dir, header(dir, 2, 2), memberFiles(originals));
  return { manifest, observedMembers: observe(dir, originals).observedMembers };
}
const finish = w => { w.remote.resolve(); };
test("paired recovery journey: preview is read-only; Restore is additive over newer M2/D/A; incoming-only graph closure is imported inertly; selection publishes held", async t => {
  const w = await world(t), input = await incomingOf(w), options = coordinatorOptions(w), coordinator = createRecoveryCoordinator(options);
  const before = canonical((await w.live.canonical.command({ type: "recovery.snapshot" })).records);
  const preview = await coordinator.preview(input);
  // Read-only: nothing closed, nothing changed, nothing reserved.
  assert.deepEqual(w.events, []);
  assert.equal(canonical((await w.live.canonical.command({ type: "recovery.snapshot" })).records), before);
  assert.equal((await w.live.canonical.command({ type: "storage.reservations" })).reservations, 0);
  assert.deepEqual(preview.canonical.excludedNativeSessions, [S.E].sort());
  assert.ok(preview.canonical.eligibleNativeSessions.includes(S.X) && preview.canonical.eligibleNativeSessions.includes(S.C1));
  assert.deepEqual(preview.native, { retained: 2, currentOnly: 4, added: 4, excluded: 1 });   // C1 u1/a1 retained; M2+D current-only; X+X1 added; E excluded
  assert.deepEqual(preview.originals, { count: 2, bytes: "synthetic shared original".length + "synthetic incoming-only original".length, retained: 1, added: 1 });
  assert.equal(preview.space.fits, true);
  assert.ok(preview.canonical.added > 0 && preview.canonical.excluded > 0 && preview.canonical.retained > 0);

  const done = setTimeout(() => finish(w), 150);
  const prepared = await coordinator.prepare(input); clearTimeout(done);
  // Logical hold, THEN remote drain, THEN the engine guards; the stores were closed only after both.
  assert.deepEqual(w.events, ["admission-closed", "remote-drained", "canonical-guard-closed", "native-guard-closed"]);
  assert.equal(prepared.manifest.generation, 2);
  // The current generation is byte-identical after preparation: the candidate is separate.
  assert.deepEqual(observe(w.g1, ["originals/o1.bin"]).observedMembers, w.closed.observedMembers);

  // Candidate canonical: current work kept, incoming-only X added, E excluded by the tombstone, nothing live resumes.
  const [C1, E, X, D] = fixture.threads, db = new DatabaseSync(join(w.profile, "generations/g2/state/renulus.sqlite3"), { readOnly: true });
  const all = (sql, ...p) => db.prepare(sql).all(...p);
  assert.deepEqual(all("SELECT id FROM learn_threads WHERE id IN (?,?,?,?) ORDER BY id", C1, E, X, D).map(r => r.id), [C1, X, D].sort());
  assert.equal(all("SELECT 1 FROM learn_runs WHERE id='attempt-a'").length, 1);                          // attempt A kept
  assert.equal(all("SELECT state FROM learn_harness_answers WHERE run_id='attempt-a'")[0].state, "completed");
  assert.deepEqual({ ...all("SELECT store_id,session_id FROM learn_harness_mappings WHERE thread_id=?", X)[0] }, { store_id: STORE_NOW, session_id: S.X });   // rewritten through the mapping
  assert.equal(JSON.parse(all("SELECT mapping_json FROM learn_harness_mappings WHERE thread_id=?", X)[0].mapping_json).store_id, STORE_NOW);
  assert.equal(all("SELECT 1 FROM learn_harness_mappings WHERE thread_id=?", E).length, 0);
  assert.equal(all("SELECT state FROM learn_harness_answers WHERE run_id='x-run'")[0].state, "cancelled");      // incoming claim never resumes
  assert.equal(all("SELECT value FROM preferences WHERE key='memory.restore_barrier:x-evidence'")[0].value, "explicit-capture-required");
  assert.equal(all("SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=?", E).length, 1);
  assert.deepEqual(JSON.parse(all("SELECT value FROM preferences WHERE key='storage.reservations/1'")[0].value).active, {});   // recovery's own reservation settled
  assert.deepEqual(all("PRAGMA foreign_key_check"), []);
  assert.equal(all("PRAGMA integrity_check")[0].integrity_check, "ok");
  db.close();

  // Candidate native: reopened from files without inference; current mutable state wins, incoming-only closure is inert.
  const reopened = await scratchGraph(join(w.profile, "generations/g2/state/harness/opencode.sqlite")), current = await scratchGraph(join(w.g1, "state/harness/opencode.sqlite"));
  const byId = new Map(reopened.sessions.map(s => [String(s.info.id), s]));
  assert.deepEqual([...byId.keys()].sort(), [S.C1, S.D, S.X, S.X1].sort());                              // E excluded, X/X1 added
  const c1 = byId.get(S.C1);
  assert.deepEqual(c1.messages.map(m => m.id), [M.u1, M.a1, M.u2, M.a2]);                                // M2 retained
  assert.equal(canonical(c1.messages), canonical(current.sessions.find(s => s.info.id === S.C1).messages));
  assert.deepEqual(c1.info.permissions, [{ action: "read", resource: "*", effect: "allow" }]);           // current grants kept exactly
  assert.equal(byId.get(S.X1).info.parentID, S.X);                                                       // child closure
  const x = byId.get(S.X);
  assert.equal(x.messages[1].content[0].type, "tool"); assert.equal(x.messages[1].content[0].state.status, "completed");
  assert.deepEqual(x.info.permissions, [{ action: "*", resource: "*", effect: "deny" }]);
  assert.equal(x.info.metadata.recoveryInert, true); assert.equal(x.info.metadata.renulusStore, STORE_NOW);
  // Closure holds for every current AND incoming canonical->native link.
  const candidateProfile = join(root, "scratch", randomUUID());
  mkdirSync(join(candidateProfile, "state"), { recursive: true }); copyFileSync(join(w.profile, "generations/g2/state/renulus.sqlite3"), join(candidateProfile, "state/renulus.sqlite3"));
  const storage = await openCanonical(candidateProfile);
  try { verifyNativeClosure((await storage.command({ type: "recovery.snapshot" })).records, ids(reopened)); } finally { await storage.close(); }
  assert.equal(runtimes.reduce((n, r) => n + r.calls(), 0), 0);                                          // zero inference anywhere

  // Selection: expected owner/epoch; published held, last. The old selector is untouched until then.
  const selectorBefore = readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8");
  const port = createRecoveryPort({ authority: w.authority, verifyBinaries: async () => { throw new Error("synthetic_binary_mismatch"); } });
  const frontier = frontierOf(w.g1);
  await assert.rejects(port.select({ generationPath: "generations/g2", rollback: false }, async () => frontier), /synthetic_binary_mismatch/);
  assert.equal(readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8"), selectorBefore);
  const selector = await createRecoveryPort({ authority: w.authority, verifyBinaries: async () => {} }).select({ generationPath: "generations/g2", rollback: false }, async () => frontier);
  assert.deepEqual([selector.state, selector.generation, selector.authorityEpoch, selector.generationPath], ["held", 2, 2, "generations/g2"]);
  assert.equal(resolveBackendSelection(w.profile).admission, "held");
});

test("shared and owned attachment originals publish through the native worker; current rights win and handles rebase into the candidate", async t => {
  const w=await world(t,{originalRecords:true}), input=await incomingOf(w), options=coordinatorOptions(w);
  const dir=join(w.profile,"generations/g2"), originals=join(dir,"owned-originals"), grants=join(w.profile,"synthetic-grants");
  let worker, native;
  t.after(async()=>{await worker?.close();});
  options.verifyOriginals=async(id,manifest,records)=>{
    mkdirSync(originals,{recursive:true});mkdirSync(grants,{recursive:true});
    worker=await openEngineWorker({python,sourceRoot:repository,launchRoot:join(w.profile,"worker-launch"),
      identity:{profile_id:PROFILE,domain_store_id:"synthetic-domain",runtime_store_id:STORE_NOW,authority_epoch:1,process_generation:randomUUID()},
      retention:"saved",current:()=>({configuration:0,grant:0,context:0,deletion:0,cancellation:0}),
      native:{originals_root:originals,budget_root:w.profile,grants_root:grants,grant_token_sha256:hex("a")}});
    native=createWorkerKnowledgeIO(worker.channel,worker.ready.capacity.max_chunk_bytes);
    return publishRecoveryOriginals(records,async(table,id,pin)=>readFileSync(join(id==="owned-attachment-original"?w.g0:w.g1,pin.original_handle)),native);
  };
  const close=options.closeCandidate;
  options.closeCandidate=async id=>{await worker.close();return close(id);};
  finish(w);
  const prepared=await createRecoveryCoordinator(options).prepare(input);
  const db=new DatabaseSync(join(dir,"state/renulus.sqlite3"),{readOnly:true});
  const shared=db.prepare("SELECT original_path FROM knowledge_revisions WHERE id='shared-rev'").get().original_path;
  const owned=db.prepare("SELECT original_path FROM knowledge_attachment_originals WHERE id='owned-attachment-original'").get().original_path;
  assert.match(shared,/^original_[a-f0-9]{64}$/);assert.match(owned,/^original_[a-f0-9]{64}$/);
  assert.equal(db.prepare("SELECT original_path FROM knowledge_attachment_originals WHERE id='shared-attachment-original'").get().original_path,null);
  assert.equal(readFileSync(join(originals,shared+".txt"),"utf8"),"synthetic shared original");
  assert.equal(readFileSync(join(originals,owned+".txt"),"utf8"),"synthetic incoming-only original");
  assert.ok(prepared.manifest.members.some(m=>m.path==="owned-originals/"+owned+".txt"));
  assert.deepEqual(db.prepare("PRAGMA foreign_key_check").all(),[]);db.close();
});

test("coordinator rollback refuses newer canonical/native loss and prepares a complete target while retaining current frontiers and grants", async t=>{
  const lost=await world(t), old=await incomingOf(lost), before=readFileSync(join(lost.profile,BACKEND_SELECTOR),"utf8");
  await rejectsWith(createRecoveryCoordinator(coordinatorOptions(lost)).prepareRollback(old),"recovery_rollback_newer_records");
  assert.deepEqual(lost.events,[]);assert.equal(readFileSync(join(lost.profile,BACKEND_SELECTOR),"utf8"),before);
  const w=await world(t), options=coordinatorOptions(w), observed=observe(w.g1,["originals/o1.bin"]);
  const records=await w.live.canonical.command({type:"recovery.snapshot"});
  const graph=await recoveryOf(w.live.native).snapshotAll();
  // The target predates the frontier: current tombstones still govern the prepared rollback.
  records.records.deletion_ledger=[];
  const input={incoming:observed.manifest,observedMembers:observed.observedMembers,canonical:records,native:graph};
  finish(w);const result=await createRecoveryCoordinator(options).prepareRollback(input);
  assert.equal(result.manifest.generation,2);
  const db=new DatabaseSync(join(w.profile,"generations/g2/state/renulus.sqlite3"),{readOnly:true});
  assert.equal(db.prepare("SELECT 1 FROM deletion_ledger WHERE entity_type='learn_thread' AND entity_id=?").all(fixture.threads[1]).length,1);
  assert.equal(db.prepare("SELECT 1 FROM learn_runs WHERE id='attempt-a'").all().length,1);db.close();
  const reopened=await scratchGraph(join(w.profile,"generations/g2/state/harness/opencode.sqlite"));
  assert.deepEqual(reopened.sessions.find(s=>s.info.id===S.C1).info.permissions,graph.sessions.find(s=>s.info.id===S.C1).info.permissions);
});

test("conflicting immutable identity or incompatible relations refuse the preview and prepare: selector untouched, nothing closed, nothing restored", async t => {
  const w = await world(t), input = await incomingOf(w), coordinator = createRecoveryCoordinator(coordinatorOptions(w));
  const selector = readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8");
  const mutate = (fn, graph = structuredClone(input.native)) => { fn(graph); return { ...input, native: graph }; };
  const session = (graph, id) => graph.sessions.find(s => s.info.id === id);
  const cases = {
    "same message identity with different bytes": [mutate(g => { session(g, S.C1).messages[1].content[0].text = "Synthetic CHANGED bytes"; }), "recovery_graph_identity_conflict"],
    "incompatible order": [mutate(g => { session(g, S.C1).messages.reverse(); }), "recovery_graph_order"],
    "incompatible parent relation": [mutate(g => { session(g, S.C1).info.parentID = S.X; }), "recovery_graph_identity_conflict"],
    // Incoming has a different message where current already has M2: a divergent suffix is never interleaved.
    "divergent suffix is never interleaved": [mutate(g => { session(g, S.C1).messages.splice(2, 0, assistant(mid("alt"), "Synthetic divergent", 70000)); }), "recovery_graph_identity_conflict"],
    "dangling tool/child relation": [mutate(g => { session(g, S.X1).info.parentID = sid("missing"); }), "recovery_graph_parent_missing"],
    "immutable canonical row with different bytes": [{ ...input, canonical: { ...input.canonical, records: { ...input.canonical.records,
      learn_messages: input.canonical.records.learn_messages.map(r => r.id === "bf00-msg" ? { ...r, content: "SYNTHETIC CHANGED" } : r) } } }, "recovery_immutable_conflict"],
    "missing deletion frontier": [{ ...input, canonical: { ...input.canonical, records: Object.fromEntries(Object.entries(input.canonical.records).filter(([k]) => k !== "deletion_ledger")) } }, "recovery_frontier_missing"],
    "different schema": [{ ...input, canonical: { ...input.canonical, schemaHash: hex("9") } }, "recovery_schema_mismatch"],
  };
  for (const [name, [bad, code]] of Object.entries(cases)) {
    await rejectsWith(coordinator.preview(bad), code, name);
    await rejectsWith(coordinator.prepare(bad), code, name);
  }
  // An original with the same identity but different bytes is a hard conflict; a missing member refuses activation.
  const tampered = { ...input, incoming: { ...input.incoming, members: input.incoming.members.map(m => m.path === "originals/o1.bin" ? { ...m, sha256: hex("e") } : m) } };
  tampered.observedMembers = tampered.incoming.members;
  await rejectsWith(coordinator.preview(tampered), "recovery_immutable_conflict");
  await rejectsWith(coordinator.preview({ ...input, observedMembers: input.observedMembers.slice(1) }), "recovery_generation_member_mismatch");
  // Never combined with an incompatible (older/other cohort) replacement runtime.
  await rejectsWith(coordinator.preview({ ...input, incoming: { ...input.incoming, cohortHash: hex("7") } }), "recovery_generation_incompatible");
  assert.deepEqual(w.events, []);                                                   // admission was never closed
  assert.equal(readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8"), selector);
  assert.equal(existsSync(join(w.profile, "generations/g2")), false);               // nothing partially restored
  assert.equal((await w.live.canonical.command({ type: "storage.reservations" })).reservations, 0);
  assert.equal((await coordinator.preview(input)).native.added, 4);                 // the unmodified input is still accepted
});

test("low space, an unsettled native stream and engine death while snapshotting refuse before anything is closed; originals and debt are preserved", async t => {
  const w = await world(t), input = await incomingOf(w), base = coordinatorOptions(w);
  const refused = async (options, code) => {
    await rejectsWith(createRecoveryCoordinator({ ...base, ...options }).prepare(input), code);
    assert.deepEqual(w.events, []); assert.equal(existsSync(join(w.profile, "generations/g2")), false);
    assert.equal(readFileSync(join(w.g1, "originals/o1.bin"), "utf8"), "synthetic shared original");
  };
  // Low space: waiting-space, nothing reserved (the 12 GiB floor is retained).
  await refused({ measure: async () => ({ allocatedBytes: 1, freeBytes: 12 * 1024 ** 3 + 10, ceilingBytes: 100_000_000_000 }) }, "storage_waiting_space");
  await refused({ measure: async () => ({ allocatedBytes: 100_000_000_000, freeBytes: 500_000_000_000, ceilingBytes: 100_000_000_000 }) }, "storage_waiting_space");
  assert.equal((await w.live.canonical.command({ type: "storage.reservations" })).reservations, 0);
  // Locked stream: a live assistant stream is unsettled; the graph refuses rather than guessing.
  const unsettled = recoveryOf({ ...w.live.native, sdk: { sessions: { ...w.live.native.sdk.sessions,
    export: input2 => w.live.native.sdk.sessions.export(input2).pipe(Effect.map(result => ({ ...result,
      messages: result.messages.map((m, i, all) => i === all.length - 1 && m.type === "assistant" ? { ...m, time: { created: m.time.created } } : m) }))) } } });
  await rejectsWith(unsettled.snapshotAll(), "recovery_graph_unsettled");
  await refused({ previewNative: async () => { await unsettled.snapshotAll(); } }, "recovery_graph_unsettled");
  // Concurrent snapshot ownership is refused, not interleaved.
  const exclusive = recoveryOf(w.live.native), first = exclusive.snapshot([S.C1]);
  await rejectsWith(exclusive.snapshot([S.C1]), "recovery_graph_busy"); await first;
  // Engine death while snapshotting the live native store.
  let calls = 0;
  const dying = recoveryOf({ ...w.live.native, sdk: { sessions: { ...w.live.native.sdk.sessions,
    export: input2 => ++calls === 2 ? Effect.fail(new Error("synthetic_engine_death")) : w.live.native.sdk.sessions.export(input2) } } });
  await refused({ previewNative: async () => { await dying.snapshotAll(); } }, "synthetic_engine_death");
  assert.equal(w.events.length, 0);
  assert.equal(runtimes.reduce((n, r) => n + r.calls(), 0), 0);
});

test("engine death mid-candidate-build and an incomplete snapshot discard the hidden candidate, keep the old selector, preserve debt", async t => {
  for (const failure of ["engine-death", "incomplete-snapshot"]) {
    const w = await world(t), input = await incomingOf(w), base = coordinatorOptions(w);
    const selector = readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8");
    const options = { ...base };
    if (failure === "engine-death") {
      options.mergeNative = async (id, incoming, eligible) => {
        const candidate = w.candidates.get(id); let imports = 0;
        const dying = { ...candidate.native, sdk: { sessions: { ...candidate.native.sdk.sessions,
          import: request => ++imports === 2 ? Effect.fail(new Error("synthetic_engine_death")) : candidate.native.sdk.sessions.import(request) } } };
        return (await recoveryOf(dying).importMerged(await scratchGraph(join(w.g1, "state/harness/opencode.sqlite")), incoming, s => eligible.has(String(s.info.id)))).mapping;
      };
    } else {
      options.current = { ...base.current, async snapshotClosed() { const closed = await base.current.snapshotClosed(); return { ...closed, observedMembers: closed.observedMembers.filter(m => m.role !== "native") }; } };
    }
    w.remote.resolve();
    await rejectsWith(createRecoveryCoordinator(options).prepare(input), failure === "engine-death" ? "synthetic_engine_death" : "recovery_generation_member_mismatch", failure);
    assert.equal(readFileSync(join(w.profile, BACKEND_SELECTOR), "utf8"), selector, failure);       // old owner retained
    assert.equal(resolveBackendSelection(w.profile).admission, "active", failure);
    assert.equal(existsSync(join(w.profile, "generations/g2")), failure === "engine-death", failure); // unconfirmed retirement retains debt
    assert.equal(w.candidates.size, failure === "engine-death" ? 1 : 0, failure);
    if (failure === "engine-death") {   // the real worker retained the discarded candidate as debt and refuses the selected generation
      assert.equal((await w.storage.retire("g2")).result, "retained_as_debt");
      await assert.rejects(w.storage.retire("g1"));
    }
    // Preserve originals and debt: the current generation's bytes are exactly the closed observation.
    assert.equal(readFileSync(join(w.g1, "originals/o1.bin"), "utf8"), "synthetic shared original");
    const reopened = new DatabaseSync(join(w.g1, "state/renulus.sqlite3"), { readOnly: true });
    // The reservation intent persists as uncertain debt/charge until the retained owner reconciles it.
    assert.equal(Object.keys(JSON.parse(reopened.prepare("SELECT value FROM preferences WHERE key='storage.reservations/1'").get().value).active).length, 1, failure);
    reopened.close();
    const resumed = await openCanonical(w.g1);
    try {
      await reconcileRecoveryReservations(resumed);
      const reconciled = await resumed.command({ type: "storage.reservations" });
      assert.equal(reconciled.reservations, 0, failure);
      assert.ok(reconciled.cleanupDebtBytes > 0, failure);
    } finally { await resumed.close(); }
  }
});
