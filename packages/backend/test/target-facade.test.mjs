// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openTargetApplication } from "../src/host/target.ts";
import { loadMigrationInventory, previewStorage } from "../src/storage/index.ts";

test("TS sole-owner Effect facade renames/replays and exports Python-compatible populated records", {
  skip: !process.env.RENULUS_BACKEND_TEST_PYTHON, timeout: 60_000,
}, async () => {
  const repository = fileURLToPath(new URL("../../..", import.meta.url));
  const profile = await mkdtemp(path.join(tmpdir(), "renulus-bf00-ts-facade-"));
  const python = process.env.RENULUS_BACKEND_TEST_PYTHON;
  const fixture = spawnSync(python, ["-I", "-B", "-X", "utf8", "-c", `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/'runtime'))
from renulus.server import create_app
from renulus.learn.conversation_models import NewConversation
s=create_app(sys.argv[2]).state.services
thread=s.registry['conversations'].create(NewConversation(kind='learning',title='SYNTHETIC CKD study'),'synthetic-bf00-create')
print(json.dumps(thread))
`, repository, profile], { encoding: "utf8", windowsHide: true,
    env: { SystemRoot: process.env.SystemRoot, WINDIR: process.env.WINDIR, TEMP: profile, TMP: profile, PATH: path.dirname(python) } });
  assert.equal(fixture.status, 0, fixture.stderr);
  const thread = JSON.parse(fixture.stdout);
  const migrations = loadMigrationInventory(repository);
  const preview = await previewStorage({ databasePath: path.join(profile, "state/renulus.sqlite3"), migrations });
  assert.equal(preview.compatible, true);
  const selection = { contract: "renulus-storage-selector/1", isolation: "synthetic", profileId: "synthetic-ts-facade", generation: 1,
    authorityEpoch: 1, writer: "ts", state: "active", ownerId: "synthetic-ts-facade-owner", database: "state/renulus.sqlite3" };
  await writeFile(path.join(profile, ".renulus-synthetic-storage.json"), JSON.stringify({ contract: "renulus-synthetic-storage/1", profileId: selection.profileId }));
  await writeFile(path.join(profile, "state/storage-selector.json"), JSON.stringify(selection));
  const token = "synthetic-ts-facade-session";
  const app = await openTargetApplication({ profileRoot: profile, selection, migrations, expectedSchemaHash: preview.schemaHash, port: 0, token });
  const origin = `http://127.0.0.1:${app.port}`;
  const headers = { "x-renulus-token": token };
  try {
    assert.equal((await fetch(origin + "/api/v1/data/export")).status, 401);
    const rename = async () => {
      const response = await fetch(origin + "/api/v1/conversations/learning/" + thread.identity.id, {
        method: "PATCH", headers: { ...headers, "content-type": "application/json", "idempotency-key": "synthetic-target-rename" },
        body: JSON.stringify({ expected_revision: 1, title: "SYNTHETIC glomerular disease study" }) });
      assert.equal(response.status, 200);
      return response.json();
    };
    const first = await rename();
    assert.equal(first.revision, 2);
    assert.deepEqual(await rename(), first);
    const exported = await (await fetch(origin + "/api/v1/data/export", { headers })).json();
    assert.equal(exported.records.learn_threads[0].title, first.title);
    const shutdown = await fetch(origin + "/api/v1/runtime/shutdown", { method: "POST", headers });
    assert.deepEqual(await shutdown.json(), { state: "settled", api_version: 1 });
    await app.closed;
  } finally { await app.close(); }
  // The compiled artifact must locate the separately compiled SQLite worker,
  // with no TypeScript loader, Python server or developer PATH at runtime.
  const child = spawn(process.execPath, [path.join(repository, "packages/backend/dist/main.mjs"), "--target",
    "--profile", profile, "--source-root", repository, "--port", "0", "--schema-hash", preview.schemaHash], {
    windowsHide: true, stdio: ["ignore", "pipe", "pipe"], env: { SystemRoot: process.env.SystemRoot,
      WINDIR: process.env.WINDIR, PATH: path.dirname(process.execPath), RENULUS_SESSION_TOKEN: token },
  });
  const exited = once(child, "exit");
  const [readyBytes] = await once(child.stdout, "data");
  const ready = JSON.parse(String(readyBytes));
  assert.equal(ready.event, "ready");
  assert.equal(ready.writer, "ts");
  const compiled = `http://127.0.0.1:${ready.port}`;
  const exported = await (await fetch(compiled + "/api/v1/data/export", { headers })).json();
  assert.equal(exported.records.learn_threads[0].title, "SYNTHETIC glomerular disease study");
  const stopped = await fetch(compiled + "/api/v1/runtime/shutdown", { method: "POST", headers });
  assert.deepEqual(await stopped.json(), { state: "settled", api_version: 1 });
  assert.equal((await exited)[0], 0);
});
