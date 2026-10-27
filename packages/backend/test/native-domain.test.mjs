// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { createNativeDomainAdapter } from "../src/host/domain-adapter.ts";

const binding = { operation_id: "synthetic-operation", attempt_id: "synthetic-attempt", session_id: "synthetic-native",
  input_id: "synthetic-input", cancellation_id: "synthetic-cancellation" };

test("in-process native domain retains the existing bound callback client and waits through Stop settlement", async () => {
  let release;
  let observed;
  const entered = new Promise(resolve => { observed = resolve; });
  const adapter = createNativeDomainAdapter({ identity: { profile_id: "synthetic-profile", store_id: "synthetic-store", generation: "synthetic-generation" },
    handle: async request => {
      assert.deepEqual(request.binding, binding);
      assert.equal(request.command, "learning.check");
      observed(request.signal);
      await new Promise(resolve => { release = resolve; });
      return { outcome: "committed_reference", result: { current: true } };
    } });
  const controller = new AbortController();
  const call = adapter.domain.request(binding, "learning.check", {}, { signal: controller.signal });
  const signal = await entered;
  controller.abort();
  assert.equal(signal.aborted, true);
  assert.equal(adapter.domain.state().active, 1);
  let closed = false;
  const close = adapter.close().then(() => { closed = true; });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(closed, false);
  release();
  assert.equal((await call).outcome, "cancelled_settled");
  await close;
  assert.equal(adapter.domain.state().active, 0);
});
