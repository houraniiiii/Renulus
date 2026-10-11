// SPDX-License-Identifier: MIT
// Real IPC/pipes; synthetic transfer host, no model or network.
import { runHarnessIpc } from "../../src/ipc.ts";
import { existsSync } from "node:fs";
import { mkdir } from "node:fs/promises";
import path from "node:path";

async function nativeTransfer(boot) {
  const { Effect, Layer, Logger, ManagedRuntime, Stream } = await import("effect");
  const { AIError, InvalidRequestError, LLMClient } = await import("@opencode/ai");
  const { OpenCode, AbsolutePath } = await import("@opencode/sdk/effect");
  const { Config } = await import("@opencode/core/config");
  const { InstructionDiscovery } = await import("@opencode/core/instruction-discovery");
  const { llmClient } = await import("@opencode/core/effect/app-node-platform");
  const { Global } = await import("@opencode/util/global");
  const { createSessionTransfer } = await import("../../src/session-transfer.ts");
  const workspace = path.join(boot.root, "native-workspace");
  await mkdir(workspace, { recursive: true });
  let modelCalls = 0;
  const denied = () => {
    modelCalls++;
    return new AIError({ reason: new InvalidRequestError({ message: "Capacity proof forbids inference." }) });
  };
  const client = { stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()), compact: () => Effect.fail(denied()) };
  const content = JSON.stringify({ compaction: { auto: false }, agents: { title: { disabled: true } } });
  const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
    app: { name: "renulus-transfer-capacity-test", version: "1" }, database: { path: path.join(boot.root, "native.sqlite") },
    config: { directory: path.join(boot.root, "config"), project: false, content },
    models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false }, events: { persist: false },
  }, { overrides: [
    Global.node.replace(Global.layerWith(Object.fromEntries(
      ["home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos"].map(key => [key, path.join(boot.root, key)])))),
    Config.node.replace(Config.configured({ project: false, global: false, content })),
    InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
    llmClient.replace(Layer.succeed(LLMClient.Service, client)),
  ] })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
  const sdk = await runtime.runPromise(OpenCode.Service);
  const transfer = createSessionTransfer({ sdk, run: effect => runtime.runPromise(effect),
    scope: { profileId: boot.profile_id, storeId: boot.store_id, generation: boot.generation,
      location: { directory: AbsolutePath.make(workspace) } }, checkCurrent: () => {} });
  return { transfer, modelCalls: () => modelCalls, async close() {
    transfer.seal(); await transfer.settled(); await runtime.dispose();
  } };
}

await runHarnessIpc(async boot => {
  let stages = 0;
  let imports = 0;
  const parts = new Map();
  const native = boot.fixture_native ? await nativeTransfer(boot) : undefined;
  const write = process.stdout.write.bind(process.stdout);
  process.stdout.write = (bytes, callback) => {
    const frame = JSON.parse(bytes);
    const held = frame.kind === "reply" && (typeof boot.fixture_hold_state === "string" &&
      frame.result?.state === boot.fixture_hold_state || typeof boot.fixture_hold_operation === "string" &&
      frame.operation_id === boot.fixture_hold_operation);
    if (!held) return write(bytes, callback);
    if (boot.fixture_hold_after) {
      return write(bytes, error => {
        if (error) { callback?.(error); return; }
        const timer = setInterval(() => {
          if (existsSync(boot.fixture_gate_file)) { clearInterval(timer); callback?.(); }
        }, 2);
      });
    }
    const publish = () => write(bytes, callback);
    const timer = setInterval(() => {
      if (existsSync(boot.fixture_gate_file)) { clearInterval(timer); publish(); }
    }, 2);
    return true;
  };
  return {
    status: async () => ({ state: "ready", stages, imports, ...(native ? { modelCalls: native.modelCalls() } : {}) }),
    inspect: async () => ({ stages, imports }),
    observe: async () => ({ session: { id: "synthetic-read" }, messages: [], execution: "settled" }),
    createSession: async () => ({ id: "synthetic-retained-session" }),
    transferCommand: async (_frame, command, payload) => {
      if (native) {
        if (command === "session.import.stage") { stages++; return native.transfer.stage(_frame, payload); }
        if (command === "session.import") { imports++; return native.transfer.commit(_frame, payload); }
        if (command === "session.import.inspect") return native.transfer.inspect(_frame, payload);
        if (command === "operation.retire") return native.transfer.retire(_frame);
        throw new Error("unknown_command");
      }
      if (command === "session.import.stage") {
        stages++;
        parts.set(payload.partIndex, payload.chunk);
        return { state: "staged", sessionId: payload.sessionId, bundleDigest: payload.bundleDigest,
          receivedParts: parts.size, receivedBytes: [...parts.values()].reduce((n, s) => n + Buffer.byteLength(s), 0),
          complete: parts.size === payload.partCount,
          ...(boot.fixture_oversized_metadata ? { unsafe: "x".repeat(8192) } : {}) };
      }
      if (command === "operation.retire") return { state: "retired" };
      if (command === "session.import") imports++;
      return { state: imports ? "verified" : "absent", sessionId: payload.sessionId,
        bundleDigest: payload.bundleDigest, ...(imports ? { messageCount: 2 } : {}) };
    },
    close: async () => { await native?.close(); return { state: "closed" }; },
    settled: async () => {},
  };
});
