// SPDX-License-Identifier: MIT
// SDK capability proof only: no production migration or shared host adapter.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { Cause, Effect, Exit, Layer, Logger, ManagedRuntime, Schema, Stream } from "effect";
import { AIError, InvalidRequestError, LLMClient } from "@opencode/ai";
import { OpenCode, AbsolutePath } from "@opencode/sdk/effect";
import { SessionMessage } from "@opencode/schema/session-message";
import { Session } from "@opencode/schema/session";
import { Config } from "@opencode/core/config";
import { InstructionDiscovery } from "@opencode/core/instruction-discovery";
import { llmClient } from "@opencode/core/effect/app-node-platform";
import { Global } from "@opencode/util/global";

const [mode, rootArgument, snapshotPath] = process.argv.slice(2);
assert.ok(["import", "observe", "delete"].includes(mode));
const root = path.resolve(rootArgument);
const snapshot = JSON.parse(await readFile(snapshotPath, "utf8"));
const workspace = path.join(root, "workspace");
await mkdir(workspace, { recursive: true });
const digest = createHash("sha256").update(JSON.stringify(snapshot)).digest("hex");
const stable = (prefix, value) => prefix + createHash("sha256").update(value).digest("hex");
const sessionID = stable("ses_", snapshot.id);
const location = { directory: AbsolutePath.make(workspace) };
const metadata = { renulusProfile: "synthetic-h06-profile", renulusStore: "synthetic-h06-store",
  operationId: "synthetic-h06-migration", legacyThreadId: snapshot.id, sourceDigest: digest, lineage: "unknown" };
let modelCalls = 0;
const denied = () => {
  modelCalls++;
  return new AIError({ reason: new InvalidRequestError({ message: "H06 proof forbids all inference." }) });
};
const client = { stream: () => Stream.fail(denied()), generate: () => Effect.fail(denied()),
  compact: () => Effect.fail(denied()) };
const content = JSON.stringify({ compaction: { auto: false }, agents: { title: { disabled: true } } });
const overrides = [
  Global.node.replace(Global.layerWith(Object.fromEntries(
    ["home", "data", "cache", "config", "state", "tmp", "bin", "log", "repos"].map(
      key => [key, path.join(root, key)])))),
  Config.node.replace(Config.configured({ project: false, global: false, content })),
  InstructionDiscovery.node.replace(InstructionDiscovery.configured({ project: false, global: false })),
  llmClient.replace(Layer.succeed(LLMClient.Service, client)),
];
const runtime = ManagedRuntime.make(Layer.effect(OpenCode.Service, OpenCode.create({
  app: { name: "renulus-h06-capability-proof", version: "1" },
  database: { path: path.join(root, "native.sqlite") },
  config: { directory: path.join(root, "config"), project: false, content },
  models: { fetch: false, snapshot: false }, fs: { filewatcher: false, fff: false },
  events: { persist: false },
}, { overrides })).pipe(Layer.provideMerge(Logger.layer([], { mergeWithExisting: false }))));
const commands = [];
const run = effect => runtime.runPromise(effect);
let result;
try {
  const sdk = await runtime.runPromise(OpenCode.Service);
  if (mode === "import") {
    // Native template fields come from supported SDK operations; no model turn.
    commands.push("session.create");
    const template = await run(sdk.sessions.create({ location, title: "Synthetic import template" }));
    commands.push("session.remove");
    await run(sdk.sessions.remove({ sessionID: template.id }));
    const messages = snapshot.messages.map(message => {
      assert.ok(["user", "assistant"].includes(message.role));
      const created = Date.parse(message.created_at);
      const common = { id: stable("msg_", snapshot.id + "/" + message.id),
        type: message.role, metadata: { lineage: "unknown", legacy: { id: message.id,
          run_id: message.run_id, created_at: message.created_at, citations: message.citations } },
        time: { created } };
      return Schema.decodeUnknownSync(SessionMessage.Info)(message.role === "user"
        ? { ...common, text: message.content }
        : { ...common, agent: "legacy-import", model: { providerID: "legacy", id: "retained-answer" },
          content: [{ type: "text", text: message.content }], time: { created, completed: created } });
    });
    const info = { ...template, id: sessionID, title: snapshot.title, metadata,
      permissions: [{ action: "*", resource: "*", effect: "deny" }] };
    commands.push("session.import");
    await run(sdk.sessions.import({ info, messages, location }));
    // Lose the import acknowledgement. No native result/mapping is returned.
    result = { acknowledged: false };
  } else if (mode === "observe") {
    commands.push("session.get");
    const info = await run(sdk.sessions.get({ sessionID }));
    assert.deepEqual(info.metadata, metadata);
    commands.push("session.export");
    const retained = await run(sdk.sessions.export({ sessionID, sanitize: false }));
    result = { info: Schema.encodeSync(Session.Info)(info),
      messages: retained.messages.map(message => Schema.encodeSync(SessionMessage.Info)(message)) };
  } else {
    commands.push("session.remove");
    await run(sdk.sessions.remove({ sessionID }));
    commands.push("session.get");
    const unavailable = await run(Effect.exit(sdk.sessions.get({ sessionID })));
    assert.ok(Exit.isFailure(unavailable));
    const tag = Cause.squash(unavailable.cause)._tag;
    assert.equal(tag, "Session.NotFoundError");
    result = { deleted: true, unavailable: tag };
  }
} finally {
  await runtime.dispose();
}
assert.equal(modelCalls, 0);
process.stdout.write(JSON.stringify({ ...result, commands, model_calls: modelCalls }) + "\n");
