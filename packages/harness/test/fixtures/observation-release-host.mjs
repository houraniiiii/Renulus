// Synthetic execution host; actual IPC/Node pipes, no SDK, credentials or network.
import { runHarnessIpc } from "../../src/ipc.ts";
import { existsSync } from "node:fs";

await runHarnessIpc(async boot => {
  let reads = 0;
  let creates = 0;
  let dispatches = 0;
  let finishPrompt;
  let finishRead;
  let closed = false;
  // The controlled boundary is actual stdout publication, not IPC internals.
  const originalWrite = process.stdout.write.bind(process.stdout);
  let heldWrites = 0;
  process.stdout.write = (bytes, callback) => {
    const frame = JSON.parse(bytes);
    const target = frame.kind === "reply" && frame.operation_id === boot.fixture_hold_operation;
    const held = target && ++heldWrites === (boot.fixture_hold_write ?? 1);
    return originalWrite(bytes, error => {
      if (!held || error) { callback?.(error); return; }
      const timer = setInterval(() => {
        if (existsSync(boot.fixture_gate_file)) { clearInterval(timer); callback?.(); }
      }, 2);
    });
  };
  return {
    status: async () => ({ state: "ready", configurationId: "synthetic", reads, creates, dispatches,
      readHeld: !!finishRead }),
    inspect: async () => ({ registry_hash: "synthetic", dispatches }),
    observe: async sessionId => {
      reads += 1;
      if (sessionId === "uncertain") throw new Error("synthetic_read_fault");
      if (sessionId === "invalid-read") throw new Error("invalid_payload");
      if (sessionId === "held-read") {
        await new Promise(resolve => { finishRead = resolve; });
        finishRead = undefined;
      }
      return { session: { id: "native-session", reads,
        ...(sessionId === "oversized" ? { text: "x".repeat(5000) } : {}) },
        messages: [], execution: finishPrompt ? "active" : "settled" };
    },
    findSession: async () => ({ sessions: [] }),
    createSession: async () => ({ id: "native-session-" + ++creates }),
    submit: async () => {
      dispatches += 1;
      await new Promise(resolve => { finishPrompt = resolve; });
      finishPrompt = undefined;
      return { input_id: "native-input" };
    },
    cancel: async () => { finishPrompt?.(); finishRead?.(); return { state: "cancelled" }; },
    close: async () => { closed = true; finishPrompt?.(); finishRead?.(); return { state: "closed" }; },
    settled: async () => { if (!closed) throw new Error("not_closed"); },
  };
});
