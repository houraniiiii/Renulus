import { Cause, Effect, Stream } from "effect";
import { HttpClientResponse, type HttpClientRequest } from "effect/http";
import { AIError, InvalidRequestError, GenerationOptions, LLMRequest, type LLMClientShape } from "@opencode/ai";
import type { Model } from "@opencode/schema/model";
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
export interface GatewayAdapterOptions {
  readonly domain: DomainClient;
  readonly beforePrepare: (binding: DomainBinding) => Effect.Effect<TrustedGatewayPreparation, AIError>;
  readonly validateImages: (binding: DomainBinding, images: readonly InlineImage[]) => Effect.Effect<void, AIError>;
}
export interface GatewayAdapter {
  readonly client: LLMClientShape;
  prepare(binding: DomainBinding, request: LLMRequest, settings?: StreamOptions): Effect.Effect<LLMRequest, AIError>;
  receipt(request: LLMRequest): Readonly<GatewayReceipt> | undefined;
  close(): Promise<void>;
}
const denied = () => new AIError({ reason: new InvalidRequestError({ message: "Trusted model gateway refused the request." }) });
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
type Entry = { adapter: NativeAdapter; plan: TrustedGatewayPreparation; used: boolean;
  release?: () => void; receipt?: Readonly<GatewayReceipt> };
function requireInputs(request: LLMRequest, plan: TrustedGatewayPreparation) {
  if (!plan.native_capabilities.tools && (request.tools.length || request.messages.some(message =>
    message.content.some(part => part.type === "tool-call" || part.type === "tool-result")))) throw denied();
  if (!plan.native_capabilities.input.includes("image") && request.messages.some(message =>
    message.content.some(part => part.type === "media"))) throw denied();
}
function bufferedHttp(http: HttpClientRequest.HttpClientRequest, outcome: DomainOutcome, plan: TrustedGatewayPreparation) {
  const result = outcome.result;
  if (outcome.outcome !== "committed_reference" || outcome.error !== undefined || !result
      || Buffer.byteLength(JSON.stringify(outcome) + "\n") > plan.bounds.max_frame_bytes
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
      return restore(Effect.tryPromise({ try: () => pending, catch: () => denied() })).pipe(
        Effect.onInterrupt(() => Effect.promise(async () => { controller.abort(); await pending.catch(() => {}); })),
        Effect.ensuring(Effect.sync(() => { controllers.delete(controller); })),
      );
    }));
  const prepare: GatewayAdapter["prepare"] = (binding, request, settings) => Effect.suspend(() => {
    if (closing || settings && Object.values(settings).some(value => value !== undefined)) return Effect.fail(denied());
    if (Object.keys(binding).length !== bindingKeys.length || !bindingKeys.every(key => identifier(binding[key]))) return Effect.fail(denied());
    binding = Object.freeze({ ...binding });
    const release = hold();
    return Effect.suspend(() => options.beforePrepare(binding)).pipe(
    Effect.flatMap(value => ownedIO(async signal => {
        const preparation = trustedPreparation(value, binding);
        if (closing || dispatches.has(preparation.dispatch_id)) throw denied();
        requireInputs(request, preparation);
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
              const buffered = bufferedHttp(http, outcome, preparation);
              entry.receipt = buffered.receipt;
              return buffered.response;
          }),
        });
        if (closing || signal.aborted) { await adapter.close(); throw denied(); }
        entry = { adapter, plan: preparation, used: false };
        adapters.add(adapter);
        const prepared = LLMRequest.update(request, { model: adapter.model,
          generation: new GenerationOptions({ ...request.generation, maxTokens: preparation.role.output_tokens }) });
        entries.set(prepared, entry);
        return prepared;
    })), Effect.ensuring(Effect.sync(release)));
  }).pipe(Effect.catchCause(cause => Cause.hasInterruptsOnly(cause) ? Effect.failCause(cause) : Effect.fail(denied())));
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
        Effect.flatMap(entry => entry.adapter.client.generate(request, settings).pipe(Effect.ensuring(finish(entry)))));
    }),
    stream: (request, settings) => Stream.unwrap(Effect.try({ try: () => claim(request), catch: () => denied() }).pipe(
      Effect.map(entry => entry.adapter.client.stream(request, settings).pipe(Stream.ensuring(finish(entry)))))),
    compact: () => Effect.fail(denied()),
  };
  return { client, prepare, receipt: request => entries.get(request)?.receipt,
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
