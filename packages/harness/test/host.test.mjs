import "./owned-environment.mjs";
import assert from "node:assert/strict";
import { mkdtemp, rm, mkdir, readFile, writeFile, access, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";
import { DatabaseSync } from "node:sqlite";
import { setTimeout as delay } from "node:timers/promises";
import { openHarness } from "../src/host.ts";
import { scriptedModel } from "./scripted-model.ts";

async function profile(root, model) {
  const options = { root, profileId: "synthetic-profile", storeId: "synthetic-store", domainStoreId: "synthetic-domain-store", domainPath: "domain/renulus.sqlite3", model };
  const manifest = JSON.parse(await readFile(new URL("../../contracts/fixtures/harness/paired-store-prepared.json", import.meta.url), "utf8"));
  manifest.runtime_store.store_id = options.storeId;
  manifest.runtime_store.path = "state/harness/opencode.sqlite";
  await mkdir(path.join(root, "state", "harness"), { recursive: true });
  await writeFile(path.join(root, "state", "harness", "manifest.json"), JSON.stringify(manifest));
  return options;
}

test("a completed learning turn reopens with the same execution and no new inference", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Synthetic CKD learning answer.");
  const options = await profile(root, model);
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-policy-v1");
    const session = await host.createSession({ operationId: "create-1", title: "CKD learning" });
    const accepted = await host.submit({ sessionId: session.id, operationId: "explain-1", attemptId: "attempt-1", text: "Explain this synthetic CKD lesson." });
    await host.wait(session.id);
    const before = await host.observe(session.id);
    assert.equal(before.session.outcome, "succeeded");
    assert.equal(before.messages.filter(x => x.type === "assistant").at(-1).content[0].text, "Synthetic CKD learning answer.");
    assert.equal(await model.count(), 1);
    assert.equal(accepted.operationId, "explain-1");
    assert.equal(accepted.sessionId, session.id);
    assert.equal(before.messages.find(x => x.id === accepted.inputId).metadata.attemptId, "attempt-1");
    assert.equal((await host.close()).state, "closed");
    host = await openHarness(options);
    const after = await host.observe(session.id);
    assert.deepEqual(after, before);
    assert.deepEqual((await host.findSession("create-1")).sessions, [before.session]);
    assert.deepEqual((await host.findSession("unknown-operation")).sessions, []);
    assert.equal(await model.count(), 1);
  } finally {
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("bounded native transcript pages reach the latest result and survive reopen", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Answer 0");
  const options = await profile(root, model);
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-policy-v1");
    const session = await host.createSession({ operationId: "pages", title: "History" });
    for (let i = 0; i < 3; i++) {
      if (i) await model.respond(`Answer ${i}`);
      await host.submit({ sessionId: session.id, operationId: `turn-${i}`, attemptId: "1", text: `Lesson ${i}` });
      await host.wait(session.id);
    }
    const collect = async () => {
      const result = [];
      let cursor;
      do {
        const page = await host.observe(session.id, { limit: 2, ...(cursor ? { cursor } : { order: "asc" }) });
        assert.ok(page.messages.length <= 2);
        result.push(...page.messages);
        cursor = page.cursor.next;
      } while (cursor);
      return result;
    };
    const before = await collect();
    assert.equal(before.filter(x => x.type === "assistant").at(-1).content[0].text, "Answer 2");
    assert.equal(new Set(before.map(x => x.id)).size, before.length);
    await host.close();
    host = await openHarness(options);
    assert.deepEqual(await collect(), before);
    const newest = await host.observe(session.id, { limit: 1, order: "desc" });
    assert.equal(newest.messages[0].id, before.at(-1).id);
    assert.equal(await model.count(), 3);
  } finally {
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("a missing store below a junction is rejected before SDK schema writes", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const external = await mkdtemp(path.join(tmpdir(), "renulus-external-"));
  let unexpected;
  try {
    const options = await profile(root);
    await symlink(external, path.join(root, "domain"), "junction");
    await assert.rejects(async () => { unexpected = await openHarness(options); }, /harness_manifest_mismatch/);
    await assert.rejects(access(path.join(root, "state/harness/opencode.sqlite")));
  } finally {
    await unexpected?.close();
    for (const [directory, prefix] of [[root, "renulus-h01-"], [external, "renulus-external-"]]) {
      assert.equal(path.dirname(directory), path.resolve(tmpdir()));
      assert.ok(path.basename(directory).startsWith(prefix));
      await rm(directory, { recursive: true, force: true });
    }
  }
});

test("a retryable provider error cannot silently spend another inference attempt", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Initial answer");
  let host;
  try {
    host = await openHarness(await profile(root, model));
    await host.activate("synthetic-policy-v1");
    const session = await host.createSession({ operationId: "error-session", title: "Rate limit" });
    await host.submit({ sessionId: session.id, operationId: "first", attemptId: "1", text: "First lesson" });
    await host.wait(session.id);
    await model.failNext();
    await host.submit({ sessionId: session.id, operationId: "limited", attemptId: "1", text: "Next lesson" });
    await host.wait(session.id);
    assert.equal((await host.observe(session.id)).session.outcome, "failed");
    assert.equal(await model.count(), 2);
  } finally {
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("recovery cannot overtake an admitted session creation that has not settled", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Unused");
  let host;
  let creating;
  try {
    host = await openHarness(await profile(root, model));
    await host.activate("synthetic-policy-v1");
    creating = host.createSession({ operationId: "in-flight-create", title: "Fresh" });
    await assert.rejects(host.recover({ configurationId: "synthetic-policy-v1", sessionIds: [] }), /recovery_requires_quiescence/);
    const session = await creating;
    assert.equal((await host.observe(session.id)).session.id, session.id);
    assert.equal(await model.count(), 0);
  } finally {
    await creating;
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("cancel acknowledges settlement only after the native execution finalizes", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Cancelled answer", true);
  const options = await profile(root, model);
  let host;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-policy-v1");
    const session = await host.createSession({ operationId: "cancel-session", title: "Cancel" });
    await host.submit({ sessionId: session.id, operationId: "cancel-turn", attemptId: "1", text: "Synthetic request" });
    await model.started();
    const cancelled = host.cancel(session.id);
    assert.equal(await Promise.race([cancelled.then(() => "settled"), delay(25).then(() => "pending")]), "pending");
    assert.ok((await host.status()).activeSessionIds.includes(session.id));
    model.release();
    assert.deepEqual(await cancelled, { interrupted: true, outcome: "cancelled_settled" });
    assert.equal((await host.observe(session.id)).session.outcome, "interrupted");
    assert.deepEqual((await host.status()).activeSessionIds, []);
    assert.equal(await model.count(), 1);
  } finally {
    model.release();
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("uncertain work stays held while fresh work runs, and recovery requires quiescence", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Interrupted synthetic response", true);
  const options = await profile(root, model);
  let host;
  let releaseFresh = () => {};
  try {
    host = await openHarness(options);
    await host.activate("synthetic-policy-v1");
    const held = await host.createSession({ operationId: "held-session", title: "Interrupted" });
    await host.submit({ sessionId: held.id, operationId: "held-turn", attemptId: "1", text: "Synthetic learning" });
    await model.started();
    const closing = host.close({ timeoutMs: 10 });
    await closing;
    model.release();
    await host.settled();
    host = await openHarness(options);
    const before = await host.observe(held.id);
    await host.activate("synthetic-policy-v1");
    await delay(30);
    assert.deepEqual(await host.observe(held.id), before);
    assert.equal(await model.count(), 1);
    assert.deepEqual((await host.status()).heldSessionIds, [held.id]);
    await assert.rejects(host.submit({ sessionId: held.id, operationId: "repeat", attemptId: "2", text: "Do not resend" }), /recovery_required/);
    const fresh = await host.createSession({ operationId: "fresh", title: "Fresh" });
    releaseFresh = await model.holdNext("Fresh answer");
    await host.submit({ sessionId: fresh.id, operationId: "fresh-turn", attemptId: "1", text: "Another lesson" });
    await model.started(2);
    await assert.rejects(host.recover({ configurationId: "synthetic-policy-v1", sessionIds: [held.id] }), /recovery_requires_quiescence/);
    releaseFresh();
    await host.wait(fresh.id);
    assert.equal((await host.observe(fresh.id)).session.outcome, "succeeded");
    assert.deepEqual((await host.status()).heldSessionIds, [held.id]);
    await model.respond("Explicitly recovered answer");
    await host.recover({ configurationId: "synthetic-policy-v1", sessionIds: [held.id] });
    // The native recovery sweep schedules execution; its acknowledgement is not settlement.
    await model.started(3);
    await host.wait(held.id);
    assert.equal((await host.observe(held.id)).session.outcome, "succeeded");
    assert.equal(await model.count(), 3);
    assert.deepEqual((await host.status()).heldSessionIds, []);
  } finally {
    model.release(); releaseFresh();
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("a bounded close retains store ownership until uninterruptible external work settles", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Late synthetic answer", true);
  const options = await profile(root, model);
  let host;
  let unexpected;
  try {
    host = await openHarness(options);
    await host.activate("synthetic-policy-v1");
    const session = await host.createSession({ operationId: "create", title: "Held learning" });
    await host.submit({ sessionId: session.id, operationId: "held", attemptId: "1", text: "Synthetic request" });
    await model.started();
    const closed = await Promise.race([host.close({ timeoutMs: 25 }), delay(250).then(() => "observer-did-not-return")]);
    assert.deepEqual(closed, { state: "blocked", outcome: "uncertain_after_disconnect" });
    await assert.rejects(async () => { unexpected = await openHarness(options); }, /store_owned/);
    assert.equal(await model.count(), 1);
    model.release();
    assert.equal((await host.close({ timeoutMs: 5000 })).state, "closed");
  } finally {
    model.release();
    await unexpected?.close();
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("startup is observable before policy, and the real store cannot have a second owner", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const model = await scriptedModel("Unused");
  const options = await profile(root, model);
  let host;
  let unexpected;
  try {
    host = await openHarness(options);
    await assert.rejects(host.createSession({ operationId: "blocked", title: "Blocked" }), /harness_policy_blocked/);
    assert.equal(await model.count(), 0);
    await assert.rejects(async () => { unexpected = await openHarness(options); }, /store_owned/);
  } finally {
    await unexpected?.close();
    await host?.close();
    await model.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});

test("failed recovery inspection disposes the native host before releasing its lease", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  const options = await profile(root);
  let host;
  try {
    host = await openHarness(options);
    await host.close();
    host = undefined;
    const db = new DatabaseSync(path.join(root, "state/harness/opencode.sqlite"));
    try { db.exec('ALTER TABLE session_v2 RENAME COLUMN time_suspended TO synthetic_missing_claim'); }
    finally { db.close(); }
    await assert.rejects(async () => { host = await openHarness(options); }, /time_suspended/);
    await assert.rejects(access(path.join(root, "state/harness/owner.json")), { code: "ENOENT" });
    const repaired = new DatabaseSync(path.join(root, "state/harness/opencode.sqlite"));
    try { repaired.exec('ALTER TABLE session_v2 RENAME COLUMN synthetic_missing_claim TO time_suspended'); }
    finally { repaired.close(); }
    host = await openHarness(options);
    assert.equal((await host.status()).state, "policy_blocked");
  } finally {
    await host?.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    // Retain a failed owner for diagnosis; never remove a still-owned database.
    const owned = await access(path.join(root, "state/harness/owner.json")).then(() => true, () => false);
    if (!owned) await rm(root, { recursive: true, force: true });
  }
});

test("an incompatible paired manifest is rejected before a runtime database is created", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "renulus-h01-"));
  let unexpected;
  try {
    const options = await profile(root);
    await assert.rejects(async () => { unexpected = await openHarness({ ...options, storeId: "different-store" }); }, /harness_manifest_mismatch/);
    await assert.rejects(access(path.join(root, "state/harness/opencode.sqlite")));
  } finally {
    await unexpected?.close();
    assert.equal(path.dirname(root), path.resolve(tmpdir()));
    assert.ok(path.basename(root).startsWith("renulus-h01-"));
    await rm(root, { recursive: true, force: true });
  }
});
