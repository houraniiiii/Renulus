import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { DatabaseSync } from "node:sqlite";
import { openHarness } from "../src/host.ts";
import { scriptedModel } from "./scripted-model.ts";

const receiptRoot = "C:/Renulus/scratch/oc-h02-h08/activation";

test("validated native/domain stores activate and reopen without generation", async () => {
  const root = path.join(receiptRoot, randomUUID());
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-runtime",
    domainStoreId: "synthetic-domain", domainPath: "domain/renulus.sqlite3" };
  const file = path.join(root, "state/harness/manifest.json");
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.domain_store.store_id = options.domainStoreId;
  manifest.runtime_store.store_id = options.storeId;
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, JSON.stringify(manifest));
  await mkdir(path.join(root, "domain"), { recursive: true });
  const domain = new DatabaseSync(path.join(root, options.domainPath));
  // Independent fixture of the actual canonical Database's mandatory schema.
  domain.exec("PRAGMA user_version=2; CREATE TABLE migration_ledger(name TEXT PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL); CREATE TABLE preferences(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL); CREATE TABLE deletion_ledger(entity_type TEXT NOT NULL,entity_id TEXT NOT NULL,deleted_at TEXT NOT NULL,PRIMARY KEY(entity_type,entity_id)); CREATE TABLE learning_evidence(id TEXT PRIMARY KEY,kind TEXT NOT NULL,topic_id TEXT,entity_id TEXT,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);");
  domain.exec("CREATE TABLE harness_store_identity(singleton INTEGER PRIMARY KEY CHECK(singleton=1),profile_id TEXT NOT NULL,store_id TEXT NOT NULL,snapshot_generation INTEGER NOT NULL,cohort_source TEXT NOT NULL);");
  domain.prepare("INSERT INTO harness_store_identity VALUES(1,?,?,1,?)").run(options.profileId, options.domainStoreId, manifest.cohort_source);
  domain.close();
  const model = await scriptedModel("Unused synthetic answer");
  let host;
  try {
    host = await openHarness({ ...options, model });
    const activated = await host.activateStores();
    assert.equal(activated.state, "active");
    assert.equal(activated.domain_store.validation, "valid");
    assert.equal(activated.runtime_store.validation, "valid");
    assert.equal(await model.count(), 0);
    const selected = await readFile(file, "utf8");
    await host.close();
    host = await openHarness({ ...options, model });
    assert.equal((await host.activateStores()).state, "active");
    assert.equal(await readFile(file, "utf8"), selected);
    assert.equal(await model.count(), 0);
    await host.activate("synthetic-configuration");
    const idle = await host.createSession({ operationId: "validation-fence", title: "Synthetic renal physiology" });
    const damaged = new DatabaseSync(path.join(root, options.domainPath));
    damaged.prepare("UPDATE harness_store_identity SET store_id='different-store'").run();
    damaged.close();
    await assert.rejects(host.activateStores(), /harness_store_identity_mismatch/);
    assert.equal((await host.status()).state, "store_activation_failed");
    await assert.rejects(host.activate("synthetic-configuration"), /harness_policy_blocked/);
    await assert.rejects(host.submit({ sessionId: idle.id, operationId: "must-stay-blocked", attemptId: "1", text: "No generation." }), /harness_policy_blocked/);
    assert.equal(await model.count(), 0);
    const repaired = new DatabaseSync(path.join(root, options.domainPath));
    repaired.prepare("UPDATE harness_store_identity SET store_id=?").run(options.domainStoreId);
    repaired.close();
    assert.equal((await host.activateStores()).state, "active");
    assert.equal((await host.status()).state, "policy_blocked");
    await host.close();
    const replaced = new DatabaseSync(path.join(root, options.domainPath));
    replaced.prepare("UPDATE harness_store_identity SET store_id='different-store'").run();
    replaced.close();
    await assert.rejects(async () => {
      const incorrectlyOpened = await openHarness({ ...options, model });
      await incorrectlyOpened.close();
    }, /harness_store_identity_mismatch/);
    assert.equal(await model.count(), 0);
  } finally {
    await host?.close();
    await model.close();
  }
});
