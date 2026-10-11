import path from "node:path";
import { open, rename, readFile, unlink } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { DatabaseSync } from "node:sqlite";
import { migrations } from "@opencode/core/database/migration.gen";
import { SOURCE, verifyPreparedProfile, type ProfileSelection } from "./manifest.ts";

function storeIdentity(database: DatabaseSync, input: ProfileSelection, storeId: string, table: string) {
  const row = database.prepare(`SELECT profile_id,store_id,snapshot_generation,cohort_source FROM ${table} WHERE singleton=1`).get();
  if (!row || row.profile_id !== input.profileId || row.store_id !== storeId ||
      row.snapshot_generation !== 1 || row.cohort_source !== SOURCE) throw new Error("harness_store_identity_mismatch");
}

function bindRuntimeIdentity(input: ProfileSelection) {
  const database = new DatabaseSync(path.join(input.root, "state/harness/opencode.sqlite"));
  try {
    database.exec("BEGIN IMMEDIATE");
    database.exec("CREATE TABLE IF NOT EXISTS _renulus_store_identity(singleton INTEGER PRIMARY KEY CHECK(singleton=1),profile_id TEXT NOT NULL,store_id TEXT NOT NULL,snapshot_generation INTEGER NOT NULL,cohort_source TEXT NOT NULL)");
    database.prepare("INSERT OR IGNORE INTO _renulus_store_identity VALUES(1,?,?,1,?)").run(input.profileId, input.storeId, SOURCE);
    storeIdentity(database, input, input.storeId, "_renulus_store_identity");
    database.exec("COMMIT");
  } catch (error) { database.exec("ROLLBACK"); throw error; }
  finally { database.close(); }
}

/** Actual local validation; parsing the paired manifest alone proves no store. */
export function validateStores(input: ProfileSelection, requireRuntimeIdentity = true) {
  const check = (relative: string, required: Record<string, string[]>, version?: number) => {
    const database = new DatabaseSync(path.join(input.root, relative), { readOnly: true });
    try {
      const results = database.prepare("PRAGMA quick_check").all();
      if (results.length !== 1 || Object.values(results[0])[0] !== "ok" ||
          database.prepare("PRAGMA foreign_key_check").all().length) throw new Error("harness_store_invalid");
      if (version !== undefined && database.prepare("PRAGMA user_version").get()?.user_version !== version) {
        throw new Error("harness_domain_schema_mismatch");
      }
      for (const [table, expected] of Object.entries(required)) {
        const columns = new Set(database.prepare(`PRAGMA table_info(${table})`).all().map(row => row.name));
        if (expected.some(column => !columns.has(column))) throw new Error("harness_store_schema_mismatch");
      }
      if (version === undefined) {
        const applied = database.prepare("SELECT id FROM migration ORDER BY id").all().map(row => row.id);
        const expected = migrations.map(migration => migration.id).sort();
        if (JSON.stringify(applied) !== JSON.stringify(expected)) throw new Error("harness_runtime_schema_mismatch");
        if (requireRuntimeIdentity) storeIdentity(database, input, input.storeId, "_renulus_store_identity");
      } else {
        storeIdentity(database, input, input.domainStoreId, "harness_store_identity");
      }
    } finally { database.close(); }
  };
  check(input.domainPath, {
    migration_ledger: ["name", "checksum", "applied_at"],
    preferences: ["key", "value", "updated_at"],
    deletion_ledger: ["entity_type", "entity_id", "deleted_at"],
    learning_evidence: ["id", "kind", "entity_id", "payload_json"],
  }, 2);
  check("state/harness/opencode.sqlite", {
    migration: ["id", "time_completed"], session_v2: ["id", "metadata", "idle_outcome"],
    session_inbox: ["id", "session_id"], session_message: ["id", "session_id", "data"],
  });
}

/** The caller holds logical admission/writer leases, never a physical IPC lock. */
export async function activateStores(input: ProfileSelection) {
  const manifest = await verifyPreparedProfile(input);
  validateStores(input, manifest.state === "active");
  if (manifest.state === "active") return manifest;
  // The host owns this store and has sealed native/admitted writes. Underscore
  // tables are the pinned upstream's supported embedding namespace.
  bindRuntimeIdentity(input);
  const active = { ...manifest, state: "active",
    domain_store: { ...manifest.domain_store, validation: "valid" },
    runtime_store: { ...manifest.runtime_store, validation: "valid" } };
  const destination = path.join(input.root, "state/harness/manifest.json");
  const staged = path.join(path.dirname(destination), `.activation-${randomUUID()}.tmp`);
  const file = await open(staged, "wx");
  try {
    await file.writeFile(JSON.stringify(active, null, 2) + "\n");
    await file.sync();
  } finally { await file.close(); }
  try {
    // A staged file is never selected. Replace the complete selection last.
    const current = JSON.parse(await readFile(destination, "utf8"));
    if (!isDeepStrictEqual(current, manifest)) throw new Error("harness_selection_changed");
    await rename(staged, destination);
    return active;
  } finally { await unlink(staged).catch(error => { if (error.code !== "ENOENT") throw error; }); }
}
