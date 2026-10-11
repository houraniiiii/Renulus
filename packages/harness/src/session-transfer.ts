// SPDX-License-Identifier: MIT
import { createHash } from "node:crypto";
import { isDeepStrictEqual } from "node:util";
import { Schema, type Effect } from "effect";
import type { OpenCode } from "@opencode/sdk/effect";
import type { Location } from "@opencode/schema/location";
import { Session } from "@opencode/schema/session";
import { SessionMessage } from "@opencode/schema/session-message";

export interface TransferFrame {
  readonly profileId: string; readonly storeId: string; readonly generation: string;
  readonly operationId: string; readonly attemptId: string;
}
export interface ImportTarget { readonly sessionId: string; readonly bundleDigest: string }
export interface StagePayload extends ImportTarget {
  readonly partIndex: number; readonly partCount: number; readonly totalBytes: number; readonly chunk: string;
}
export type Json = null | boolean | number | string | readonly Json[] | { readonly [key: string]: Json };
export type LegacyOutcome = "completed" | "cancelled" | "failed" | "interrupted";
interface SavedMessageBase {
  readonly id: string; readonly content: string; readonly runId: string | null; readonly createdAt: string;
  readonly citations: readonly Json[];
}
export type SavedMessage = SavedMessageBase & (
  { readonly role: "user"; readonly completedAt?: never; readonly legacyOutcome?: never } |
  { readonly role: "assistant"; readonly completedAt: string; readonly legacyOutcome: LegacyOutcome });
export interface SavedBundle {
  readonly format: "renulus.saved-session/1"; readonly conversationId: string;
  readonly title: string | null; readonly messages: readonly SavedMessage[];
}
export interface StageResult extends ImportTarget {
  readonly state: "staged"; readonly receivedParts: number; readonly receivedBytes: number; readonly complete: boolean;
}
export interface VerifiedResult extends ImportTarget { readonly state: "verified"; readonly messageCount: number }
export type InspectResult = VerifiedResult | (ImportTarget & { readonly state: "absent" });
export interface RemoveResult { readonly state: "removed"; readonly sessionId: string }
export type RetireResult = { readonly state: "pending" | "retired" };
export type TransferCommand = "session.import.stage" | "session.import" | "session.import.inspect" |
  "session.remove" | "operation.retire";
export interface TransferOptions {
  readonly sdk: { readonly sessions: Pick<OpenCode.Interface["sessions"], "create" | "import" | "export" | "get" | "remove"> };
  readonly run: <A, E>(effect: Effect.Effect<A, E>) => Promise<A>;
  readonly scope: Readonly<{ profileId: string; storeId: string; generation: string; location: Location.Ref }>;
  readonly checkCurrent: (frame: TransferFrame, command: TransferCommand, target?: ImportTarget | { sessionId: string }) => void;
}
export interface SessionTransfer {
  stage(frame: TransferFrame, payload: StagePayload): StageResult;
  commit(frame: TransferFrame, target: ImportTarget): Promise<VerifiedResult>;
  inspect(frame: TransferFrame, target: ImportTarget): Promise<InspectResult>;
  remove(frame: TransferFrame, target: { sessionId: string }): Promise<RemoveResult>;
  retire(frame: TransferFrame): RetireResult;
  seal(): void;
  settled(): Promise<void>;
}
export class SessionTransferError extends Error {
  readonly code: string;
  constructor(code: string) { super(code); this.name = "SessionTransferError"; this.code = code; }
}
function fail(code: string): never { throw new SessionTransferError(code); }
export const SESSION_TRANSFER_LIMITS = Object.freeze({ maxBundleBytes: 8 * 1024 * 1024, maxMessages: 4096,
  maxParts: 256, maxPartBytes: 48 * 1024, maxStages: 4, maxStagedBytes: 16 * 1024 * 1024, maxRecords: 256 });
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const identifier = (value: unknown): value is string => typeof value === "string" &&
  value.length > 0 && value.length <= 256 && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value);
const utf8 = (text: string) => Buffer.from(text, "utf8").toString("utf8") === text;
function validTarget(value: unknown): value is ImportTarget {
  return object(value) && typeof value.sessionId === "string" && /^ses_[0-9a-f]{64}$/.test(value.sessionId) &&
    typeof value.bundleDigest === "string" && /^[0-9a-f]{64}$/.test(value.bundleDigest);
}
function validateStage(payload: unknown): asserts payload is StagePayload {
  if (!validTarget(payload) || Object.keys(payload).sort().join(",") !==
      "bundleDigest,chunk,partCount,partIndex,sessionId,totalBytes") fail("transfer_invalid_stage");
  const part = payload as StagePayload;
  if (!Number.isSafeInteger(part.partCount) || part.partCount < 1 || part.partCount > SESSION_TRANSFER_LIMITS.maxParts ||
      !Number.isSafeInteger(part.partIndex) || part.partIndex < 0 || part.partIndex >= part.partCount ||
      !Number.isSafeInteger(part.totalBytes) || part.totalBytes < 1 || part.totalBytes > SESSION_TRANSFER_LIMITS.maxBundleBytes ||
      typeof part.chunk !== "string" || !part.chunk || !utf8(part.chunk) ||
      Buffer.byteLength(JSON.stringify(part), "utf8") > SESSION_TRANSFER_LIMITS.maxPartBytes) fail("transfer_invalid_stage");
}
function timestamp(value: unknown): number | undefined {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?(?:Z|\+00:00)$/.test(value)) return;
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed) || new Date(parsed).toISOString().slice(0, 10) !== value.slice(0, 10)) return;
  return parsed;
}
function json(value: unknown): boolean {
  const pending = [value];
  while (pending.length) {
    const item = pending.pop();
    if (item === null || typeof item === "boolean") continue;
    if (typeof item === "string") { if (!utf8(item)) return false; continue; }
    if (typeof item === "number") { if (!Number.isFinite(item)) return false; continue; }
    if (Array.isArray(item)) { for (const entry of item) pending.push(entry); continue; }
    if (object(item)) { for (const entry of Object.values(item)) pending.push(entry); continue; }
    return false;
  }
  return true;
}
function decodeBundle(document: string): SavedBundle {
  let decoded: unknown;
  try { decoded = JSON.parse(document); } catch { return fail("transfer_invalid_bundle"); }
  if (!object(decoded) || Object.keys(decoded).sort().join(",") !== "conversationId,format,messages,title" ||
      decoded.format !== "renulus.saved-session/1" || !identifier(decoded.conversationId) ||
      !(decoded.title === null || typeof decoded.title === "string" && utf8(decoded.title)) ||
      !Array.isArray(decoded.messages) || decoded.messages.length > SESSION_TRANSFER_LIMITS.maxMessages) {
    return fail("transfer_invalid_bundle");
  }
  const ids = new Set<string>();
  for (const message of decoded.messages) {
    if (!object(message) || !identifier(message.id) || ids.has(message.id) ||
        typeof message.content !== "string" || !utf8(message.content) ||
        !(message.runId === null || identifier(message.runId)) ||
        !Array.isArray(message.citations) || !json(message.citations)) fail("transfer_invalid_bundle");
    const created = timestamp(message.createdAt);
    const completed = timestamp(message.completedAt);
    const keys = Object.keys(message).sort().join(",");
    if (created === undefined || (message.role === "user"
      ? keys !== "citations,content,createdAt,id,role,runId"
      : message.role !== "assistant" || keys !== "citations,completedAt,content,createdAt,id,legacyOutcome,role,runId" ||
        !["completed", "cancelled", "failed", "interrupted"].includes(message.legacyOutcome as string) ||
        completed === undefined || completed < created)) fail("transfer_invalid_bundle");
    ids.add(message.id);
  }
  return decoded as unknown as SavedBundle;
}
const sha = (text: string) => createHash("sha256").update(text, "utf8").digest("hex");
export function nativeSessionId(profileId: string, storeId: string, conversationId: string): string {
  return "ses_" + sha(JSON.stringify(["renulus-h06-session-v1", profileId, storeId, conversationId]));
}
export function nativeMessageId(sessionId: string, legacyId: string): string {
  return "msg_" + sha(JSON.stringify(["renulus-h06-message-v1", sessionId, legacyId]));
}
const missing = (error: unknown) => error !== null && typeof error === "object" &&
  "_tag" in error && error._tag === "Session.NotFoundError";
const encodeMessage = Schema.encodeSync(SessionMessage.Info);
const deniedPermissions = [{ action: "*", resource: "*", effect: "deny" }] as const;
interface ImportRecord {
  readonly kind: "import";
  readonly frame: TransferFrame; readonly target: ImportTarget; readonly partCount: number; readonly bytes: number;
  readonly parts: Map<number, string>; pending: number; receivedBytes: number; bundle?: SavedBundle; task?: Promise<VerifiedResult>;
  template?: { readonly id: Session.ID; readonly metadata: Session.Metadata; pending: boolean };
  cleanupTask?: Promise<void>;
  inspection?: Promise<InspectResult>;
}
interface RemoveRecord {
  readonly kind: "remove"; readonly frame: TransferFrame; readonly sessionId: string; pending: number; task?: Promise<RemoveResult>;
}
type OperationRecord = ImportRecord | RemoveRecord | { readonly kind: "retired" };

/** Only the embedding host supplies native scope, SDK lifetime and current admission. */
export function createSessionTransfer(options: TransferOptions): SessionTransfer {
  const { sdk, run, checkCurrent } = options;
  const scope = Object.freeze({ ...options.scope, location: Object.freeze({ ...options.scope.location }) });
  const records = new Map<string, OperationRecord>();
  const tasks = new Set<Promise<unknown>>();
  let sealed = false;
  function authenticate(frame: TransferFrame) {
    if (!object(frame) || Object.keys(frame).sort().join(",") !== "attemptId,generation,operationId,profileId,storeId" ||
        !Object.values(frame).every(identifier)) fail("transfer_invalid_frame");
    if (frame.profileId !== scope.profileId || frame.storeId !== scope.storeId ||
        frame.generation !== scope.generation) fail("transfer_scope_mismatch");
  }
  function terminal(frame: TransferFrame) {
    authenticate(frame);
    if (records.get(frame.operationId)?.kind === "retired") fail("transfer_retired");
  }
  function current(frame: TransferFrame, command: TransferCommand, target?: ImportTarget | { sessionId: string }) {
    authenticate(frame);
    if (sealed && command !== "operation.retire") fail("transfer_stopping");
    checkCurrent(Object.freeze({ ...frame }), command, target && Object.freeze({ ...target }));
  }
  function own<A>(record: ImportRecord | RemoveRecord, task: Promise<A>): Promise<A> {
    record.pending++;
    tasks.add(task);
    void task.finally(() => { record.pending--; tasks.delete(task); }).catch(() => {});
    return task;
  }
  async function native<A, E>(effect: Effect.Effect<A, E>): Promise<A> {
    try { return await run(effect); }
    catch (error) { if (missing(error)) throw error; return fail("transfer_native_failed"); }
  }
  function cleanupTemplate(record: ImportRecord): Promise<void> {
    if (record.cleanupTask) return record.cleanupTask;
    const template = record.template;
    if (!template?.pending) return Promise.resolve();
    const task = (async () => {
      let retained: Session.Info | undefined;
      try { retained = await native(sdk.sessions.get({ sessionID: template.id })); }
      catch (error) { if (!missing(error)) throw error; }
      if (!retained) { template.pending = false; return; }
      if (!isDeepStrictEqual(retained.metadata, template.metadata) ||
          retained.location.directory !== scope.location.directory || retained.parentID !== undefined ||
          !isDeepStrictEqual(retained.permissions, deniedPermissions)) fail("transfer_conflict");
      const exported = await native(sdk.sessions.export({ sessionID: template.id, sanitize: false }));
      if (exported.messages.length !== 0 || !isDeepStrictEqual(exported.info.metadata, template.metadata)) fail("transfer_conflict");
      try { await native(sdk.sessions.remove({ sessionID: template.id })); } catch {
        // Reconcile removal by exact readback even if the acknowledgement was lost.
      }
      try {
        await native(sdk.sessions.get({ sessionID: template.id }));
        fail("transfer_cleanup_pending");
      } catch (error) { if (!missing(error)) throw error; }
      template.pending = false;
    })();
    record.cleanupTask = own(record, task);
    void task.finally(() => { record.cleanupTask = undefined; }).catch(() => {});
    return task;
  }
  const source = (record: ImportRecord) => record.bundle ?? fail("transfer_stage_incomplete");
  const metadata = (record: ImportRecord): Session.Metadata => ({
    renulusProfile: record.frame.profileId, renulusStore: record.frame.storeId, operationId: record.frame.operationId,
    bundleDigest: record.target.bundleDigest, legacyConversationId: source(record).conversationId, lineage: "unknown",
  });
  function messages(record: ImportRecord): SessionMessage.Info[] {
    return source(record).messages.map(message => Schema.decodeUnknownSync(SessionMessage.Info)({
      id: nativeMessageId(record.target.sessionId, message.id), type: message.role,
      metadata: { lineage: "unknown", legacy: { id: message.id, runId: message.runId,
        createdAt: message.createdAt, citations: message.citations,
        ...(message.role === "user" ? {} : { completedAt: message.completedAt, outcome: message.legacyOutcome }) } },
      time: { created: Date.parse(message.createdAt),
        ...(message.role === "assistant" ? { completed: Date.parse(message.completedAt!) } : {}) },
      ...(message.role === "user" ? { text: message.content } : { agent: "legacy-import",
        model: { providerID: "legacy", id: "retained-answer" }, content: [{ type: "text", text: message.content }] }),
    }));
  }
  async function read(record: ImportRecord, command: "session.import" | "session.import.inspect" = "session.import"): Promise<VerifiedResult | undefined> {
    current(record.frame, command, record.target);
    const sessionID = Session.ID.make(record.target.sessionId);
    let info: Session.Info;
    try { info = await native(sdk.sessions.get({ sessionID })); }
    catch (error) { if (missing(error)) return undefined; throw error; }
    finally { current(record.frame, command, record.target); }
    function matches(info: Session.Info) {
      return info.id === sessionID && isDeepStrictEqual(info.metadata, metadata(record)) &&
        (info.title ?? null) === source(record).title && isDeepStrictEqual(info.permissions, deniedPermissions) &&
        info.location.directory === scope.location.directory &&
        info.location.workspaceID === scope.location.workspaceID && info.parentID === undefined &&
        info.fork === undefined && info.agent === undefined && info.model === undefined && info.revert === undefined;
    }
    if (!matches(info)) {
      fail("transfer_conflict");
    }
    let exported: { info: Session.Info; messages: readonly SessionMessage.Info[] };
    try { exported = await native(sdk.sessions.export({ sessionID, sanitize: false })); }
    finally { current(record.frame, command, record.target); }
    if (!matches(exported.info) ||
        !isDeepStrictEqual(exported.messages.map(message => encodeMessage(message)),
          messages(record).map(message => encodeMessage(message)))) {
      fail("transfer_conflict");
    }
    return { state: "verified", ...record.target, messageCount: source(record).messages.length };
  }
  async function commitRecord(record: ImportRecord): Promise<VerifiedResult> {
    const existing = await read(record);
    current(record.frame, "session.import", record.target);
    if (existing) return existing;
    const templateID = Session.ID.make("ses_" + sha(JSON.stringify(["renulus-h06-template-v1",
      record.frame.profileId, record.frame.storeId, record.frame.operationId, record.frame.attemptId])));
    const templateMetadata = { renulusProfile: record.frame.profileId, renulusStore: record.frame.storeId,
      operationId: record.frame.operationId, transferTemplate: true };
    record.template = { id: templateID, metadata: templateMetadata, pending: true };
    let template: Session.Info;
    try {
      template = await native(sdk.sessions.create({ id: templateID, location: scope.location,
        metadata: templateMetadata, permissions: [{ action: "*", resource: "*", effect: "deny" }] }));
      if (!isDeepStrictEqual(template.metadata, templateMetadata)) fail("transfer_conflict");
    } finally {
      await cleanupTemplate(record);
    }
    current(record.frame, "session.import", record.target);
    try {
      await native(sdk.sessions.import({ info: { ...template, id: Session.ID.make(record.target.sessionId),
        title: source(record).title ?? undefined, metadata: metadata(record) }, messages: messages(record),
        location: scope.location }));
    } catch {
      // Import is non-idempotent. Only exact readback can resolve an uncertain acknowledgement.
    }
    const verified = await read(record);
    current(record.frame, "session.import", record.target);
    return verified ?? fail("transfer_unconfirmed");
  }
  return {
    stage(frame: TransferFrame, payload: StagePayload): StageResult {
      terminal(frame);
      validateStage(payload);
      current(frame, "session.import.stage", { sessionId: payload.sessionId, bundleDigest: payload.bundleDigest });
      let record = records.get(frame.operationId);
      if (!record) {
        const stages = [...records.values()].filter((entry): entry is ImportRecord => entry.kind === "import");
        const stagedBytes = stages.reduce((total, entry) => total + entry.bytes, 0);
        if (stages.length >= SESSION_TRANSFER_LIMITS.maxStages || records.size >= SESSION_TRANSFER_LIMITS.maxRecords ||
            stagedBytes + payload.totalBytes > SESSION_TRANSFER_LIMITS.maxStagedBytes) fail("transfer_capacity");
        if (Buffer.byteLength(payload.chunk, "utf8") > payload.totalBytes) fail("transfer_invalid_stage");
        record = { kind: "import", frame: Object.freeze({ ...frame }), target: { sessionId: payload.sessionId, bundleDigest: payload.bundleDigest },
          partCount: payload.partCount, bytes: payload.totalBytes, parts: new Map(), receivedBytes: 0, pending: 0 };
        records.set(frame.operationId, record);
      }
      if (record.kind !== "import") fail("transfer_conflict");
      if (record.frame.attemptId !== frame.attemptId || record.target.sessionId !== payload.sessionId ||
          record.target.bundleDigest !== payload.bundleDigest || record.partCount !== payload.partCount ||
          record.bytes !== payload.totalBytes) fail("transfer_conflict");
      const prior = record.parts.get(payload.partIndex);
      if (prior === undefined) {
        if (record.receivedBytes + Buffer.byteLength(payload.chunk, "utf8") > record.bytes) fail("transfer_invalid_stage");
        record.parts.set(payload.partIndex, payload.chunk);
        record.receivedBytes += Buffer.byteLength(payload.chunk, "utf8");
      } else if (prior !== payload.chunk) fail("transfer_conflict");
      if (record.parts.size === record.partCount && !record.bundle) {
        const document = Array.from({ length: record.partCount }, (_, index) => record!.parts.get(index)).join("");
        if (sha(document) !== payload.bundleDigest || Buffer.byteLength(document, "utf8") !== record.bytes) {
          fail("transfer_digest_mismatch");
        }
        const decoded = decodeBundle(document);
        if (nativeSessionId(frame.profileId, frame.storeId, decoded.conversationId) !== payload.sessionId) fail("transfer_target_mismatch");
        record.bundle = decoded;
      }
      return { state: "staged", sessionId: payload.sessionId, bundleDigest: payload.bundleDigest,
        receivedParts: record.parts.size, receivedBytes: record.receivedBytes, complete: record.bundle !== undefined };
    },
    commit(frame: TransferFrame, target: ImportTarget): Promise<VerifiedResult> {
      terminal(frame);
      current(frame, "session.import", target);
      const record = records.get(frame.operationId) ?? fail("transfer_stage_incomplete");
      if (record.kind !== "import") fail("transfer_conflict");
      if (!isDeepStrictEqual(record.target, target) || record.frame.attemptId !== frame.attemptId) fail("transfer_conflict");
      source(record);
      if (!record.task) {
        record.task = own(record, commitRecord(record));
      }
      return record.task;
    },
    inspect(frame: TransferFrame, target: ImportTarget): Promise<InspectResult> {
      terminal(frame);
      current(frame, "session.import.inspect", target);
      const record = records.get(frame.operationId) ?? fail("transfer_stage_incomplete");
      if (record.kind !== "import") fail("transfer_conflict");
      if (!isDeepStrictEqual(record.target, target) || record.frame.attemptId !== frame.attemptId) fail("transfer_conflict");
      source(record);
      if (record.inspection) return record.inspection;
      const task = (async (): Promise<InspectResult> => {
        if (record.task) await record.task.catch(() => {});
        const verified = await read(record, "session.import.inspect");
        current(record.frame, "session.import.inspect", record.target);
        return verified ?? { state: "absent", ...record.target };
      })();
      record.inspection = own(record, task);
      void task.finally(() => { record.inspection = undefined; }).catch(() => {});
      return task;
    },
    remove(frame: TransferFrame, target: { sessionId: string }): Promise<RemoveResult> {
      terminal(frame);
      if (!object(target) || Object.keys(target).join(",") !== "sessionId" ||
          !identifier(target.sessionId) || !target.sessionId.startsWith("ses_")) fail("transfer_invalid_target");
      current(frame, "session.remove", target);
      let record = records.get(frame.operationId);
      if (!record) {
        if (records.size >= SESSION_TRANSFER_LIMITS.maxRecords) fail("transfer_capacity");
        record = { kind: "remove", frame: Object.freeze({ ...frame }), sessionId: target.sessionId, pending: 0 };
        records.set(frame.operationId, record);
      }
      if (record.kind !== "remove" || record.frame.attemptId !== frame.attemptId || record.sessionId !== target.sessionId) {
        fail("transfer_conflict");
      }
      if (!record.task) {
        const removal = record;
        const removalTarget = Object.freeze({ sessionId: removal.sessionId });
        record.task = (async (): Promise<RemoveResult> => {
          const sessionID = Session.ID.make(removal.sessionId);
          let info: Session.Info | undefined;
          try { info = await native(sdk.sessions.get({ sessionID })); }
          catch (error) { if (!missing(error)) throw error; }
          current(removal.frame, "session.remove", removalTarget);
          if (info) {
            if (info.metadata?.renulusProfile !== removal.frame.profileId || info.metadata?.renulusStore !== removal.frame.storeId) {
              fail("transfer_scope_mismatch");
            }
            try { await native(sdk.sessions.remove({ sessionID })); } catch {
              // A lost acknowledgement requires the exact missing-session readback below.
            }
            current(removal.frame, "session.remove", removalTarget);
            try { await native(sdk.sessions.get({ sessionID })); fail("transfer_unconfirmed"); }
            catch (error) { if (!missing(error)) throw error; }
            current(removal.frame, "session.remove", removalTarget);
          }
          return { state: "removed", sessionId: removal.sessionId };
        })();
        own(record, record.task);
      }
      return record.task;
    },
    retire(frame: TransferFrame): RetireResult {
      current(frame, "operation.retire");
      const record = records.get(frame.operationId);
      if (record?.kind === "retired") return { state: "retired" };
      if (record && record.frame.attemptId !== frame.attemptId) fail("transfer_conflict");
      if (record && (record.pending > 0 || record.kind === "import" && record.template?.pending)) return { state: "pending" };
      if (!record && records.size >= SESSION_TRANSFER_LIMITS.maxRecords) fail("transfer_capacity");
      // Retired keys contain neither payload bytes nor the erased payload digest.
      records.set(frame.operationId, { kind: "retired" });
      return { state: "retired" };
    },
    seal() { sealed = true; },
    async settled() {
      await Promise.allSettled([...tasks]);
      const cleanups = [...records.values()].filter((record): record is ImportRecord =>
        record.kind === "import" && record.template?.pending === true);
      const results = await Promise.allSettled(cleanups.map(cleanupTemplate));
      if (results.some(result => result.status === "rejected")) fail("transfer_cleanup_pending");
    },
  };
}
