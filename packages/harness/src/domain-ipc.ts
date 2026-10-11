import { createHash, randomUUID } from "node:crypto";

export interface DomainIdentity {
  protocol: "renulus-harness/1";
  profile_id: string;
  store_id: string;
  generation: string;
  token: string;
}
export interface DomainBinding {
  operation_id: string;
  attempt_id: string;
  session_id: string;
  input_id: string;
  cancellation_id: string;
}
export interface DomainOutcome extends DomainBinding, Omit<DomainIdentity, "token"> {
  kind: "domain_result";
  callback_id: string;
  outcome: "accepted_pending" | "rejected_before_admission" | "committed_reference" |
    "cancelled_settled" | "uncertain_after_disconnect";
  result?: Record<string, unknown>;
  error?: { code: string; status?: number; retryable?: boolean };
}
type Entry = { frame: DomainIdentity & DomainBinding & { callback_id: string };
  resolve: () => void; result?: Buffer; promise: Promise<void>;
  size: number; metadataSize: number; cancelled: boolean; digest: string; removeAbort?: () => void };
const bindingKeys = ["operation_id", "attempt_id", "session_id", "input_id", "cancellation_id"] as const;
const identityKeys = ["protocol", "profile_id", "store_id", "generation", "token"] as const;
const identifier = (value: unknown): value is string => typeof value === "string" &&
  value.length <= 256 && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.exec(value)?.[0] === value;
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const outcomes = new Set(["accepted_pending", "rejected_before_admission", "committed_reference",
  "cancelled_settled", "uncertain_after_disconnect"]);
function encode(value: unknown): Buffer {
  return Buffer.from(JSON.stringify(value, (_, item) => {
    if (["undefined", "function", "symbol", "bigint"].includes(typeof item) ||
        typeof item === "number" && !Number.isFinite(item) ||
        typeof item === "string" && /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(item)) throw new Error("domain_invalid_json");
    return item;
  }) + "\n");
}
export interface DomainLimits {
  maxInflight?: number;
  maxRecords?: number;
  maxBytes?: number;
  maxFrameBytes?: number;
}
export interface DomainRequestOptions { signal?: AbortSignal; callbackId?: string }

/** A private callback client; only the trusted host creates execution bindings. */
export class DomainClient {
  private readonly identity: DomainIdentity;
  private readonly write: (bytes: Buffer) => Promise<void>;
  private readonly records = new Map<string, Entry>();
  private readonly writes = new Set<Promise<void>>();
  private readonly limits: Required<DomainLimits>;
  private closing = false;
  private disconnected = false;

  constructor(identity: DomainIdentity, write: (bytes: Buffer) => Promise<void>, limits: DomainLimits = {}) {
    // Boot also carries owned filesystem paths and limits. Never echo those.
    this.identity = Object.fromEntries(identityKeys.map(key => [key, identity[key]])) as unknown as DomainIdentity;
    this.write = write;
    this.limits = { maxInflight: limits.maxInflight ?? 4, maxRecords: limits.maxRecords ?? 256,
      maxBytes: limits.maxBytes ?? 16_777_216, maxFrameBytes: limits.maxFrameBytes ?? 1_048_576 };
    if (Object.values(this.limits).some(value => !Number.isSafeInteger(value) || value < 1)) throw new Error("invalid_domain_limits");
  }

  request(binding: DomainBinding, command: string, payload: Readonly<Record<string, unknown>>,
    options: DomainRequestOptions = {}): Promise<DomainOutcome> {
    const frame = { ...binding, ...this.identity, callback_id: options.callbackId ?? randomUUID() };
    const rejected = (code: string) => Promise.resolve(this.outcome(frame, "rejected_before_admission", { error: { code } }));
    if (!object(binding) || Object.keys(binding).length !== bindingKeys.length ||
        !bindingKeys.every(key => identifier(binding[key])) || !identifier(frame.callback_id) ||
        !identifier(command) || !object(payload)) return rejected("domain_invalid_request");
    let bytes: Buffer;
    try { bytes = encode({ ...frame, kind: "domain_request", command, payload }); }
    catch { return rejected("domain_invalid_request"); }
    if (bytes.length > this.limits.maxFrameBytes) return rejected("domain_frame_too_large");
    const digest = createHash("sha256").update(bytes).digest("hex");
    const previous = this.records.get(frame.callback_id);
    if (previous) return previous.digest === digest
      ? previous.promise.then(() => this.result(frame.callback_id)!) : rejected("callback_id_conflict");
    if (this.closing || this.disconnected || options.signal?.aborted) return rejected(this.disconnected ? "domain_disconnected" : "domain_cancelled");
    if (this.state().active >= this.limits.maxInflight) return rejected("domain_overloaded");
    const metadataSize = encode(frame).length;
    const reservation = metadataSize + bytes.length + this.limits.maxFrameBytes;
    if (this.records.size >= this.limits.maxRecords || this.state().bytes + reservation > this.limits.maxBytes) return rejected("domain_result_capacity");
    let resolve!: () => void;
    const promise = new Promise<void>(done => { resolve = done; });
    const entry: Entry = { frame, resolve, promise, size: reservation, metadataSize, cancelled: false, digest };
    this.records.set(frame.callback_id, entry);
    if (options.signal) {
      const abort = () => this.cancel(entry);
      options.signal.addEventListener("abort", abort, { once: true });
      entry.removeAbort = () => options.signal!.removeEventListener("abort", abort);
    }
    this.send(bytes);
    return promise.then(() => this.result(frame.callback_id)!);
  }

  private outcome(frame: Entry["frame"], outcome: DomainOutcome["outcome"], body: Pick<DomainOutcome, "result" | "error">): DomainOutcome {
    const { token, ...identity } = frame;
    return { ...identity, kind: "domain_result", outcome, ...body };
  }

  private send(bytes: Buffer): void {
    let write: Promise<void>;
    try { write = this.write(bytes); } catch { this.disconnect(); return; }
    this.writes.add(write);
    void write.then(() => this.writes.delete(write), () => { this.writes.delete(write); this.disconnect(); });
  }

  private cancel(entry: Entry): void {
    if (entry.result || entry.cancelled) return;
    entry.cancelled = true;
    this.send(encode({ ...entry.frame, kind: "domain_cancel" }));
  }

  seal(): void {
    this.closing = true;
    for (const entry of this.records.values()) this.cancel(entry);
  }

  disconnect(): void {
    this.disconnected = true;
    this.closing = true;
    for (const entry of this.records.values()) {
      if (!entry.result) this.finish(entry, this.outcome(entry.frame, "uncertain_after_disconnect",
        { error: { code: "domain_disconnected" } }));
    }
  }

  async settled(): Promise<void> {
    await Promise.all([...this.records.values()].map(entry => entry.promise));
    await Promise.allSettled([...this.writes]);
  }

  private finish(entry: Entry, outcome: DomainOutcome): void {
    entry.removeAbort?.();
    entry.result = encode(outcome);
    entry.size = entry.metadataSize + entry.result.length;
    entry.resolve();
  }

  receive(frame: Record<string, unknown>): void {
    if (frame.kind !== "domain_result" || typeof frame.callback_id !== "string") return;
    const entry = this.records.get(frame.callback_id);
    if (!entry || entry.result || [...identityKeys, ...bindingKeys].some(key => frame[key] !== entry.frame[key])) return;
    if (Object.keys(frame).some(key => ![...identityKeys, ...bindingKeys, "callback_id", "kind", "outcome", "result", "error"].includes(key)) ||
        typeof frame.outcome !== "string" || !outcomes.has(frame.outcome) ||
        frame.error !== undefined && (!object(frame.error) || !identifier(frame.error.code) ||
          Object.keys(frame.error).some(key => !["code", "status", "retryable"].includes(key)) ||
          frame.error.status !== undefined && (!Number.isSafeInteger(frame.error.status) ||
            (frame.error.status as number) < 400 || (frame.error.status as number) > 599) ||
          frame.error.retryable !== undefined && typeof frame.error.retryable !== "boolean") ||
        frame.result !== undefined && !object(frame.result)) return;
    try { if (encode(frame).length > this.limits.maxFrameBytes) return; } catch { return; }
    if (frame.outcome === "accepted_pending") return;
    if ((frame.result === undefined) === (frame.error === undefined)) return;
    const { token, ...result } = frame;
    this.finish(entry, entry.cancelled
      ? this.outcome(entry.frame, "cancelled_settled", { error: { code: "domain_cancelled" } })
      : result as unknown as DomainOutcome);
  }

  result(callbackId: string): DomainOutcome | undefined {
    const value = this.records.get(callbackId)?.result;
    return value ? JSON.parse(value.toString("utf8")) as DomainOutcome : undefined;
  }

  state() {
    return { active: [...this.records.values()].filter(entry => !entry.result).length,
      retained: this.records.size, bytes: [...this.records.values()].reduce((sum, entry) => sum + entry.size, 0),
      accepting: !this.closing && !this.disconnected };
  }
}
