// SPDX-License-Identifier: MIT
import { Context, Effect, Layer, Schema, Scope, Fiber } from "effect";
import { Job } from "@opencode/core/job";
import { PluginHooks } from "@opencode/core/plugin/hooks";
import { Bus } from "@opencode/core/bus";
import { Permission } from "@opencode/core/permission";
import { Session } from "@opencode/core/session";
import { SessionInbox } from "@opencode/core/session/inbox";
import { SessionExecution } from "@opencode/core/session/execution";
import { SessionMessage } from "@opencode/core/session/message";
import { SessionEvent } from "@opencode/core/session/event";
import { SubagentJob } from "@opencode/core/session/subagent-job";
import { SubagentCompletion } from "@opencode/core/session/subagent-completion";
import { createHash } from "node:crypto";
import { Tool } from "@opencode/schema/tool";
import type { Plugin } from "@opencode/plugin/effect/plugin";
import type { OpenCode } from "@opencode/sdk/effect";
import type { DomainBinding } from "./domain-ipc.ts";

export interface ChildAuthorityBridge {
  /** Correlate the actual assistant/tool call to its originally admitted root USER. */
  readonly resolveParent: (native: Pick<Tool.Context, "sessionID" | "messageID" | "id" | "agent">) => Readonly<DomainBinding>;
  readonly request: (binding: Readonly<DomainBinding>, command: string, payload: Readonly<Record<string, unknown>>) =>
    Effect.Effect<Record<string, unknown>, Tool.Error>;
  /** Synchronous host seal/generation/epoch guard; never performs an IPC request. */
  readonly localCurrent: (parent: Readonly<DomainBinding>, grantEpoch: number) => boolean;
  /** Register this allocated child USER in the host map before native prompt admission. */
  readonly bindInput: (child: Readonly<DomainBinding>) => void;
}
export interface ChildAuthorityBounds {
  readonly maxChildren: number; readonly maxInvocations: number;
  readonly maxDescriptionBytes: number; readonly maxPromptBytes: number; readonly maxReportBytes: number;
}
type Reservation = Readonly<{ reservation_id: string; operation_id: string; attempt_id: string;
  cancellation_id: string; grant_epoch: number }>;
type Entry = { readonly parent: Readonly<DomainBinding>; readonly grant: Reservation;
  session?: import("@opencode/core/session/schema").SessionSchema.ID;
  child?: Readonly<DomainBinding>; inputDigest?: string; reportID?: string; notificationID?: string;
  startedAt?: number; reportConsumed?: boolean; constructing: number };
type Owner = { parent?: Readonly<DomainBinding>; fiber?: Fiber.Fiber<unknown, unknown> };
type JobOwner = Owner & { id: string; started: boolean };
type StopTask = { parent?: Readonly<DomainBinding>; launched: boolean; settled: boolean; failed: boolean };
export interface ChildAuthorityStatus {
  readonly state: "open" | "sealed" | "closing" | "closed";
  readonly records: number; readonly invocations: number; readonly constructions: number; readonly jobs: number;
  readonly generations: number; readonly notifications: number; readonly controls: number; readonly owned: number;
  readonly settled: boolean; readonly cleanup_failed: boolean;
}
const Invocation = Context.Reference<Entry | undefined>("renulus/ChildInvocation", { defaultValue: () => undefined });
const exact = (value: unknown, keys: readonly string[]): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
const identifier = (value: unknown): value is string => typeof value === "string" &&
  /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(value);
const failure = (code: string) => new Tool.Error({ message: code });
const bindingKeys = ["operation_id", "attempt_id", "session_id", "input_id", "cancellation_id"] as const;
function frozenBinding(value: unknown): Readonly<DomainBinding> {
  if (!exact(value, bindingKeys) || !bindingKeys.every(key => identifier(value[key]))) throw failure("child_binding_invalid");
  return Object.freeze({ ...value }) as unknown as Readonly<DomainBinding>;
}
const familyKey = (binding: Readonly<DomainBinding>) => JSON.stringify(bindingKeys.map(key => binding[key]));
function reservation(value: unknown): Reservation {
  if (!exact(value, ["reservation_id", "operation_id", "attempt_id", "cancellation_id", "grant_epoch"]) ||
      !["reservation_id", "operation_id", "attempt_id", "cancellation_id"].every(key => identifier(value[key])) ||
      !Number.isSafeInteger(value.grant_epoch) || Number(value.grant_epoch) < 0) throw failure("child_invalid_response");
  return Object.freeze({ ...value }) as Reservation;
}

/**
 * Native H07 integration; canonical authority remains in the authenticated parent.
 * Install both plugin and overrides. Bounds include retained metadata for this
 * adapter generation. Keep native restart recovery closed: this module neither
 * rehydrates grants nor adopts reports across a root/generation. Canonical family
 * sealing precedes familyStop; its timeout observes retained cleanup, never
 * cancels it. Native settlement is independent of Domain/Registry/process proof.
 */
export function createChildAuthority(bridge: ChildAuthorityBridge, bounds: ChildAuthorityBounds) {
  if (!exact(bounds, ["maxChildren", "maxInvocations", "maxDescriptionBytes", "maxPromptBytes", "maxReportBytes"]) ||
      Object.values(bounds).some(value => !Number.isSafeInteger(value) || Number(value) < 1) ||
      !Number.isSafeInteger(bounds.maxChildren + 2 * bounds.maxInvocations + 1)) throw new Error("child_invalid_bounds");
  if (![bridge.resolveParent, bridge.request, bridge.localCurrent, bridge.bindInput].every(value => typeof value === "function"))
    throw new Error("child_bridge_invalid");
  bounds = Object.freeze({ ...bounds });
  bridge = Object.freeze({ ...bridge });
  const entries = new Map<string, Entry>();
  const children = new Map<string, Entry>();
  const notifications = new Map<string, Entry>();
  const notificationGenerations = new Set<string>();
  const observers = new Set<string>();
  const observerParents = new Map<string, Readonly<DomainBinding>>();
  const observerFibers = new Map<string, Fiber.Fiber<unknown, unknown>>();
  const invocationOwners = new Set<Owner>();
  const jobOwners = new Set<JobOwner>();
  const generationOwners = new Map<string, Owner>();
  const permissionServices = new Set<Permission.Interface>();
  const sealedFamilies = new Set<string>();
  const stopTasks = new Map<string, StopTask>();
  let ownerScope: Scope.Scope | undefined;
  let ownerContext: Context.Context<never> | undefined;
  let closing = false;
  let pendingChildren = 0;
  let sessions: Session.Interface | undefined;
  let jobs: Job.Interface | undefined;
  let execution: SessionExecution.Interface | undefined;
  let executionContext: Context.Context<never> | undefined;
  let inboxes: Pick<SessionInbox.Interface, "list"> | undefined;
  const local = (entry: Entry) => Effect.try({ try: () => {
    if (closing || sealedFamilies.has(familyKey(entry.parent)) || !bridge.localCurrent(entry.parent, entry.grant.grant_epoch))
      throw failure("child_authority_stale");
  }, catch: () => failure("child_authority_stale") });
  const check = (entry: Entry, stage: string, binding: Readonly<DomainBinding> = entry.parent) =>
    local(entry).pipe(Effect.andThen(bridge.request(binding, "child.check", { reservation_id: entry.grant.reservation_id, stage })),
      Effect.flatMap(value => exact(value, ["current", "grant_epoch"]) && value.current === true &&
        value.grant_epoch === entry.grant.grant_epoch ? local(entry) : Effect.fail(failure("child_authority_stale"))));
  const acknowledged = (binding: Readonly<DomainBinding>, command: string, payload: Readonly<Record<string, unknown>>, key: string) =>
    bridge.request(binding, command, payload).pipe(Effect.flatMap(value =>
      exact(value, [key]) && value[key] === true ? Effect.void : Effect.fail(failure("child_invalid_response"))));
  const report = (entry: Entry, output: string, notificationID: string | null) => Effect.gen(function* () {
    if (!entry.child || !entry.session || !jobs || !execution) return yield* failure("child_not_admitted");
    if (Buffer.byteLength(output) > bounds.maxReportBytes || /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(output))
      return yield* failure("child_report_too_large");
    yield* execution.awaitIdle(entry.session);
    yield* check(entry, notificationID === null ? "before_result" : "before_detached", entry.child);
    const info = yield* jobs.get(entry.session);
    if (!info || info.status !== "completed" || info.output !== output || (info.notificationID ?? null) !== notificationID)
      return yield* failure("child_job_identity_conflict");
    yield* acknowledged(entry.child, "child.observe_job", { reservation_id: entry.grant.reservation_id, job_id: info.id,
      started_at: info.started_at, notification_id: notificationID }, "observed");
    yield* local(entry);
    const result = yield* bridge.request(entry.child, "child.report", { reservation_id: entry.grant.reservation_id,
      notification_id: notificationID, report_digest: createHash("sha256").update(output).digest("hex"), output });
    if (!exact(result, ["report_id"]) || !identifier(result.report_id)) return yield* failure("child_invalid_response");
    entry.reportID = result.report_id;
    if (notificationID !== null) { entry.notificationID = notificationID; entry.startedAt = info.started_at; }
    yield* local(entry);
    if (notificationID === null) {
      yield* acknowledged(entry.parent, "child.consume_report", { report_id: entry.reportID }, "consumed");
      yield* local(entry);
    }
  });
  const work = (value: unknown) => {
    if (!exact(value, ["description", "prompt", "background"]) || typeof value.background !== "boolean" ||
        !["description", "prompt"].every(key => typeof value[key] === "string" && (value[key] as string).trim().length > 0 &&
          !/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/.test(value[key] as string)) ||
        Buffer.byteLength(value.description as string) > bounds.maxDescriptionBytes ||
        Buffer.byteLength(value.prompt as string) > bounds.maxPromptBytes) throw failure("child_invalid_work");
    return Object.freeze({ description: value.description as string, prompt: value.prompt as string, background: value.background });
  };
  const plugin: Plugin = { id: "renulus-evidence-review", effect: context => Effect.gen(function* () {
    yield* context.tool.hook("execute.before", event => event.tool !== "subagent" ? Effect.void :
      Effect.try({ try: () => { work(event.input); }, catch: () => failure("child_invalid_work") }));
    yield* context.tool.transform(editor => editor.update("subagent", tool => {
      const execute = tool.execute;
      tool.input = Schema.Struct({ description: Schema.String, prompt: Schema.String, background: Schema.Boolean });
      tool.description = "Ask the configured evidence-review child to examine bounded learning evidence. Supply only work.";
      tool.execute = (input, native) => Effect.suspend(() => {
        if (closing) return Effect.fail(failure("child_closed"));
        if (invocationOwners.size >= bounds.maxInvocations || entries.size + pendingChildren >= bounds.maxChildren) return Effect.fail(failure("child_capacity"));
        const owner: Owner = {};
        invocationOwners.add(owner); pendingChildren++;
        let reservationPending = true;
        return Effect.gen(function* () {
          owner.fiber = yield* Effect.fiber;
          const payload = yield* Effect.try({ try: () => work(input), catch: () => failure("child_invalid_work") });
          const parent = yield* Effect.try({ try: () => frozenBinding(bridge.resolveParent(native)), catch: () => failure("child_binding_invalid") });
          owner.parent = parent;
          if (sealedFamilies.has(familyKey(parent))) return yield* failure("child_closed");
          const grant = yield* bridge.request(parent, "child.prepare", { invocation: { message_id: native.messageID,
            tool_call_id: native.id }, work: payload }).pipe(Effect.flatMap(value =>
              Effect.try({ try: () => reservation(value), catch: () => failure("child_invalid_response") })));
          if (entries.has(grant.reservation_id)) return yield* failure("child_reservation_conflict");
          const entry: Entry = { parent, grant, constructing: 0 };
          entries.set(grant.reservation_id, entry);
          pendingChildren--; reservationPending = false;
          yield* local(entry);
          const result = yield* execute({ ...payload, agent: "evidence-review" }, native).pipe(Effect.provideService(Invocation, entry));
          const output = result.output as { sessionID?: unknown; status?: unknown; output?: unknown } | undefined;
          if (output?.status === "completed") {
            if (output.sessionID !== entry.session || typeof output.output !== "string") return yield* failure("child_invalid_result");
            yield* report(entry, output.output, null);
          } else if (output?.status === "running" && output.sessionID === entry.session)
            yield* check(entry, "before_result", entry.child);
          else return yield* failure("child_invalid_result");
          yield* local(entry);
          return result;
        }).pipe(Effect.scoped, Effect.ensuring(Effect.sync(() => {
          invocationOwners.delete(owner); if (reservationPending) pendingChildren--;
        })));
      });
    }));
  }) };
  const overrides: NonNullable<OpenCode.EmbedOptions["overrides"]> = [
    Bus.node.replace(Bus.node.mapLayer(nativeLayer => Layer.effect(Bus.Service, Effect.gen(function* () {
      const native = yield* Bus.Service;
      const publish: Bus.Interface["publish"] = (definition, data, options) => {
        const promoting = definition.type === SessionEvent.InboxDelivered.type;
        if (!promoting && definition.type !== SessionEvent.InboxEnqueued.type) return native.publish(definition, data, options);
        const delivery = data as { sessionID: string; inboxID: string; item?: SessionInbox.Item };
        return Effect.gen(function* () {
          const entry = notifications.get(delivery.inboxID);
          const child = children.get(delivery.sessionID);
          const pending = promoting && inboxes ? (yield* inboxes.list(Session.ID.make(delivery.sessionID))).find(item => item.id === delivery.inboxID) : delivery.item;
          const detached = entry !== undefined || pending?.type === "synthetic" && pending.payload.metadata?.source === "subagent";
          if (detached && !entry) return yield* Effect.die(failure("child_notification_unbound"));
          const guard = Effect.suspend(() => {
            if (entry && (entry.parent.session_id !== delivery.sessionID || entry.notificationID !== delivery.inboxID || promoting && !entry.reportConsumed))
              return Effect.die(failure("child_report_not_consumed"));
            if (child && child.child?.input_id !== delivery.inboxID) return Effect.die(failure("child_input_conflict"));
            return entry || child ? local((entry ?? child)!).pipe(Effect.orDie) : Effect.void;
          });
          yield* guard;
          // This synchronous guard runs after native projectors/any prior commit
          // hook, in their transaction. It performs no callback or remote work.
          return yield* native.publish(definition, data, { ...options, commit: seq =>
            (options?.commit ? options.commit(seq) : Effect.void).pipe(Effect.andThen(guard)) });
        });
      };
      return Bus.Service.of({ ...native, publish });
    })).pipe(Layer.provide(nativeLayer)))),
    PluginHooks.node.replace(PluginHooks.node.mapLayer(nativeLayer => Layer.effect(PluginHooks.Service, Effect.gen(function* () {
      const native = yield* PluginHooks.Service;
      // The native input-repair hook strips unknown keys and coerces booleans.
      // Reject raw child work before any hook can erase that authority evidence.
      const trigger = ((domain, name, event) => {
        const raw: unknown = event;
        const guard = domain === "tool" && name === "execute.before" && typeof raw === "object" && raw !== null &&
            "tool" in raw && raw.tool === "subagent" && "input" in raw ?
          Effect.try({ try: () => { work(raw.input); }, catch: () => failure("child_invalid_work") }) : Effect.void;
        return guard.pipe(Effect.andThen(native.trigger(domain, name, event)));
      }) as PluginHooks.Interface["trigger"];
      return PluginHooks.Service.of({ ...native, trigger });
    })).pipe(Layer.provide(nativeLayer)))),
    SessionExecution.node.replace(SessionExecution.node.mapLayer(nativeLayer => Layer.effect(SessionExecution.Service, Effect.gen(function* () {
      const native = yield* SessionExecution.Service; execution = native;
      const scope = yield* Scope.Scope;
      const context = executionContext = yield* Effect.context<never>();
      const track = (entry: Entry) => Effect.suspend(() => {
        if (!entry.session || generationOwners.has(entry.session)) return Effect.void;
        const id = entry.session;
        generationOwners.set(id, { parent: entry.parent });
        return native.awaitIdle(id).pipe(Effect.ensuring(Effect.sync(() => { generationOwners.delete(id); })),
          Effect.forkIn(scope, { startImmediately: true }), Effect.asVoid, Effect.setContext(context));
      });
      return SessionExecution.Service.of({ ...native, wake: sessionID => Effect.suspend(() => {
        const entry = children.get(sessionID);
        return entry ? local(entry).pipe(Effect.orDie, Effect.andThen(native.wake(sessionID)), Effect.andThen(track(entry))) : native.wake(sessionID);
      }), resume: sessionID => Effect.suspend(() => {
        const entry = children.get(sessionID);
        if (!entry) return native.resume(sessionID);
        return Effect.gen(function* () {
          yield* check(entry, "before_wake", entry.child).pipe(Effect.orDie);
          if (yield* native.isActive(sessionID)) {
            yield* track(entry);
            yield* native.awaitIdle(sessionID);
            yield* local(entry).pipe(Effect.orDie);
            return;
          }
          const owner: Owner = { parent: entry.parent };
          generationOwners.set(sessionID, owner);
          yield* native.resume(sessionID).pipe(Effect.ensuring(Effect.sync(() => {
            if (generationOwners.get(sessionID) === owner) generationOwners.delete(sessionID);
          })));
        });
      }) });
    })).pipe(Layer.provide(nativeLayer)))),
    Session.node.replace(Session.node.mapLayer(nativeLayer => Layer.effect(Session.Service, Effect.gen(function* () {
      const native = yield* Session.Service;
      const decorated = Session.Service.of({ ...native, create: input => Effect.gen(function* () {
        if (!input.parentID) return yield* native.create(input);
        const entry = yield* Invocation;
        if (!entry || entry.session || input.parentID !== entry.parent.session_id || input.agent !== "evidence-review")
          return yield* Effect.die(failure("child_construction_unbound"));
        entry.constructing++;
        return yield* Effect.gen(function* () {
          yield* check(entry, "before_create").pipe(Effect.orDie);
          // Allocate before native writes so cancellation cannot erase an in-flight child's identity.
          const id = Session.ID.create();
          entry.session = id; children.set(id, entry);
          const created = yield* native.create({ ...input, id });
          if (created.id !== id) return yield* Effect.die(failure("child_session_identity_conflict"));
          yield* local(entry).pipe(Effect.orDie);
          return created;
        }).pipe(Effect.ensuring(Effect.sync(() => { entry.constructing--; })));
      }), prompt: input => Effect.gen(function* () {
        const entry = children.get(input.sessionID);
        if (!entry) return yield* native.prompt(input);
        yield* check(entry, "before_prompt", entry.child).pipe(Effect.orDie);
        const digest = createHash("sha256").update(JSON.stringify({ text: input.text, files: input.files, agents: input.agents,
          skills: input.skills, metadata: input.metadata, delivery: input.delivery })).digest("hex");
        if (entry.inputDigest !== undefined && entry.inputDigest !== digest || input.id !== undefined && entry.child && input.id !== entry.child.input_id)
          return yield* Effect.die(failure("child_input_conflict"));
        const id = entry.child ? SessionMessage.ID.make(entry.child.input_id) : input.id ?? SessionMessage.ID.create();
        if (!entry.child) {
          entry.inputDigest = digest;
          entry.child = Object.freeze({ operation_id: entry.grant.operation_id, attempt_id: entry.grant.attempt_id,
            session_id: input.sessionID, input_id: id, cancellation_id: entry.grant.cancellation_id });
          bridge.bindInput(entry.child);
          yield* acknowledged(entry.child, "child.admit_input", { reservation_id: entry.grant.reservation_id }, "admitted").pipe(Effect.orDie);
        }
        yield* local(entry).pipe(Effect.orDie);
        return yield* native.prompt({ ...input, id });
      }), synthetic: input => Effect.suspend(() => {
        const entry = input.id ? notifications.get(input.id) : undefined;
        if (!entry && input.metadata?.source !== "subagent") return native.synthetic(input);
        if (!entry || input.sessionID !== entry.parent.session_id || input.metadata?.childID !== entry.session || input.resume !== false)
          return Effect.die(failure("child_notification_unbound"));
        return local(entry).pipe(Effect.orDie, Effect.andThen(native.synthetic({ ...input, delivery: "queue" })));
      }), steerInbox: input => Effect.suspend(() => {
        const entry = notifications.get(input.inboxID);
        if (!entry) return native.steerInbox(input);
        if (invocationOwners.size >= bounds.maxInvocations) return Effect.die(failure("child_capacity"));
        const owner: Owner = { parent: entry.parent };
        invocationOwners.add(owner);
        return Effect.gen(function* () {
          owner.fiber = yield* Effect.fiber;
          if (input.sessionID !== entry.parent.session_id || input.inboxID !== entry.notificationID || !entry.reportID || !jobs)
            return yield* Effect.die(failure("child_notification_unbound"));
          const pending = (yield* native.inbox(input.sessionID)).find(item => item.id === input.inboxID);
          const info = entry.session ? yield* jobs.get(entry.session) : undefined;
          if (!pending || pending.type !== "synthetic" || pending.payload.metadata?.source !== "subagent" ||
              pending.payload.metadata.childID !== entry.session || entry.startedAt === undefined ||
              info && (info.started_at !== entry.startedAt || info.notificationID !== input.inboxID || info.status !== "completed"))
            return yield* Effect.die(failure("child_notification_unbound"));
          yield* check(entry, "before_wake", entry.parent).pipe(Effect.orDie);
          if (!entry.reportConsumed) {
            yield* acknowledged(entry.parent, "child.consume_report", { report_id: entry.reportID }, "consumed").pipe(Effect.orDie);
            yield* local(entry).pipe(Effect.orDie);
            entry.reportConsumed = true;
          }
          yield* local(entry).pipe(Effect.orDie);
          return yield* native.steerInbox(input);
        }).pipe(Effect.ensuring(Effect.sync(() => { invocationOwners.delete(owner); })));
      }), switchAgent: input => children.has(input.sessionID) ? Effect.die(failure("child_switch_not_supported")) : native.switchAgent(input),
      switchModel: input => children.has(input.sessionID) ? Effect.die(failure("child_switch_not_supported")) : native.switchModel(input) });
      sessions = decorated;
      return decorated;
    })).pipe(Layer.provide(nativeLayer)))),
    SessionInbox.node.replace(SessionInbox.node.mapLayer(nativeLayer => Layer.effect(SessionInbox.Service, Effect.gen(function* () {
      const native = yield* SessionInbox.Service;
      inboxes = native;
      return SessionInbox.Service.of({ ...native, steer: input => Effect.suspend(() => {
        const entry = notifications.get(input.id);
        if (entry && (input.sessionID !== entry.parent.session_id || !entry.reportConsumed))
          return Effect.die(failure("child_report_not_consumed"));
        return entry ? local(entry).pipe(Effect.orDie, Effect.andThen(native.steer(input))) : native.steer(input);
      }), reconcile: request => Effect.suspend(() => {
        const child = children.get(request.sessionID);
        const entry = child ?? notifications.get(request.id);
        if (child && (request.type !== "user" || request.id !== child.child?.input_id)) return Effect.die(failure("child_input_conflict"));
        return entry ? local(entry).pipe(Effect.orDie, Effect.andThen(native.reconcile(request))) : native.reconcile(request);
      }), admit: request => Effect.suspend(() => {
        const child = children.get(request.sessionID);
        const entry = child ?? notifications.get(request.id);
        if (child && (request.item.type !== "user" || request.id !== child.child?.input_id)) return Effect.die(failure("child_input_conflict"));
        return entry ? local(entry).pipe(Effect.orDie, Effect.andThen(native.admit(request))) : native.admit(request);
      }) });
    })).pipe(Layer.provide(nativeLayer)))),
    SubagentJob.node.replace(SubagentJob.node.mapLayer(nativeLayer => Layer.effect(SubagentJob.Service, Effect.gen(function* () {
      const native = yield* SubagentJob.Service;
      const scope = yield* Scope.Scope;
      const context = yield* Effect.context<never>();
      const notify: SubagentJob.Interface["notify"] = (recovery, startedAt) => Effect.suspend(() => {
        const entry = children.get(recovery.childSessionID);
        const key = `${recovery.childSessionID}:${startedAt}`;
        if (!entry || entry.parent.session_id !== recovery.parentSessionID || !jobs || !sessions)
          return Effect.die(failure("child_notification_unbound"));
        if (notificationGenerations.has(key)) return Effect.void;
        notificationGenerations.add(key); observers.add(key); observerParents.set(key, entry.parent);
        const ownedJobs = jobs, ownedSessions = sessions;
        return Effect.gen(function* () {
          const started = yield* ownedJobs.get(recovery.childSessionID);
          if (!started || started.started_at !== startedAt || !started.notificationID) return;
          notifications.set(started.notificationID, entry);
          const info = (yield* ownedJobs.wait({ id: recovery.childSessionID })).info;
          if (!info || info.started_at !== startedAt || info.status !== "completed" || info.notificationID !== started.notificationID || typeof info.output !== "string") return;
          yield* report(entry, info.output, info.notificationID).pipe(Effect.orDie);
          notifications.set(info.notificationID, entry);
          yield* local(entry).pipe(Effect.orDie);
          yield* SubagentCompletion.deliver(ownedSessions, ownedJobs, { ...info, recovery, resume: false });
        }).pipe(Effect.ensuring(Effect.sync(() => { observers.delete(key); observerParents.delete(key); observerFibers.delete(key); })),
          Effect.forkIn(scope, { startImmediately: true }), Effect.tap(fiber => Effect.sync(() => {
            if (observers.has(key)) observerFibers.set(key, fiber);
          })), Effect.asVoid, Effect.setContext(context), Effect.uninterruptible);
      });
      return SubagentJob.Service.of({ ...native, notify, background: recovery => Effect.gen(function* () {
        if (!jobs) return yield* Effect.die(failure("child_not_admitted"));
        const info = yield* jobs.background(recovery.childSessionID);
        if (info) yield* notify(recovery, info.started_at);
      }) });
    })).pipe(Layer.provide(nativeLayer)))),
    Permission.node.replace(Permission.node.mapLayer(nativeLayer => Layer.effect(Permission.Service, Effect.gen(function* () {
      const native = yield* Permission.Service;
      permissionServices.add(native);
      yield* Effect.addFinalizer(() => Effect.sync(() => { permissionServices.delete(native); }));
      return Permission.Service.of({ ...native, assert: input => Effect.gen(function* () {
        if (input.action !== "subagent") return yield* native.assert(input);
        const entry = yield* Invocation;
        const blocked = () => new Permission.BlockedError({ permission: input.action, resources: input.resources,
          rules: [], reason: "child_authority_stale" });
        if (!entry || input.sessionID !== entry.parent.session_id || input.resources.length !== 1 || input.resources[0] !== "evidence-review")
          return yield* blocked();
        yield* local(entry).pipe(Effect.mapError(blocked));
        yield* native.assert(input);
        yield* check(entry, "after_permission").pipe(Effect.mapError(blocked));
      }) });
    })).pipe(Layer.provide(nativeLayer)))),
    Job.node.replace(Job.node.mapLayer(nativeLayer => Layer.effect(Job.Service, Effect.gen(function* () {
      const native = yield* Job.Service;
      jobs = native;
      ownerScope = yield* Scope.Scope;
      ownerContext = yield* Effect.context<never>();
      return Job.Service.of({ ...native, start: input => Effect.suspend(() => {
        if (input.type !== "subagent") return native.start(input);
        if (closing || jobOwners.size >= bounds.maxChildren) return Effect.die(failure("child_job_capacity"));
        const entry = children.get(input.id);
        const owner: JobOwner = { id: input.id, started: false, parent: entry?.parent };
        jobOwners.add(owner);
        return (entry ? local(entry).pipe(Effect.orDie) : Effect.void).pipe(Effect.andThen(native.start({ ...input,
          run: Effect.suspend(() => { owner.started = true; return Effect.scoped(input.run); }).pipe(
            Effect.ensuring(Effect.sync(() => { jobOwners.delete(owner); }))) })),
          Effect.ensuring(Effect.sync(() => { if (!owner.started) jobOwners.delete(owner); })));
      }) });
    })).pipe(Layer.provide(nativeLayer)))),
  ];
  const matches = (owner: { parent?: Readonly<DomainBinding> }, parent?: Readonly<DomainBinding>) =>
    parent === undefined || owner.parent !== undefined && familyKey(owner.parent) === familyKey(parent);
  const status = (parent?: Readonly<DomainBinding>): ChildAuthorityStatus => {
    const bound = parent === undefined ? undefined : frozenBinding(parent);
    const records = [...entries.values()].filter(entry => matches(entry, bound));
    const invocations = [...invocationOwners].filter(owner => matches(owner, bound)).length;
    const constructions = records.reduce((count, entry) => count + entry.constructing, 0);
    const ownedJobs = [...jobOwners].filter(owner => matches(owner, bound)).length;
    const generations = [...generationOwners.values()].filter(owner => matches(owner, bound)).length;
    const notificationsOwned = [...observerParents.values()].filter(value => matches({ parent: value }, bound)).length;
    const tasks = [...stopTasks.values()].filter(task => matches(task, bound));
    const controls = tasks.filter(task => !task.settled).length;
    const owned = invocations + constructions + ownedJobs + generations + notificationsOwned + controls;
    const cleanupFailed = tasks.some(task => task.failed);
    return Object.freeze({ state: closing ? owned === 0 && !cleanupFailed ? "closed" : "closing" :
      bound && sealedFamilies.has(familyKey(bound)) ? "sealed" : "open",
      records: records.length, invocations, constructions, jobs: ownedJobs, generations, notifications: notificationsOwned,
      controls, owned, settled: owned === 0 && !cleanupFailed, cleanup_failed: cleanupFailed });
  };
  const settlement = (timeout: number, parent?: Readonly<DomainBinding>) => {
    if (!Number.isSafeInteger(timeout) || timeout < 0 || timeout > 60_000) throw failure("child_invalid_timeout");
    const bound = parent === undefined ? undefined : frozenBinding(parent);
    return Effect.gen(function* () {
      const waiting = Effect.gen(function* () {
        while (!status(bound).settled) yield* Effect.sleep(5);
      });
      yield* waiting.pipe(Effect.timeoutOption(timeout));
      return status(bound);
    });
  };
  const stop = (timeout: number, parent?: Readonly<DomainBinding>) => {
    if (!Number.isSafeInteger(timeout) || timeout < 0 || timeout > 60_000) throw failure("child_invalid_timeout");
    const bound = parent === undefined ? undefined : frozenBinding(parent);
    const key = bound ? familyKey(bound) : "all";
    if (bound && !stopTasks.has(key) && ![...entries.values(), ...invocationOwners].some(owner => matches(owner, bound)) &&
        [...stopTasks.values()].filter(task => task.parent && ![...entries.values(), ...invocationOwners].some(owner => matches(owner, task.parent))).length >= bounds.maxInvocations)
      throw failure("child_control_capacity");
    if (bound) sealedFamilies.add(key); else closing = true;
    let task = stopTasks.get(key);
    if (!task) { task = { parent: bound, launched: false, settled: false, failed: false }; stopTasks.set(key, task); }
    const ownedTask = task;
    const cleanup = Effect.gen(function* () {
      const interrupted = new Set<string>();
      // Every constructor is leased. Repeat after constructors settle to catch any ID allocated during Stop.
      do {
        const records = [...entries.values()].filter(entry => matches(entry, bound));
        const ids = new Set(records.flatMap(entry => entry.session ? [entry.session, Session.ID.make(entry.parent.session_id)] : [Session.ID.make(entry.parent.session_id)]));
        if (bound) ids.add(Session.ID.make(bound.session_id));
        for (const owner of invocationOwners) if (owner.parent && matches(owner, bound)) ids.add(Session.ID.make(owner.parent.session_id));
        if (execution) for (const id of ids) if (!interrupted.has(id)) {
          yield* execution.interrupt(id, { resume: false, reason: "user" }); interrupted.add(id);
        }
        // Reject actual approval waits before joining foreground invocations.
        for (const permission of permissionServices) for (const request of yield* permission.list())
          if (ids.has(request.sessionID)) yield* permission.reply({ requestID: request.id, reply: "reject" }).pipe(Effect.ignoreCause);
        const cancels: Effect.Effect<unknown>[] = [];
        if (jobs) for (const owner of jobOwners) if (matches(owner, bound)) cancels.push(jobs.cancel(owner.id));
        for (const owner of invocationOwners) if (owner.fiber && matches(owner, bound)) cancels.push(Fiber.interrupt(owner.fiber));
        for (const [key, fiber] of observerFibers) if (matches({ parent: observerParents.get(key) }, bound)) cancels.push(Fiber.interrupt(fiber));
        if (execution) for (const id of ids) cancels.push(execution.awaitIdle(id));
        yield* Effect.all(cancels, { concurrency: "unbounded", discard: true });
      } while ([...entries.values()].some(entry => matches(entry, bound) && entry.constructing > 0));
      // A native terminal marker is not proof: join our adopted resources and observers too.
      while ([...jobOwners, ...invocationOwners, ...generationOwners.values()].some(owner => matches(owner, bound)) ||
          [...observerParents.values()].some(parent => matches({ parent }, bound))) yield* Effect.sleep(5);
      if (sessions) for (const [id, entry] of notifications) if (matches(entry, bound)) {
        const sessionID = Session.ID.make(entry.parent.session_id), inboxID = SessionMessage.ID.make(id);
        // An interrupted observer can own a notification ID without admitting
        // an Inbox row. All possible producers have settled before this read.
        if ((yield* sessions.inbox(sessionID)).some(item => item.id === inboxID))
          yield* sessions.cancelInbox({ sessionID, inboxID }).pipe(Effect.orDie);
        if (jobs) yield* jobs.completeBackground(inboxID);
      }
    }).pipe(Effect.onExit(exit => Effect.sync(() => { ownedTask.failed = exit._tag === "Failure"; ownedTask.settled = true; })));
    return Effect.uninterruptibleMask(restore => Effect.gen(function* () {
      if (!ownedTask.launched) {
        ownedTask.launched = true;
        if (ownerScope && ownerContext) yield* cleanup.pipe(Effect.forkIn(ownerScope, { startImmediately: true }), Effect.setContext(ownerContext));
        else ownedTask.settled = true;
      }
      return yield* restore(settlement(timeout, bound));
    }));
  };
  return { plugin, overrides, status, settlement,
    native: () => ({ jobs: jobs!, execution: execution!, context: executionContext! }),
    familyStop: (parent: Readonly<DomainBinding>, timeout: number) => stop(timeout, parent),
    close: (timeout: number) => stop(timeout) };
}
