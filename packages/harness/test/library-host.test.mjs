import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { test } from "node:test";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { openHarness } from "../src/host.ts";
import { scriptedModel } from "./scripted-model.ts";

test("native Library registration executes only the admitted internal tools", async () => {
  const root = path.join("C:/Renulus/scratch/oc-h02-h08/library-host", randomUUID());
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  const file = path.join(root, "state/harness/manifest.json");
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, JSON.stringify(manifest));
  const model = await scriptedModel("Synthetic cited CKD explanation [1].", false,
    { name: "renulus_library_retrieve", input: { query: "CKD", limit: 1 } });
  const calls = [];
  const passage = { id: "passage_" + "1".repeat(32), document_id: "doc_" + "2".repeat(32),
    document_revision: "rev_" + "3".repeat(32), text: "Synthetic educational CKD passage.", locators: [{ page: 1 }] };
  // Scripted domain callback, actual native SDK tool/continuation. Python
  // engine and authenticated IPC integration have separate acceptance.
  const library = {
    async resolve(context) { return { sessionId: context.sessionID, operationId: "learning", attemptId: "1",
      scope: { kind: "study" }, revisionIds: [passage.document_revision], policyRevision: 0, contextEpoch: 0, cancellationEpoch: 0 }; },
    async check() {},
    async execute(command, args) { calls.push({ command, args }); return { status: "ready", passages: [passage] }; },
    async recordDependencies() {},
  };
  let host;
  try {
    host = await openHarness({ root, profileId: manifest.profile_id, storeId: manifest.runtime_store.store_id,
      domainStoreId: manifest.domain_store.store_id, domainPath: manifest.domain_store.path, model, library });
    await host.activate("synthetic-configuration");
    const session = await host.createSession({ operationId: "learning", title: "Synthetic CKD" });
    await host.submit({ sessionId: session.id, operationId: "learning", attemptId: "1", text: "Explain CKD with a passage." });
    await host.wait(session.id);
    assert.deepEqual(calls, [{ command: "library.retrieve", args: { query: "CKD", limit: 1 } }]);
    const requests = await model.requests();
    assert.equal(requests.length, 2, "Tool continuation is a second dispatch");
    assert.deepEqual(requests[0].tools.map(tool => tool.name).sort(), ["renulus_library_citation", "renulus_library_retrieve"]);
    assert.match(JSON.stringify((await host.observe(session.id)).messages), /Synthetic cited CKD explanation/);
  } finally {
    await host?.close();
    await model.close();
  }
});
