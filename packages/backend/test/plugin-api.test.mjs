// SPDX-License-Identifier: MIT
import "../../harness/test/owned-environment.mjs";
import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { createCapabilityPluginHarness, CAPABILITY_COHORT } from "../../harness/src/capability-plugins.ts";
import { createPluginLifecycle } from "../src/plugins/lifecycle.ts";
import { canonical } from "../src/plugins/manifest.ts";
import { openTargetApplication } from "../src/host/target.ts";
import { loadMigrationInventory, previewStorage } from "../src/storage/index.ts";

test("authenticated target API adds, activates, edits, disables and removes real native plugins", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 120_000,
}, async () => {
  const repository = fileURLToPath(new URL("../../..", import.meta.url));
  const profile = await mkdtemp(path.join(tmpdir(), "renulus-bf01-plugin-api-"));
  const python = process.env.RENULUS_BACKEND_TEST_PYTHON;
  const fixture = spawnSync(python, ["-I", "-B", "-X", "utf8", "-c",
    "import sys;sys.path.insert(0,sys.argv[1]+'/runtime');from renulus.server import create_app;create_app(sys.argv[2])", repository, profile],
  { encoding: "utf8", windowsHide: true, env: { SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR,
    PATH: path.dirname(python), TEMP: profile, TMP: profile } });
  assert.equal(fixture.status, 0, fixture.stderr);
  const migrations = loadMigrationInventory(repository);
  const preview = await previewStorage({ databasePath: path.join(profile, "state/renulus.sqlite3"), migrations });
  assert.equal(preview.compatible, true);
  const selection = { contract: "renulus-storage-selector/1", isolation: "synthetic", profileId: "synthetic-plugin-api", generation: 1,
    authorityEpoch: 1, writer: "ts", state: "active", ownerId: "synthetic-plugin-owner", database: "state/renulus.sqlite3" };
  await writeFile(path.join(profile, ".renulus-synthetic-storage.json"), JSON.stringify({ contract: "renulus-synthetic-storage/1", profileId: selection.profileId }));
  await writeFile(path.join(profile, "state/storage-selector.json"), JSON.stringify(selection));
  const host = createCapabilityPluginHarness({ root: profile });
  const plugins = createPluginLifecycle({ root: profile, host, cohortSource: CAPABILITY_COHORT });
  const app = await openTargetApplication({ profileRoot: profile, selection, migrations, expectedSchemaHash: preview.schemaHash,
    port: 0, token: "synthetic-plugin-api-token", plugins, settlePlugins: async () => { await plugins.close(); await host.close(); } });
  const root = `http://127.0.0.1:${app.port}/api/v1/runtime/plugins`;
  const headers = { "x-renulus-token": "synthetic-plugin-api-token", "content-type": "application/json" };
  const hash = value => createHash("sha256").update(value).digest("hex");
  const schema = { type: "object", properties: {}, additionalProperties: false };
  async function install(version) {
    const bytes = `export default { id:'renulus-api-proof', effect:c=>c.tool.transform(e=>{e.add({name:'synthetic_api_proof',description:'Synthetic ${version}',input:${JSON.stringify(schema)},options:{codemode:false,permission:'synthetic.api'},execute:()=>{throw new Error('effect denied')}})}) };\n`;
    const manifest = { contract: "renulus-plugin/1", plugin_id: "synthetic.api", version, native_id: "renulus-api-proof",
      artifact_sha256: hash(bytes), cohort_source: CAPABILITY_COHORT, contract_schema: "renulus-capabilities/1", dependencies: [], migrations: [],
      tools: [{ name: "synthetic_api_proof", permission: "synthetic.api", input_schema_sha256: hash(canonical(schema)), output_schema_sha256: null }],
      prompts: [], skills: [], capabilities: ["synthetic.api"], endpoints: [], retention: "derived", resource_bounds: { max_tool_bytes: 4096 },
      license: "MIT", notices: [], derived_namespaces: ["synthetic.api"] };
    const directory = path.join(profile, "artifacts", manifest.plugin_id, version + "-" + manifest.artifact_sha256);
    await mkdir(directory, { recursive: true });
    await writeFile(path.join(directory, "server.js"), bytes);
    await writeFile(path.join(directory, "LICENSE"), "Synthetic MIT fixture.\n");
    return manifest;
  }
  async function command(action, body) {
    const response = await fetch(root + "/" + action, { method: "POST", headers, body: JSON.stringify(body) });
    const value = await response.json();
    assert.equal(response.status, 200, JSON.stringify(value));
    return value;
  }
  try {
    assert.equal((await fetch(root)).status, 401);
    assert.equal((await fetch(root + "/add", { method: "POST", headers, body: '{"manifest":{},"manifest":{}}' })).status, 422);
    await command("add", { manifest: await install("1.0.0") });
    const first = await command("activate", {});
    assert.equal(first.state, "ready");
    assert.equal(first.active[0].manifest.version, "1.0.0");
    await command("edit", { manifest: await install("1.1.0") });
    const edited = await command("activate", {});
    assert.equal(edited.active[0].manifest.version, "1.1.0");
    assert.notEqual(edited.registry_hash, first.registry_hash);
    await command("disable", { plugin_id: "synthetic.api" });
    assert.equal((await command("activate", {})).active[0].enabled, false);
    await command("remove", { plugin_id: "synthetic.api" });
    assert.deepEqual((await command("activate", {})).active, []);
  } finally { await app.close(); await plugins.close(); await host.close(); }
});
