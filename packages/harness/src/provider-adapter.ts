import { Cause, Effect, Layer, ManagedRuntime, Option, Stream } from "effect";
import { HttpClientRequest, type HttpClientResponse } from "effect/http";
import { LLMClient, LLMRequest, LLMResponse, Usage, HttpOptions, AIError, AuthenticationError, RateLimitError, QuotaExceededError,
  ProviderInternalError, TransportError, InvalidRequestError, Media, type LLMClientShape, type LLMEvent } from "@opencode/ai";
import { RequestExecutor } from "@opencode/ai/route/executor";
import { OpenAICompatibleChat } from "@opencode/ai/protocols/openai-compatible-chat";
import { OpenAIResponses } from "@opencode/ai/protocols/openai-responses";
import { Auth } from "@opencode/ai/route/auth";
import { Route, type StreamOptions } from "@opencode/ai/route/client";

/** Safe Python-owned route data; credential values never enter configuration. */
export interface SubscriptionRoute {
  readonly provider_id: "codex" | "opencode-go";
  readonly catalog_model_id: string;
  readonly wire_model_id: string;
  readonly endpoint: string;
  readonly protocol: "openai-responses" | "openai-chat";
  readonly credential_ref: string;
  readonly credential_epoch: number;
  readonly catalogue_listed: boolean | null;
}

export interface SubscriptionAdapterOptions {
  readonly route: SubscriptionRoute;
  readonly sessionId: string;
  /** Parent-owned final admission/budget gate AND credential injection, then IO.
   * Receives the actual serialized request. No default executor or auth discovery. */
  readonly dispatch: (route: SubscriptionRoute, request: HttpClientRequest.HttpClientRequest) =>
    Effect.Effect<HttpClientResponse.HttpClientResponse, AIError>;
  /** Python validate_harness_images reuses the managed Pillow parser. Required
   * for images, before dispatch; no omitted decoder can grant image IO. */
  readonly validateImages?: (images: readonly InlineImage[]) => Effect.Effect<void, AIError>;
}

export interface InlineImage {
  readonly type: "image";
  readonly media_type: "image/png" | "image/jpeg" | "image/webp";
  readonly data: string;
}

const allowed = {
  codex: ["gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna"],
  "opencode-go": ["mimo-v2.6-pro", "deepseek-v4.1-flash"],
} as const;
const denied = () => new AIError({ reason: new InvalidRequestError({ message: "Subscription adapter refused an incompatible request." }) });

function safeFailure(error?: AIError): AIError {
  switch (error?.reason._tag) {
    case "Authentication": return new AIError({ reason: new AuthenticationError({ message: "Reconnect the selected subscription." }) });
    case "RateLimit": return new AIError({ reason: new RateLimitError({ message: "The selected subscription reached a usage limit." }) });
    case "QuotaExceeded": return new AIError({ reason: new QuotaExceededError({ message: "The selected subscription reached its quota." }) });
    case "ProviderInternal": return new AIError({ reason: new ProviderInternalError({ message: "The selected subscription could not finish the request." }) });
    case "Transport": return new AIError({ reason: new TransportError({ message: "The selected subscription transport was interrupted.", transport: "http", operation: "request" }) });
    default: return denied();
  }
}

function safeEvent(event: LLMEvent): LLMEvent {
  // Unstructured diagnostics and raw metadata do not belong in transcripts.
  if (["provider-error", "tool-error", "tool-input-error"].includes(event.type)) throw denied();
  const safe = { ...event, providerMetadata: undefined };
  if (safe.type === "finish" || safe.type === "step-finish") return { ...safe,
    reason: { normalized: safe.reason.normalized },
    usage: safe.usage === undefined ? undefined : new Usage({ ...safe.usage, providerMetadata: undefined }),
  };
  return safe;
}

function validateRoute(route: SubscriptionRoute) {
  const models: readonly string[] | undefined = Object.hasOwn(allowed, route.provider_id) ? allowed[route.provider_id] : undefined;
  const codex = route.provider_id === "codex";
  if (!models?.includes(route.catalog_model_id) || route.catalog_model_id !== route.wire_model_id
      || route.protocol !== (codex ? "openai-responses" : "openai-chat")
      || route.endpoint !== (codex ? "https://api.openai.com/v1/responses" : "https://opencode.ai/zen/go/v1/chat/completions")
      || !/^[A-Za-z0-9_-]{1,128}$/.test(route.credential_ref)
      || !Number.isSafeInteger(route.credential_epoch) || route.credential_epoch < 0) throw denied();
}

function validateToolPairs(request: LLMRequest) {
  const pending = new Map<string, string>();
  const seen = new Set<string>();
  for (const message of request.messages) {
    if (pending.size && message.role !== "tool") throw denied();
    for (const part of message.content) {
      if (part.type === "tool-call") {
        if (message.role !== "assistant" || part.providerExecuted || seen.has(part.id)
            || !/^[A-Za-z0-9_-]{1,128}$/.test(part.id) || !/^[A-Za-z0-9_-]{1,128}$/.test(part.name)) throw denied();
        seen.add(part.id);
        pending.set(part.id, part.name);
      } else if (part.type === "tool-result") {
        if (message.role !== "tool" || part.providerExecuted || pending.get(part.id) !== part.name) throw denied();
        pending.delete(part.id);
      } else if (message.role === "tool") throw denied();
    }
  }
  if (pending.size) throw denied();
}

function validateInputs(request: LLMRequest) {
  if (!request.messages.length || request.messages.length > 200) throw denied();
  let text = request.system.reduce((sum, part) => sum + part.text.length, 0);
  let images = 0, imageBytes = 0;
  for (const tool of request.tools) {
    if (tool.type !== "tool" || tool.native !== undefined) throw denied();
    text += JSON.stringify(tool).length;
  }
  for (const message of request.messages) {
    for (const part of message.content) {
      if (part.type === "media") {
        const asset = part.media;
        const source = asset.source;
        if (message.role !== "user" || !["image/png", "image/jpeg", "image/webp"].includes(asset.mediaType)
            || (source.type !== "base64" && source.type !== "bytes")) throw denied();
        if (source.type === "base64" && (source.data.length > 11184812
            || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(source.data))) throw denied();
        const data = source.type === "bytes" ? source.data : Buffer.from(source.data, "base64");
        if (!data.length || data.length > 8 * 1024 * 1024 || Media.detectMediaType(data) !== asset.mediaType) throw denied();
        images += 1;
        imageBytes += data.length;
        if (images > 4 || imageBytes > 16 * 1024 * 1024) throw denied();
      } else if (part.type === "text" || part.type === "reasoning") {
        text += part.text.length;
      } else if (part.type === "tool-call") {
        text += JSON.stringify(part.input).length;
      } else if (part.type === "tool-result") {
        if (part.result.type === "content" && part.result.value.some(item => item.type !== "text")) throw denied();
        text += JSON.stringify(part.result.value).length;
      } else throw denied();
    }
  }
  if (text > 1000000) throw denied();
}

function finalImages(body: Record<string, unknown>, codex: boolean): readonly InlineImage[] {
  const images: InlineImage[] = [];
  const messages = body[codex ? "input" : "messages"];
  if (!Array.isArray(messages)) throw denied();
  for (const message of messages) {
    if (!Array.isArray(message.content)) continue;
    for (const part of message.content) {
      if (part.type !== (codex ? "input_image" : "image_url")) continue;
      const url = codex ? part.image_url : part.image_url?.url;
      const match = typeof url === "string" ? /^data:(image\/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)$/.exec(url) : null;
      if (!match || message.role !== "user") throw denied();
      images.push(Object.freeze({ type: "image", media_type: match[1] as InlineImage["media_type"], data: match[2] }));
    }
  }
  return Object.freeze(images);
}

export async function createSubscriptionAdapter(options: SubscriptionAdapterOptions) {
  const route = Object.freeze({ ...options.route });
  validateRoute(route);
  const codex = route.provider_id === "codex";
  const baseURL = codex ? "https://api.openai.com/v1" : "https://opencode.ai/zen/go/v1";
  // Select native serialization explicitly. HTTP only; upstream WS fallback and
  // opaque native compaction are separate parent acceptance gates.
  const model = codex
    ? Route.make({ id: "openai-responses", provider: route.provider_id,
        protocol: OpenAIResponses.protocol, endpoint: { baseURL, path: "/responses" },
        auth: Auth.none, transport: OpenAIResponses.httpTransport,
        defaults: { providerOptions: { store: false } },
      }).model({ id: route.wire_model_id })
    : OpenAICompatibleChat.route.with({ provider: route.provider_id, endpoint: { baseURL }, auth: Auth.none })
      .model({ id: route.wire_model_id });
  const executor: RequestExecutor.Interface = {
    execute: request => Effect.suspend(() => {
      if (request.method !== "POST" || request.url !== route.endpoint || [...request.urlParams].length
          || request.body._tag !== "Uint8Array") return Effect.fail(denied());
      let body: Record<string, unknown>;
      try { body = JSON.parse(new TextDecoder().decode(request.body.body)); }
      catch { return Effect.fail(denied()); }
      if (body.model !== route.wire_model_id || body.stream !== true || body.store === true
          || body.context_management !== undefined || body.previous_response_id !== undefined
          || body.conversation !== undefined || body.truncation === "auto") return Effect.fail(denied());
      let images: readonly InlineImage[];
      try { images = finalImages(body, codex); } catch { return Effect.fail(denied()); }
      if (images.length && !options.validateImages) return Effect.fail(denied());
      const validation = images.length ? options.validateImages!(images) : Effect.void;
      return validation.pipe(Effect.flatMap(() => options.dispatch(route, HttpClientRequest.setHeaders(request, {
      "user-agent": "Renulus/0.1.0",
      ...(codex ? {} : { "x-opencode-session": options.sessionId }),
      }))), Effect.flatMap(response => {
        if (response.status === 401 || response.status === 403)
          return Effect.fail(new AIError({ reason: new AuthenticationError({ message: "Reconnect the selected subscription." }) }));
        if (response.status === 429)
          return Effect.fail(new AIError({ reason: new RateLimitError({ message: "The selected subscription reached a usage limit." }) }));
        if (response.status >= 500)
          return Effect.fail(new AIError({ reason: new ProviderInternalError({ message: "The selected subscription could not finish the request." }) }));
        if (response.status >= 300) return Effect.fail(denied());
        return Effect.succeed(response);
      }));
    }),
  };
  const runtime = ManagedRuntime.make(LLMClient.layer.pipe(
    Layer.provide(Layer.succeed(RequestExecutor.Service, executor)),
  ));
  const nativeClient = await runtime.runPromise(LLMClient.Service);
  const prepare = (request: LLMRequest, settings?: StreamOptions) => Effect.try({
    try: () => {
      if (settings?.http || settings?.webSocket) throw denied();
      if (request.http?.body || request.http?.query) throw denied();
      const upstreamHeaders = new Set(["x-opencode-session-id", "x-session-affinity", "x-session-id",
        "x-opencode-parent-session-id", "x-parent-session-id",
        "user-agent", "x-opencode-project", "x-opencode-session", "x-opencode-client"]);
      if (Object.keys(request.http?.headers ?? {}).some(name => !upstreamHeaders.has(name.toLowerCase()))) throw denied();
      if (request.model.id !== route.catalog_model_id || request.model.provider !== route.provider_id
          || request.model.route.protocol !== route.protocol || request.model.route.endpoint.baseURL !== baseURL) throw denied();
      validateToolPairs(request);
      validateInputs(request);
      // Upstream session headers are recognized but reconstructed by Renulus.
      // Do not forward project paths, another client identity or arbitrary values.
      return LLMRequest.update(request, { model, http: request.http === undefined ? undefined
        : new HttpOptions({ timeout: request.http.timeout, headerTimeout: request.http.headerTimeout, chunkTimeout: request.http.chunkTimeout }) });
    },
    catch: () => denied(),
  });
  const client: LLMClientShape = {
    stream: (request, settings) => Stream.unwrap(prepare(request, settings).pipe(
      Effect.map(prepared => nativeClient.stream(prepared)),
    )).pipe(Stream.map(safeEvent), Stream.catchCause(cause => Cause.hasInterruptsOnly(cause)
      ? Stream.failCause(cause) : Stream.fail(safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause)))))),
    generate: (request, settings) => prepare(request, settings).pipe(
      Effect.flatMap(prepared => nativeClient.generate(prepared)),
      Effect.flatMap(response => Effect.try({ try: () => {
        const safe = LLMResponse.fromEvents(response.events.map(safeEvent));
        if (!safe) throw denied();
        return safe;
      }, catch: () => denied() })),
      Effect.catchCause(cause => Cause.hasInterruptsOnly(cause)
        ? Effect.failCause(cause) : Effect.fail(safeFailure(Option.getOrUndefined(Cause.findErrorOption(cause))))),
    ),
    compact: () => Effect.fail(denied()),
  };
  return { providerId: route.provider_id, modelId: route.catalog_model_id, model, client,
    configuration: { model: `${route.provider_id}/${route.catalog_model_id}`,
      providers: { [route.provider_id]: {
        package: codex ? "@opencode/ai/providers/openai" : "@opencode/ai/providers/openai-compatible",
        settings: { baseURL }, models: { [route.catalog_model_id]: { limit: { context: 32768, output: 4096 } } },
      } },
    },
    close: () => runtime.dispose(),
  };
}
