// Dedicated callback fixture; no provider, ambient state or network imports.
import { runHarnessIpc } from "../../src/ipc.ts";

await runHarnessIpc(async (boot, domain) => {
  let calls = 0;
  let closed = false;
  const binding = { operation_id: "learning-1", attempt_id: "attempt-1",
    session_id: "native-session", input_id: "native-input", cancellation_id: "parent-cancel-1" };
  return {
    status: async () => ({ state: "ready", configurationId: "synthetic", calls, callbacks: domain.state() }),
    observe: async () => ({ session: { domain: await domain.request(binding,
      "synthetic.extract", { topic: "CKD" }) } }),
    submit: async () => { calls += 1; return { text: "Synthetic extraction result." }; },
    findSession: async operationId => ({ sessions: operationId === "unknown-run" ? []
      : Array.from({ length: operationId === "duplicate-run" ? 2 : 1 },
        () => ({ id: "recovered-native-session", operationId })) }),
    close: async () => { closed = true; return { state: "closed" }; },
    settled: async () => { if (!closed) throw new Error("not_closed"); },
  };
});
