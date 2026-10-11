// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { before, after, test } from "node:test";
import { nativeChildContractFixture } from "./fixtures/native-child-contract.ts";

let native: Awaited<ReturnType<typeof nativeChildContractFixture>>;
before(async () => { native = await nativeChildContractFixture(); });
after(async () => {
  if (!native) return;
  try { assert.deepEqual(await native.requests(), []); }
  finally { await native.close(); }
});

test("public native children inherit metadata and permission snapshots, with explicit overrides", { timeout: 20_000 }, async () => {
  const permissions = [{ action: "*", resource: "*", effect: "deny" as const },
    { action: "renulus.library", resource: "*", effect: "allow" as const }];
  const metadata = { operationId: "fixture-parent", cancellationEpoch: 4 };
  const parent = await native.createParent("Synthetic evidence review", metadata, permissions);
  const child = await native.run(native.sdk.sessions.create({ parentID: parent.id,
    title: "Synthetic child", agent: native.Agent.ID.make("reviewer") }));
  assert.equal(child.parentID, parent.id);
  assert.deepEqual(child.location, parent.location);
  assert.deepEqual(child.metadata, metadata);
  assert.deepEqual(child.permissions, permissions);
  // Generic create does not inherit the parent model. The native subagent tool chooses it.
  assert.equal(child.model, undefined);

  const widened = [{ action: "*", resource: "*", effect: "allow" as const }];
  const override = await native.run(native.sdk.sessions.create({ parentID: parent.id,
    title: "Override probe", agent: native.Agent.ID.make("reviewer"),
    model: { id: native.Model.ID.make("override"), providerID: native.Provider.ID.make("synthetic") },
    metadata: { operationId: "fixture-override" }, permissions: widened }));
  assert.deepEqual(override.permissions, widened);
  assert.deepEqual(override.metadata, { operationId: "fixture-override" });
  assert.equal(override.model?.id, "override");
  // This is record construction, not execution or proof that an override is authorised.
  const page = await native.run(native.sdk.sessions.list({ parentID: parent.id, limit: 10 }));
  assert.deepEqual(page.data.map(item => item.id).sort(), [child.id, override.id].sort());
  assert.deepEqual(await native.requests(), []);
});

test("changing the parent does not narrow a previously created native child snapshot", { timeout: 20_000 }, async () => {
  const parent = await native.createParent("Revocation snapshot probe", { cancellationEpoch: 1 },
    [{ action: "renulus.library", resource: "*", effect: "allow" }]);
  const child = await native.run(native.sdk.sessions.create({ parentID: parent.id,
    title: "Existing child", agent: native.Agent.ID.make("reviewer") }));
  await native.run(native.sdk.sessions.update({ sessionID: parent.id, metadata: { cancellationEpoch: 2 },
    permissions: [{ action: "*", resource: "*", effect: "deny" }] }));
  const currentParent = await native.run(native.sdk.sessions.get({ sessionID: parent.id }));
  const currentChild = await native.run(native.sdk.sessions.get({ sessionID: child.id }));
  assert.deepEqual(currentParent.metadata, { cancellationEpoch: 2 });
  assert.deepEqual(currentChild.metadata, { cancellationEpoch: 1 });
  assert.deepEqual(currentChild.permissions, child.permissions);
  assert.deepEqual(await native.requests(), []);
});

test("prompt hook sees actual child input and can pin host metadata; synthetic admission bypasses it", { timeout: 20_000 }, async () => {
  const parent = await native.createParent("Input identity probe", {}, [{ action: "*", resource: "*", effect: "deny" }]);
  const child = await native.run(native.sdk.sessions.create({ parentID: parent.id,
    title: "Parked child", agent: native.Agent.ID.make("reviewer") }));
  const id = native.SessionMessage.ID.create();
  native.pins.set(child.id, 7);
  const count = native.prompts.length;
  const receipt = await native.run(native.sdk.sessions.prompt({ sessionID: child.id, id,
    text: "Synthetic review input", resume: false, metadata: { fixtureParentEpoch: 999 } }));
  assert.deepEqual(native.prompts.slice(count), [{ sessionID: child.id, inputID: id, parentEpoch: 7 }]);
  assert.equal(receipt.id, id);
  assert.equal(receipt.payload.metadata?.fixtureParentEpoch, 7);
  assert.equal(receipt.payload.metadata?.fixtureInputID, id);
  const notification = await native.run(native.sdk.sessions.synthetic({ sessionID: parent.id,
    text: "Synthetic detached completion probe", resume: false, metadata: { source: "subagent", childID: child.id } }));
  assert.equal(notification.type, "synthetic");
  assert.equal(native.prompts.length, count + 1);
  assert.deepEqual(native.syntheticAdmissions.at(-1), { sessionID: parent.id, resume: false });
  assert.deepEqual(await native.requests(), []);
});

test("idle interrupt and wait never start parked child work; startup recovery is held", { timeout: 20_000 }, async () => {
  const parent = await native.createParent("Idle Stop API probe", {}, [{ action: "*", resource: "*", effect: "deny" }]);
  const child = await native.run(native.sdk.sessions.create({ parentID: parent.id,
    title: "Idle child", agent: native.Agent.ID.make("reviewer") }));
  await native.run(native.sdk.sessions.prompt({ sessionID: child.id, text: "Parked", resume: false }));
  assert.deepEqual(await native.run(native.sdk.sessions.interrupt({ sessionID: parent.id })), { interrupted: false });
  await native.run(native.sdk.sessions.wait({ sessionID: child.id }));
  assert.deepEqual(await native.requests(), []);
  assert.equal(native.recoveryEntered(), 1);
  // Idle APIs cannot prove active descendant cancellation or actual finalizer settlement.
});

async function permissionReplyProbe(guarded: boolean) {
  const parent = await native.createParent("Permission wait probe", {},
    [{ action: "*", resource: "*", effect: "deny" }, { action: "subagent", resource: "reviewer", effect: "ask" }]);
  native.pins.set(parent.id, 1);
  const id = native.Permission.ID.create();
  let earlyOutcome: unknown;
  native.permissionIntents.set(parent.id, { id, guarded });
  // Exported native assertion is the same primitive the built-in subagent awaits.
  // No tool or model is executed; public SDK methods observe/change/reply to the wait.
  const completion = native.run(native.sdk.sessions.command({ sessionID: parent.id, name: "fixture_permission_wait", text: "" }))
    .then(() => "allowed",
      error => { earlyOutcome = error; return error; });
  let pending = false;
  for (let read = 0; read < 100; read++) {
    const requests = await native.run(native.sdk.permission.list({ sessionID: parent.id }));
    if (requests.some(item => item.id === id)) { pending = true; break; }
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  assert.equal(pending, true, `Native assertion must actually be waiting for approval: ${JSON.stringify(native.permissionDiagnostics)}; ${String(earlyOutcome)}`);
  native.pins.set(parent.id, 2);
  await native.run(native.sdk.sessions.update({ sessionID: parent.id,
    permissions: [{ action: "*", resource: "*", effect: "deny" }] }));
  await native.run(native.sdk.permission.reply({ sessionID: parent.id, requestID: id, decision: "once" }));
  const outcome = await completion;
  assert.deepEqual(await native.requests(), []);
  return { outcome, allowedEffect: native.permissionEffects.includes(parent.id) };
}

test("original native approval releases its waiter after the parent rules changed", { timeout: 20_000 }, async () => {
  assert.deepEqual(await permissionReplyProbe(false), { outcome: "allowed", allowedEffect: true });
});

test("composed post-assert epoch check blocks the waiting effect after a stale approval", { timeout: 20_000 }, async () => {
  const { outcome, allowedEffect } = await permissionReplyProbe(true);
  assert.equal(allowedEffect, false);
  assert.match(String(outcome), /fixture_parent_revoked_after_approval/);
});
