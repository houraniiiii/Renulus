// Synthetic host over actual IPC/pipes; holds stdin at the public stream boundary.
import { existsSync } from "node:fs";
import { setTimeout as delay } from "node:timers/promises";
import { runHarnessIpc } from "../../src/ipc.ts";

const originalInput = process.stdin[Symbol.asyncIterator].bind(process.stdin);
let inputHeld = false;
let gate;
process.stdin[Symbol.asyncIterator] = async function* () {
  for await (const chunk of { [Symbol.asyncIterator]: originalInput }) {
    yield chunk;
    while (inputHeld && !existsSync(gate)) await delay(2);
  }
};

await runHarnessIpc(async boot => {
  gate = boot.fixture_gate_file;
  if (typeof gate !== "string") throw new Error("synthetic_gate_required");
  let reads = 0;
  let dispatches = 0;
  let finishPrompt;
  let closed = false;
  return {
    status: async () => ({ state: "ready", configurationId: "synthetic", reads, dispatches }),
    observe: async sessionId => {
      reads += 1;
      if (sessionId === "hold-stdin") inputHeld = true;
      return { session: { id: "native-session", reads, inputHeld },
        messages: [], execution: finishPrompt ? "active" : "settled" };
    },
    submit: async () => {
      dispatches += 1;
      await new Promise(resolve => { finishPrompt = resolve; });
      finishPrompt = undefined;
      return { input_id: "native-input" };
    },
    cancel: async () => { finishPrompt?.(); return { state: "cancelled" }; },
    close: async () => { closed = true; finishPrompt?.(); return { state: "closed" }; },
    settled: async () => { if (!closed) throw new Error("not_closed"); },
  };
});
