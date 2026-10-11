import "../owned-environment.mjs";
import assert from "node:assert/strict";
import { mock } from "node:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";
import path from "node:path";
import * as stores from "../../src/stores.ts";
import { scriptedModel } from "../scripted-model.ts";

// Controlled storage delay at the lower failure boundary; actual SDK,
// ownership lock, local SQLite validation and activation remain real.
let entered;
let release;
const started = new Promise(resolve => { entered = resolve; });
const gate = new Promise(resolve => { release = resolve; });
mock.module(new URL("../../src/stores.ts", import.meta.url), { exports: { ...stores,
  async activateStores(input) { entered(); await gate; return stores.activateStores(input); },
} });
const { openHarness } = await import("../../src/host.ts");
const root = path.join("C:/Renulus/scratch/oc-h02-h08/activation", randomUUID());
const options = { root, profileId: "synthetic-profile", storeId: "synthetic-runtime",
  domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3" };
const manifest = JSON.parse(await readFile(new URL("../../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
manifest.domain_store.store_id = options.domainStoreId;
manifest.runtime_store.store_id = options.storeId;
manifest.runtime_store.path = "state/harness/opencode.sqlite";
await mkdir(path.join(root, "state/harness"), { recursive: true });
await writeFile(path.join(root, "state/harness/manifest.json"), JSON.stringify(manifest));
await mkdir(path.join(root, "domain"), { recursive: true });
const db = new DatabaseSync(path.join(root, options.domainPath));
db.exec("PRAGMA user_version=2; CREATE TABLE migration_ledger(name TEXT PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL); CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL); CREATE TABLE deletion_ledger(entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,deleted_at TEXT NOT NULL,PRIMARY KEY(entity_type,entity_id)); CREATE TABLE learning_evidence(id TEXT PRIMARY KEY,kind TEXT NOT NULL,topic_id TEXT,entity_id TEXT,payload_json TEXT NOT NULL,created_at TEXT NOT NULL); CREATE TABLE harness_store_identity(singleton INTEGER PRIMARY KEY,profile_id TEXT NOT NULL,store_id TEXT NOT NULL,snapshot_generation INTEGER NOT NULL,cohort_source TEXT NOT NULL);");
db.prepare("INSERT INTO harness_store_identity VALUES(1,?,?,1,?)").run(options.profileId, options.domainStoreId, manifest.cohort_source);
db.close();
const model = await scriptedModel("Unused synthetic answer");
let host;
let activation;
try {
  host = await openHarness({ ...options, model });
  activation = host.activateStores();
  await started;
  assert.deepEqual(await host.close({ timeoutMs: 0 }), { state: "blocked", outcome: "uncertain_after_disconnect" });
  await assert.rejects(openHarness({ ...options, model }), /store_owned/);
  release();
  assert.equal((await activation).state, "active");
  await host.settled();
  assert.equal(await model.count(), 0);
} finally {
  release();
  await activation?.catch(() => {});
  await host?.close();
  await model.close();
  mock.restoreAll();
}
