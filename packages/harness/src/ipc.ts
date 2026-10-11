import path from "node:path";
import { createHash, timingSafeEqual } from "node:crypto";
import type { openHarness } from "./host.ts";
import { DomainClient } from "./domain-ipc.ts";

export interface HarnessBoot {
  protocol: "renulus-harness/1";
  profile_id: string;
  store_id: string;
  generation: string;
  token: string;
  root: string;
  domain_store_id: string;
  domain_path: string;
  ipc?: { max_result_records?: number; max_result_bytes?: number; max_frame_bytes?: number;
    max_inflight?: number; max_control_inflight?: number; max_domain_inflight?: number;
    max_domain_result_records?: number; max_domain_result_bytes?: number };
}

type Host = Awaited<ReturnType<typeof openHarness>>;
type Request = Record<string, unknown> & {
  operation_id: string; attempt_id: string; request_id: string;
  command: string; payload: Record<string, unknown>;
};
const identityKeys = ["protocol", "profile_id", "store_id", "generation", "token"] as const;
const controls = new Set(["host.status", "session.cancel"]);
type Lane = "data" | "control" | "close";
type RecordEntry = { lane: Lane; digest: string; size: number; overhead: number; pending: boolean; reply?: Buffer };
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const nonempty = (value: unknown): value is string => typeof value === "string" && value.length > 0;
const identifier = (value: unknown): value is string => typeof value === "string" &&
  value.length <= 256 && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.exec(value)?.[0] === value;

function bootConfiguration(): HarnessBoot {
  const boot: unknown = JSON.parse(process.env.RENULUS_HARNESS_BOOT ?? "null");
  if (!object(boot) || boot.protocol !== "renulus-harness/1" ||
      ![...identityKeys, "root", "domain_store_id", "domain_path"].every(key => nonempty(boot[key])) ||
      !["profile_id", "store_id", "generation", "domain_store_id"].every(key => identifier(boot[key])) ||
      (boot.token as string).length > 256 ||
      !path.isAbsolute(boot.root as string)) throw new Error("invalid_boot");
  if (boot.ipc !== undefined) {
    if (!object(boot.ipc)) throw new Error("invalid_boot_limits");
    for (const [key, minimum, maximum] of [
      ["max_result_records", 1, 256], ["max_result_bytes", 4096, 16_777_216],
      ["max_frame_bytes", 4096, 1_048_576],
      ["max_inflight", 1, 8], ["max_control_inflight", 1, 4],
      ["max_domain_inflight", 1, 8], ["max_domain_result_records", 1, 256],
      ["max_domain_result_bytes", 4096, 16_777_216],
    ] as const) {
      const value = boot.ipc[key];
      if (value !== undefined && (!Number.isSafeInteger(value) || (value as number) < minimum || (value as number) > maximum)) throw new Error("invalid_boot_limits");
    }
  }
  return boot as unknown as HarnessBoot;
}

function text(payload: Record<string, unknown>, key: string): string {
  if (!nonempty(payload[key])) throw new Error("invalid_payload");
  return payload[key];
}

function page(payload: Record<string, unknown>) {
  const { limit, order, cursor } = payload;
  if ((limit !== undefined && (typeof limit !== "number" || !Number.isInteger(limit) || limit < 1 || limit > 200)) ||
      (order !== undefined && order !== "asc" && order !== "desc") ||
      (cursor !== undefined && (!nonempty(cursor) || cursor.length > 2048 || order !== undefined))) {
    throw new Error("invalid_observation_page");
  }
  return { limit, order, cursor } as { limit?: number; order?: "asc" | "desc"; cursor?: string };
}

/** Owns one private pipe generation. Only the caller supplies an execution host. */
export async function runHarnessIpc(create: (boot: HarnessBoot, domain: DomainClient) => Promise<Host>): Promise<void> {
  const boot = bootConfiguration();
  const identity = Object.fromEntries(identityKeys.map(key => [key, boot[key]]));
  const records = new Map<string, RecordEntry>();
  const maxRecords = boot.ipc?.max_result_records ?? 256;
  const maxBytes = boot.ipc?.max_result_bytes ?? 16_777_216;
  const maxFrameBytes = boot.ipc?.max_frame_bytes ?? 1_048_576;
  const active = new Map<string, Promise<void>>();
  const writes = new Set<Promise<void>>();
  let closing = false;
  let accepting = true;
  let stopped = false;
  let settlement: Promise<void> | undefined;
  let draining: Promise<void> | undefined;
  let input = Buffer.alloc(0);
  let finish!: () => void;
  const done = new Promise<void>(resolve => { finish = resolve; });
  const write = (frame: object | Buffer) => {
    const bytes = Buffer.isBuffer(frame) ? frame : Buffer.from(JSON.stringify(frame) + "\n");
    const pending = new Promise<void>((resolve, reject) => {
      if (bytes.length > maxFrameBytes) { reject(new Error("reply_too_large")); return; }
      process.stdout.write(bytes, error => error ? reject(error) : resolve());
    });
    writes.add(pending);
    void pending.then(() => writes.delete(pending), () => { writes.delete(pending); process.exitCode = 1; });
    return pending;
  };
  const domain = new DomainClient(boot, bytes => write(bytes), {
    maxInflight: boot.ipc?.max_domain_inflight, maxRecords: boot.ipc?.max_domain_result_records,
    maxBytes: boot.ipc?.max_domain_result_bytes, maxFrameBytes,
  });
  const host = await create(boot, domain);
  const stop = () => {
    stopped = true;
    process.stdin.destroy();
    finish();
  };
  const settleHost = () => {
    closing = true;
    domain.seal();
    return settlement ??= (async () => {
      await host.close({ timeoutMs: 0 });
      await Promise.all([host.settled(), domain.settled()]);
    })();
  };
  const flush = async (except?: string) => {
    accepting = false;
    await Promise.allSettled([...active].filter(([id]) => id !== except).map(([, task]) => task));
    await Promise.allSettled([...writes]);
  };
  const drain = () => {
    if (stopped || draining) return;
    accepting = false;
    domain.disconnect();
    draining = (async () => {
      await settleHost();
      await flush();
      stop();
    })();
    // A failed native drain leaves ownership alive and uncertain; it never kills.
    void draining.catch(() => { process.exitCode = 1; });
  };
  const reply = (request: Request, outcome: string, body: object, retain = true) => {
    const envelope = {
      kind: "reply", ...identity, operation_id: request.operation_id,
      attempt_id: request.attempt_id, request_id: request.request_id,
    };
    let line = Buffer.from(JSON.stringify({ ...envelope, outcome, ...body }) + "\n");
    if (line.length > maxFrameBytes) {
      line = Buffer.from(JSON.stringify({ ...envelope, outcome: "uncertain_after_disconnect", error: { code: "reply_too_large" } }) + "\n");
    }
    const record = records.get(request.request_id);
    if (record && retain) record.reply = line;
    return write(line);
  };
  const dispatch = async (request: Request) => {
    try {
      if (closing && !["host.status", "host.close"].includes(request.command)) throw new Error("host_closing");
      let result: unknown;
      switch (request.command) {
        case "host.status":
          result = closing ? { state: "blocked", outcome: "uncertain_after_disconnect" } : await host.status(); break;
        case "host.inspect":
          if (Object.keys(request.payload).length) throw new Error("invalid_payload");
          result = await host.inspect(); break;
        case "host.activate":
          await host.activate(text(request.payload, "configuration_id"));
          result = await host.status(); break;
        case "host.stores.activate":
          if (Object.keys(request.payload).length) throw new Error("invalid_payload");
          result = await host.activateStores(); break;
        case "host.recover":
          if (!Array.isArray(request.payload.session_ids) || !request.payload.session_ids.every(nonempty) ||
              new Set(request.payload.session_ids).size !== request.payload.session_ids.length) throw new Error("invalid_payload");
          await host.recover({ configurationId: text(request.payload, "configuration_id"), sessionIds: request.payload.session_ids });
          result = await host.status(); break;
        case "session.create":
          result = { session: await host.createSession({ operationId: request.operation_id, title: text(request.payload, "title") }) }; break;
        case "session.find": {
          if (Object.keys(request.payload).length) throw new Error("invalid_payload");
          const found = await host.findSession(request.operation_id);
          if (!Array.isArray(found.sessions) || found.sessions.length > 1) throw new Error("harness_session_identity_conflict");
          result = found; break;
        }
        case "session.prompt":
          if (text(request.payload, "configuration_id") !== (await host.status()).configurationId) throw new Error("configuration_mismatch");
          result = await host.submit({
            sessionId: text(request.payload, "session_id"), operationId: request.operation_id,
            attemptId: request.attempt_id, text: text(request.payload, "text"), images: request.payload.images,
          }); break;
        case "session.get": {
          const observed = await host.observe(text(request.payload, "session_id"));
          result = { session: observed.session, execution: observed.execution }; break;
        }
        case "session.messages": {
          const observed = await host.observe(text(request.payload, "session_id"), page(request.payload));
          result = { messages: observed.messages, cursor: observed.cursor }; break;
        }
        case "session.cancel":
          result = await host.cancel(text(request.payload, "session_id"));
          await reply(request, "cancelled_settled", { result }); return;
        case "host.close":
          await settleHost();
          await flush(request.request_id);
          await reply(request, "cancelled_settled", { result: { state: "closed" } });
          stop(); return;
        default: throw new Error("unknown_command");
      }
      await reply(request, "committed_reference", { result });
    } catch (error) {
      const code = error instanceof Error ? error.message : "host_error";
      const rejected = ["invalid_payload", "invalid_images", "invalid_observation_page", "unknown_command", "harness_policy_blocked", "host_closing", "harness_closing", "configuration_requires_new_generation", "configuration_mismatch", "recovery_required", "recovery_admission_mismatch", "recovery_admission_unavailable", "recovery_requires_quiescence",
        "store_activation_requires_quiescence", "harness_store_invalid", "harness_domain_schema_mismatch",
        "harness_store_schema_mismatch", "harness_runtime_schema_mismatch", "harness_store_identity_mismatch",
        "harness_manifest_mismatch", "harness_selection_changed", "harness_session_identity_conflict"].includes(code);
      await reply(request, rejected ? "rejected_before_admission" : "uncertain_after_disconnect", { error: { code: rejected ? code : "host_error" } });
    }
  };
  const receive = async (line: Buffer) => {
    let frame: unknown;
    try { frame = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(line)); }
    catch { drain(); return; }
    if (!object(frame) || !nonempty(frame.token)) return;
    const token = Buffer.from(frame.token);
    const expected = Buffer.from(boot.token);
    if (token.length !== expected.length || !timingSafeEqual(token, expected) ||
        !identityKeys.every(key => frame[key] === boot[key])) return;
    if (frame.kind === "domain_result") { domain.receive(frame); return; }
    if (frame.kind !== "request") return;
    if (!["operation_id", "attempt_id", "request_id"].every(key => identifier(frame[key])) ||
        !nonempty(frame.command) || !object(frame.payload)) return;
    const request = frame as Request;
    const digest = createHash("sha256").update(JSON.stringify([
      request.operation_id, request.attempt_id, request.command, request.payload,
    ])).digest("hex");
    const previous = records.get(request.request_id);
    if (previous) {
      if (previous.digest !== digest) {
        await reply(request, "rejected_before_admission", { error: { code: "request_id_conflict" } }, false);
      } else if (previous.reply) await write(previous.reply);
      else await reply(request, "accepted_pending", { result: { state: "pending" } }, false);
      return;
    }
    const lane = request.command === "host.close" ? "close" : controls.has(request.command) ? "control" : "data";
    const retained = [...records.values()].filter(record => record.lane === lane);
    const limit = lane === "close" ? 1 : lane === "data" ? (boot.ipc?.max_inflight ?? 8) : (boot.ipc?.max_control_inflight ?? 4);
    if (retained.filter(record => record.pending).length >= limit) {
      await reply(request, "rejected_before_admission", { error: { code: "overloaded" } }, false);
      return;
    }
    const overhead = Buffer.byteLength(JSON.stringify({ ...identity,
      operation_id: request.operation_id, attempt_id: request.attempt_id, request_id: request.request_id,
    })) + 256;
    const reservation = maxFrameBytes * 2 + overhead;
    if (retained.length >= (lane === "close" ? 1 : maxRecords) ||
        (lane !== "close" && retained.reduce((total, record) => total + record.size, 0) + reservation > maxBytes)) {
      await reply(request, "rejected_before_admission", { error: { code: "result_capacity" } }, false);
      return;
    }
    const record = { lane, digest, size: reservation, overhead, pending: true } as RecordEntry;
    records.set(request.request_id, record);
    const task = dispatch(request).catch(() => { drain(); }).finally(() => {
      record.pending = false;
      record.size = overhead + (record.reply?.length ?? 0);
      active.delete(request.request_id);
    });
    active.set(request.request_id, task);
  };
  process.stdout.on("error", drain);
  process.stdin.on("error", drain);
  process.stdin.on("end", drain);
  const read = async () => {
    for await (const chunk of process.stdin) {
      if (!accepting || stopped) return;
      let offset = 0;
      while (offset < chunk.length && accepting && !stopped) {
        const newline = chunk.indexOf(10, offset);
        const end = newline < 0 ? chunk.length : newline + 1;
        if (input.length + end - offset > maxFrameBytes) { drain(); return; }
        input = Buffer.concat([input, chunk.subarray(offset, end)]);
        if (newline >= 0) { const line = input; input = Buffer.alloc(0); await receive(line); }
        offset = end;
      }
    }
  };
  try {
    await write({ kind: "ready", ...identity, state: (await host.status()).state });
    void read().catch(drain);
  } catch { drain(); }
  await done;
}
