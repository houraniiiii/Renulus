import { Cause, Effect, Option, Stream } from "effect";
import { HttpClientResponse, type HttpClientRequest } from "effect/http";
import { AIError, AuthenticationError, RateLimitError, QuotaExceededError, ProviderInternalError, TransportError,
  InvalidRequestError, GenerationOptions, LLMRequest, type LLMClientShape } from "@opencode/ai";
import { Model } from "@opencode/schema/model";
import { Provider } from "@opencode/schema/provider";
import { SessionRunnerModel } from "@opencode/core/session/runner/model";
import type { StreamOptions } from "@opencode/ai/route/client";
import { DomainClient, type DomainBinding, type DomainOutcome } from "./domain-ipc.ts";
import { createSubscriptionAdapter, type InlineImage, type SubscriptionRoute } from "./provider-adapter.ts";

export interface SerializedSubscriptionHttp {
  readonly method: "POST";
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body_base64: string;
}
export interface TrustedGatewayPreparation {
  readonly dispatch_id: string;
  readonly binding: DomainBinding;
  readonly role: { readonly version: string; readonly purpose: string; readonly model_id: string;
    readonly output_tokens: number; readonly dispatch_limit: number };
  readonly request_kind: "primary" | "tool-continuation";
  readonly continuation_of?: string;
  readonly route: SubscriptionRoute;
  readonly native_capabilities: Model.Capabilities;
  readonly limits: { readonly input_tokens: number; readonly output_tokens: number; readonly window_tokens: number };
  readonly required_capabilities: readonly string[];
  readonly bounds: { readonly max_request_bytes: number; readonly max_response_bytes: number; readonly max_frame_bytes: number };
}
export interface GatewayReceipt { readonly dispatch_id: string; readonly permit_id: string }
export interface GatewayPrimaryPreparation {
  readonly resolved: SessionRunnerModel.Resolved;
  readonly prepare: (request: LLMRequest, settings: StreamOptions, unfiltered: LLMRequest) => Effect.Effect<LLMRequest, AIError>;
}
export interface GatewayAdapterOptions {
  readonly domain: DomainClient;
  readonly beforePrepare: (binding: DomainBinding) => Effect.Effect<TrustedGatewayPreparation, AIError>;
  readonly validateImages: (binding: DomainBinding, images: readonly InlineImage[]) => Effect.Effect<void, AIError>;
  /** Trusted parent builds/registers native pre-filter evidence; no model envelope authority. */
  readonly registerManifest?: (plan: Readonly<TrustedGatewayPreparation>, unfiltered: LLMRequest) => Effect.Effect<void, AIError>;
}
export interface GatewayAdapter {
  readonly client: LLMClientShape;
  prepare(binding: DomainBinding, request: LLMRequest, settings?: StreamOptions): Effect.Effect<LLMRequest, AIError>;
  preparePrimary(binding: DomainBinding, resolved: SessionRunnerModel.Resolved): Effect.Effect<GatewayPrimaryPreparation, AIError>;
  receipt(request: LLMRequest): Readonly<GatewayReceipt> | undefined;
  close(): Promise<void>;
}
const denied = () => new AIError({ reason: new InvalidRequestError({ message: "Trusted model gateway refused the request." }) });
const modelUnavailable = "The selected model or input is unavailable. Refresh its capabilities.";
function safeFailure(error: unknown): AIError {
  if (!(error instanceof AIError)) return denied();
  switch (error.reason._tag) {
    case "Authentication": return new AIError({ reason: new AuthenticationError({ message: "Reconnect the selected subscription." }) });
    case "RateLimit": return new AIError({ reason: new RateLimitError({ message: "The selected subscription reached a usage limit." }) });
    case "QuotaExceeded": return new AIError({ reason: new QuotaExceededError({ message: "The selected subscription reached its quota." }) });
    case "ProviderInternal": return new AIError({ reason: new ProviderInternalError({ message: "The selected subscription could not finish the request." }) });
    case "Transport": return new AIError({ reason: new TransportError({ message: "The selected subscription transport was interrupted.", transport: "http", operation: "request" }) });
    case "InvalidRequest": return error.reason.message === modelUnavailable
      ? new AIError({ reason: new InvalidRequestError({ message: modelUnavailable }) }) : denied();
    default: return denied();
  }
}
const bindingKeys = ["operation_id", "attempt_id", "session_id", "input_id", "cancellation_id"] as const;
const identifier = (value: unknown): value is string => typeof value === "string" &&
  /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(value);
const positive = (value: number) => Number.isSafeInteger(value) && value > 0;
function trustedPreparation(value: TrustedGatewayPreparation, binding: DomainBinding): TrustedGatewayPreparation {
  const plan = structuredClone(value);
  if (!identifier(plan.dispatch_id) || Object.keys(binding).length !== bindingKeys.length
      || Object.keys(plan.binding).length !== bindingKeys.length
      || !bindingKeys.every(key => identifier(binding[key]) && plan.binding[key] === binding[key])
      || !identifier(plan.role.version) || !identifier(plan.role.purpose)
      || plan.role.model_id !== plan.route.catalog_model_id || !positive(plan.role.dispatch_limit)
      || !positive(plan.role.output_tokens) || ![plan.limits.input_tokens, plan.limits.output_tokens, plan.limits.window_tokens].every(positive)
      || plan.role.output_tokens > plan.limits.output_tokens
      || plan.limits.output_tokens >= plan.limits.window_tokens || plan.limits.input_tokens > plan.limits.window_tokens
      || ![plan.bounds.max_request_bytes, plan.bounds.max_response_bytes, plan.bounds.max_frame_bytes].every(positive)
      || !["primary", "tool-continuation"].includes(plan.request_kind)
      || (plan.request_kind === "tool-continuation" ? !identifier(plan.continuation_of) : plan.continuation_of !== undefined)
      || typeof plan.native_capabilities.tools !== "boolean"
      || !Array.isArray(plan.native_capabilities.input) || !Array.isArray(plan.native_capabilities.output)
      || !plan.native_capabilities.input.every(identifier) || !plan.native_capabilities.output.every(identifier)
      || !plan.native_capabilities.input.includes("text") || !plan.native_capabilities.output.includes("text")
      || !plan.required_capabilities.every(identifier)) throw denied();
  Object.freeze(plan.binding); Object.freeze(plan.role); Object.freeze(plan.route);
  Object.freeze(plan.limits); Object.freeze(plan.bounds); Object.freeze(plan.required_capabilities);
  Object.freeze(plan.native_capabilities.input); Object.freeze(plan.native_capabilities.output);
  Object.freeze(plan.native_capabilities);
  return Object.freeze(plan);
}
type NativeAdapter = Awaited<ReturnType<typeof createSubscriptionAdapter>>;
type Entry = { adapter: NativeAdapter; plan: TrustedGatewayPreparation; bound: boolean; used: boolean;
  release?: () => void; receipt?: Readonly<GatewayReceipt>; failure?: AIError };
function requireInputs(request: LLMRequest, plan: TrustedGatewayPreparation) {
  if (!plan.native_capabilities.tools && (request.tools.length || request.messages.some(message =>
    message.content.some(part => part.type === "tool-call" || part.type === "tool-result")))) throw denied();
  if (!plan.native_capabilities.input.includes("image") && request.messages.some(message =>
    message.content.some(part => part.type === "media"))) throw denied();
}
/** Reuse the authenticated safe categories for preparation and final HTTP. */
export function gatewayDomainError(outcome: DomainOutcome): AIError {
  if (outcome.outcome === "rejected_before_admission" && outcome.result === undefined
      && outcome.error?.code === "authentication_required" && outcome.error.status === 401)
    return new AIError({ reason: new AuthenticationError({ message: "Reconnect the selected subscription." }) });
  if (outcome.outcome === "rejected_before_admission" && outcome.result === undefined
      && outcome.error?.code === "subscription_limit" && outcome.error.status === 429)
    return new AIError({ reason: new RateLimitError({ message: "The selected subscription reached a usage limit." }) });
  if (outcome.outcome === "rejected_before_admission" && outcome.result === undefined
      && outcome.error?.status === 409 && ["model_unavailable", "model_not_found", "model_access_denied",
        "account_model_unsupported", "unsupported_image_input", "image_input_not_supported",
        "unsupported_input_modality", "unsupported_modality"].includes(outcome.error.code))
    return new AIError({ reason: new InvalidRequestError({ message: modelUnavailable }) });
  if (outcome.outcome === "rejected_before_admission" && outcome.result === undefined && outcome.error?.status === 503) {
    if (["provider_stream_failed", "provider_unavailable"].includes(outcome.error.code))
      return new AIError({ reason: new ProviderInternalError({ message: "The selected subscription could not finish the request." }) });
    if (outcome.error.code === "transport_unavailable")
      return new AIError({ reason: new TransportError({ message: "The selected subscription transport was interrupted.", transport: "http", operation: "request" }) });
  }
  return denied();
}
function bufferedHttp(http: HttpClientRequest.HttpClientRequest, outcome: DomainOutcome, plan: TrustedGatewayPreparation) {
  if (Buffer.byteLength(JSON.stringify(outcome) + "\n") > plan.bounds.max_frame_bytes) throw denied();
  if (outcome.outcome !== "committed_reference") throw gatewayDomainError(outcome);
  const result = outcome.result;
  if (outcome.outcome !== "committed_reference" || outcome.error !== undefined || !result
      || Object.keys(result).sort().join(",") !== "body_base64,headers,permit_id,status"
      || result.status !== 200 || !identifier(result.permit_id)
      || !result.headers || typeof result.headers !== "object" || Array.isArray(result.headers)
      || Object.keys(result.headers).join(",") !== "content-type"
      || (result.headers as Record<string, unknown>)["content-type"] !== "text/event-stream"
      || typeof result.body_base64 !== "string" || !result.body_base64.length
      || result.body_base64.length > 4 * Math.ceil(plan.bounds.max_response_bytes / 3)
      || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(result.body_base64)) throw denied();
  const bytes = Buffer.from(result.body_base64, "base64");
  if (bytes.length > plan.bounds.max_response_bytes || bytes.toString("base64") !== result.body_base64) throw denied();
  return { response: HttpClientResponse.fromWeb(http, new Response(bytes,
    { status: 200, headers: { "content-type": "text/event-stream" } })),
    receipt: Object.freeze({ dispatch_id: plan.dispatch_id, permit_id: result.permit_id }) };
}

/** Native serialization only. Python owns current routing, final accounting and the single durable permit. */
export async function createGatewayAdapter(options: GatewayAdapterOptions): Promise<GatewayAdapter> {
  if (!(options.domain instanceof DomainClient) || typeof options.beforePrepare !== "function"
      || typeof options.validateImages !== "function") throw denied();
  const entries = new WeakMap<LLMRequest, Entry>();
  const adapters = new Set<NativeAdapter>();
  const dispatches = new Set<string>();
  const controllers = new Set<AbortController>();
  const settlements = new Set<Promise<void>>();
  let closing = false;
  let closePromise: Promise<void> | undefined;
  const hold = () => {
    let release!: () => void;
    const settlement = new Promise<void>(resolve => { release = () => { settlements.delete(settlement); resolve(); }; });
    settlements.add(settlement);
    return release;
  };
  const ownedIO = <A>(work: (signal: AbortSignal) => Promise<A>): Effect.Effect<A, AIError> =>
    Effect.uninterruptibleMask(restore => Effect.suspend(() => {
      if (closing) return Effect.fail(denied());
      const controller = new AbortController();
      controllers.add(controller);
      const pending = work(controller.signal);
      return restore(Effect.tryPromise({ try: () => pending, catch: safeFailure })).pipe(
        Effect.onInterrupt(() => Effect.promise(async () => { controller.abort(); await pending.catch(() => {}); })),
        Effect.ensuring(Effect.sync(() => { controllers.delete(controller); })),
      );
    }));
  const open = (binding: DomainBinding): Effect.Effect<Entry, AIError> => Effect.suspend(() => {
    if (closing) return Effect.fail(denied());
    if (Object.keys(binding).length !== bindingKeys.length || !bindingKeys.every(key => identifier(binding[key]))) return Effect.fail(denied());
    binding = Object.freeze({ ...binding });
    const release = hold();
    return Effect.suspend(() => options.beforePrepare(binding)).pipe(
    Effect.flatMap(value => ownedIO(async signal => {
        const preparation = trustedPreparation(value, binding);
        if (closing || dispatches.has(preparation.dispatch_id)) throw denied();
        dispatches.add(preparation.dispatch_id);
        binding = preparation.binding;
        let entry: Entry;
        const adapter = await createSubscriptionAdapter({ route: preparation.route, sessionId: binding.session_id,
          validateImages: images => options.validateImages(binding, images),
          dispatch: (_route, http) => ownedIO(async signal => {
              if (http.method !== "POST" || http.url !== preparation.route.endpoint || [...http.urlParams].length
                  || http.body._tag !== "Uint8Array" || http.body.body.length > preparation.bounds.max_request_bytes) throw denied();
              const body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(http.body.body));
              const output = body[preparation.route.protocol === "openai-responses" ? "max_output_tokens" : "max_completion_tokens"];
              if (body.model !== preparation.route.wire_model_id || !positive(output)
                  || output > preparation.role.output_tokens || output > preparation.limits.output_tokens) throw denied();
              const serialized: SerializedSubscriptionHttp = { method: "POST", url: http.url, headers: http.headers,
                body_base64: Buffer.from(http.body.body).toString("base64") };
              const payload = { dispatch_id: preparation.dispatch_id, serialized_request: serialized };
              if (Buffer.byteLength(JSON.stringify(payload) + "\n") > preparation.bounds.max_frame_bytes) throw denied();
              const outcome = await options.domain.request(binding, "model.dispatch", payload, { signal });
              let buffered: ReturnType<typeof bufferedHttp>;
              try { buffered = bufferedHttp(http, outcome, preparation); }
              catch (error) { entry.failure = safeFailure(error); throw entry.failure; }
              entry.receipt = buffered.receipt;
              return buffered.response;
          }),
        });
        if (closing || signal.aborted) { await adapter.close(); throw denied(); }
        entry = { adapter, plan: preparation, bound: false, used: false };
        adapters.add(adapter);
        return entry;
    })), Effect.ensuring(Effect.sync(release)));
  }).pipe(Effect.catchCause(cause => Cause.hasInterruptsOnly(cause) ? Effect.failCause(cause)
    : Effect.fail(safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause))))));
  const settingsAllowed = (settings?: StreamOptions) => !settings || Object.values(settings).every(value => value === undefined);
  const checkPrimary = (entry: Entry, request: LLMRequest, settings: StreamOptions) => {
    const route = entry.plan.route;
    const headers = new Set(["x-opencode-session-id", "x-session-affinity", "x-session-id",
      "user-agent", "x-opencode-project", "x-opencode-session", "x-opencode-client"]);
    if (!settingsAllowed(settings) || request.model.id !== route.wire_model_id || request.model.provider !== route.provider_id
        || request.model.route.protocol !== route.protocol
        || `${request.model.route.endpoint.baseURL}${request.model.route.endpoint.path}` !== route.endpoint
        || request.http?.body || request.http?.query
        || Object.keys(request.http?.headers ?? {}).some(name => !headers.has(name.toLowerCase()))
        || request.generation?.maxTokens !== undefined && (!positive(request.generation.maxTokens)
          || request.generation.maxTokens > entry.plan.role.output_tokens)) throw denied();
    requireInputs(request, entry.plan);
  };
  const bind = (entry: Entry, request: LLMRequest, maxTokens = entry.plan.role.output_tokens) => {
    if (closing) throw denied();
    requireInputs(request, entry.plan);
    const prepared = LLMRequest.update(request, { model: entry.adapter.model,
      generation: new GenerationOptions({ ...request.generation, maxTokens }) });
    entries.set(prepared, entry);
    return prepared;
  };
  const use = (entry: Entry, work: () => Effect.Effect<LLMRequest, AIError>) => Effect.suspend(() => {
    if (closing || entry.bound) return Effect.fail(denied());
    entry.bound = true;
    const release = hold();
    return Effect.suspend(work).pipe(
      Effect.onExit(exit => exit._tag === "Failure" ? finish(entry) : Effect.void),
      Effect.ensuring(Effect.sync(release)),
      Effect.catchCause(cause => Cause.hasInterruptsOnly(cause) ? Effect.failCause(cause)
        : Effect.fail(safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause))))),
    );
  });
  const prepare: GatewayAdapter["prepare"] = (binding, request, settings) => Effect.suspend(() => {
    if (!settingsAllowed(settings)) return Effect.fail(denied());
    return open(binding).pipe(Effect.flatMap(entry => use(entry, () => Effect.try({ try: () => bind(entry, request), catch: safeFailure }))));
  });
  const preparePrimary: GatewayAdapter["preparePrimary"] = (binding, currentResolved) => Effect.suspend(() => {
    if (typeof options.registerManifest !== "function") return Effect.fail(denied());
    return open(binding).pipe(Effect.flatMap(entry => Effect.try({ try: () => {
      const nativeResolved = SessionRunnerModel.resolved(entry.adapter.model, { capabilities: entry.plan.native_capabilities,
        cost: Object.freeze(structuredClone(currentResolved.cost)),
        limit: Object.freeze({ input: entry.plan.limits.input_tokens, output: entry.plan.role.output_tokens, context: entry.plan.limits.window_tokens }),
      });
      const resolved: SessionRunnerModel.Resolved = { ...nativeResolved,
        ref: Model.Ref.make({ providerID: Provider.ID.make(entry.plan.route.provider_id), id: Model.ID.make(entry.plan.route.catalog_model_id) }) };
      const primary: GatewayPrimaryPreparation = { resolved: Object.freeze(resolved),
        prepare: (request, settings, unfiltered) => use(entry, () => Effect.gen(function* () {
          if (!settingsAllowed(settings) || !unfiltered || !Array.isArray(unfiltered.system)
              || !Array.isArray(unfiltered.messages) || !Array.isArray(unfiltered.tools)) return yield* Effect.fail(denied());
          checkPrimary(entry, request, settings); requireInputs(unfiltered, entry.plan);
          yield* Effect.uninterruptible(Effect.suspend(() => options.registerManifest!(entry.plan, unfiltered)));
          checkPrimary(entry, request, settings);
          return bind(entry, request, request.generation?.maxTokens ?? entry.plan.role.output_tokens);
        })),
      };
      return Object.freeze(primary);
    }, catch: safeFailure }).pipe(Effect.onExit(exit => exit._tag === "Failure" ? finish(entry) : Effect.void))));
  });
  const claim = (request: LLMRequest) => {
    const entry = entries.get(request);
    if (closing || !entry || entry.used) throw denied();
    entry.used = true;
    requireInputs(request, entry.plan);
    entry.release = hold();
    return entry;
  };
  const finish = (entry: Entry) => Effect.promise(async () => {
    try { await entry.adapter.close(); adapters.delete(entry.adapter); } finally { entry.release?.(); }
  });
  const client: LLMClientShape = {
    generate: (request, settings) => Effect.suspend(() => {
      return Effect.try({ try: () => claim(request), catch: () => denied() }).pipe(
        Effect.flatMap(entry => entry.adapter.client.generate(request, settings).pipe(Effect.ensuring(finish(entry)),
          Effect.catchCause(cause => Cause.hasInterruptsOnly(cause) ? Effect.failCause(cause)
            : Effect.fail(entry.failure ?? safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause))))))));
    }),
    stream: (request, settings) => Stream.unwrap(Effect.try({ try: () => claim(request), catch: () => denied() }).pipe(
      Effect.map(entry => entry.adapter.client.stream(request, settings).pipe(Stream.ensuring(finish(entry)),
        Stream.catchCause(cause => Cause.hasInterruptsOnly(cause) ? Stream.failCause(cause)
          : Stream.fail(entry.failure ?? safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause))))))))),
    compact: () => Effect.fail(denied()),
  };
  return { client, prepare, preparePrimary, receipt: request => entries.get(request)?.receipt,
    close: () => {
      closing = true;
      for (const controller of controllers) controller.abort();
      return closePromise ??= (async () => {
        await Promise.all([...settlements]);
        await Promise.all([...adapters].map(adapter => adapter.close()));
        adapters.clear();
      })();
    } };
}
