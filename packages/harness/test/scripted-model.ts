import { Effect, ManagedRuntime, Stream } from "effect";
import { TestLLM } from "@opencode/ai/testing";
import { AIError, RateLimitError } from "@opencode/ai";
import type { ModelAdapter } from "../src/host.ts";

export async function scriptedModel(answer: string, hold = false) {
  const runtime = ManagedRuntime.make(TestLLM.testLayer());
  const client = await runtime.runPromise(TestLLM.Test);
  let release!: () => void;
  const settlement = new Promise<void>(resolve => { release = resolve; });
  const response = TestLLM.text(answer, "answer");
  await runtime.runPromise(client.push(hold
    ? Stream.unwrap(Effect.promise(() => settlement).pipe(Effect.uninterruptible, Effect.as(Stream.fromIterable(response))))
    : response));
  return {
    providerId: "synthetic",
    modelId: "counted-learning",
    configuration: {
      model: "synthetic/counted-learning",
      providers: { synthetic: {
        package: "@opencode/ai/providers/openai-compatible",
        settings: { baseURL: "https://synthetic.invalid/v1", apiKey: "synthetic-unused" },
        models: { "counted-learning": { limit: { context: 128000, output: 4096 } } },
      } },
    },
    client,
    count: async () => (await runtime.runPromise(client.requests())).length,
    started: (count = 1) => runtime.runPromise(client.wait(count)),
    release,
    respond: (text: string) => runtime.runPromise(client.push(TestLLM.text(text, "answer"))),
    failNext: () => runtime.runPromise(client.push(Stream.fail(new AIError({
      reason: new RateLimitError({ message: "Synthetic retryable limit", retryAfterMs: 1 }),
    })))),
    async holdNext(text: string) {
      let done!: () => void;
      const pending = new Promise<void>(resolve => { done = resolve; });
      await runtime.runPromise(client.push(Stream.unwrap(Effect.promise(() => pending).pipe(
        Effect.uninterruptible, Effect.as(Stream.fromIterable(TestLLM.text(text, "answer"))),
      ))));
      return done;
    },
    close: () => runtime.dispose(),
  } satisfies ModelAdapter & { count(): Promise<number>; close(): Promise<void>; started(count?: number): Promise<void>; release(): void; respond(text: string): Promise<void>; failNext(): Promise<void>; holdNext(text: string): Promise<() => void> };
}
