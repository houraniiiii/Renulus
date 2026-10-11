import test from "node:test";
import assert from "node:assert/strict";

const identity = { protocol: "renulus-harness/1", profile_id: "profile", store_id: "runtime",
  generation: "process-generation", token: "synthetic-private-token" };
const binding = { operation_id: "operation", attempt_id: "attempt", session_id: "native-session",
  input_id: "native-input", cancellation_id: "parent-cancellation" };

function reply(request, body) {
  const { command, payload, kind, ...envelope } = request;
  return { ...envelope, kind: "domain_result", ...body };
}

test("reverse requests retain authenticated bindings and receive matching results", async () => {
  const { DomainClient } = await import("../src/domain-ipc.ts");
  const writes = [];
  const domain = new DomainClient(identity, async bytes => { writes.push(JSON.parse(bytes)); });
  const pending = domain.request(binding, "library.retrieve", { arguments: { query: "CKD" } });
  assert.equal(writes.length, 1);
  const request = writes[0];
  assert.equal(request.kind, "domain_request");
  assert.equal(request.input_id, "native-input");
  domain.receive(reply(request, { outcome: "committed_reference",
    result: { passages: [{ text: "Synthetic CKD passage." }] } }));
  const result = await pending;
  assert.deepEqual(result.result, { passages: [{ text: "Synthetic CKD passage." }] });
  assert.equal("token" in result, false);
  assert.deepEqual(domain.result(request.callback_id), result);
  assert.equal(domain.state().active, 0);
});

test("cancellation retains the callback until its final result and capacity stays bounded", async () => {
  const { DomainClient } = await import("../src/domain-ipc.ts");
  const writes = [];
  const domain = new DomainClient(identity, async bytes => { writes.push(JSON.parse(bytes)); },
    { maxInflight: 1, maxRecords: 1, maxBytes: 12000, maxFrameBytes: 4096 });
  const controller = new AbortController();
  const pending = domain.request(binding, "library.retrieve", { query: "CKD" }, { signal: controller.signal });
  const request = writes[0];
  const overloaded = await domain.request(binding, "library.citation", {});
  assert.equal(overloaded.error.code, "domain_overloaded");
  for (const key of ["profile_id", "store_id", "generation", "token", "callback_id", "operation_id",
    "attempt_id", "session_id", "input_id", "cancellation_id"]) {
    domain.receive(reply({ ...request, [key]: "stale-or-foreign" },
      { outcome: "committed_reference", result: { poisoned: true } }));
  }
  domain.receive(reply(request, { outcome: "made_up_success", result: {} }));
  domain.receive(reply(request, { outcome: "committed_reference", result: { numeric: Infinity } }));
  assert.equal(domain.state().active, 1);
  controller.abort();
  await Promise.resolve();
  assert.equal(writes[1].kind, "domain_cancel");
  assert.equal(domain.state().active, 1);
  let settled = false;
  const settlement = domain.settled().then(() => { settled = true; });
  await Promise.resolve();
  assert.equal(settled, false);
  domain.receive(reply(request, { outcome: "committed_reference", result: { late: "forbidden" } }));
  const result = await pending;
  assert.equal(result.outcome, "cancelled_settled");
  assert.equal("result" in result, false);
  await settlement;
  const noRoom = await domain.request(binding, "library.retrieve", {});
  assert.equal(noRoom.error.code, "domain_result_capacity");
  assert.equal(domain.state().retained, 1);
  assert.ok(domain.state().bytes <= 12000);
});
