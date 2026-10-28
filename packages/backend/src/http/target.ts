// SPDX-License-Identifier: MIT
import http from "node:http";
import { timingSafeEqual } from "node:crypto";
import type { StorageClient } from "../storage/index.ts";
import { StorageError } from "../storage/index.ts";
import { PluginLifecycleError } from "../plugins/manifest.ts";
import { readJsonObject, RequestBodyError } from "./body.ts";
import { pluginCommand, type PluginCommands } from "./plugin-commands.ts";
import { learningCommand, type SavedLearning } from './learning-commands.ts';
import { learningStream } from './learning-stream.ts';
import { temporaryLearning } from './learning-temporary.ts';
import { credentialCommand, type CredentialCommands } from './credential-commands.ts';
import type { ConnectedTarget } from '../host/composition.ts';
import { memoryCommand } from './memory-commands.ts';
import { knowledgeCommand } from './knowledge-commands.ts';
import { projectCommand } from './project-commands.ts';
import { mcpCommand, type McpCommands } from './mcp-commands.ts';
import { developerCommand, type DeveloperCommands } from './developer-commands.ts';
import { questionCommand, type QuestionCommands } from './question-commands.ts';
import { findCommand } from './find-commands.ts';
import type { FindDomain } from '../domain/find/index.ts';
import type { KnowledgeDomain } from '../domain/knowledge/index.ts';
import { assessmentCommand } from './assessment-commands.ts';
import { contentCommand, type ContentPorts } from './content-commands.ts';
import type { AssessmentGeneration } from '../domain/assessment/generation.ts';
import { studyCommand } from './study-commands.ts';
import { updatesCommand } from './updates-commands.ts';
import { recoveryCommand, RECOVERY_SELECT, type RecoveryPort } from './recovery-commands.ts';

/** BF00 final-owner target. Its explicit synthetic selector is checked by the
 * canonical thread; it cannot open production profiles or proxy domain writes.
 */
export interface TargetFacadeOptions {
  port: number; token: string; storage: StorageClient; plugins?: PluginCommands;
  learning?: SavedLearning;
  temporary?: ConnectedTarget['temporary'];
  credentials?: CredentialCommands;
  mcp?: McpCommands;
  developer?: DeveloperCommands;
  questions?: QuestionCommands;
  configuration?: ConnectedTarget['configuration'];
  inspect?: ConnectedTarget['inspect'];
  memory?: ConnectedTarget['memory'];
  knowledge?: KnowledgeDomain;
  find?: FindDomain;
  assessment?: AssessmentGeneration;
  content?: ContentPorts;
  study?: ConnectedTarget['study'];
  updates?: ConnectedTarget['updates'];
  /** Retains actual native/plugin ownership through settlement before SQLite closes. */
  settlePlugins?: () => Promise<void>;
  /** Candidate-generation selection by the selected owner (expected owner/epoch required). */
  recovery?: RecoveryPort;
}
export async function openTargetFacade(options: TargetFacadeOptions) {
  if (!options.token || !Number.isSafeInteger(options.port) || options.port < 0 || options.port > 65535)
    throw new Error("invalid_target_facade_configuration");
  if (options.plugins && !options.settlePlugins) throw new Error("plugin_settlement_required");
  let closing = false, active = 0;
  let state: "running" | "stopping" | "held" | "settled" = "running";
  let closedResolve!: () => void;
  const closed = new Promise<void>(resolve => { closedResolve = resolve; });
  const ordinary = new Set<Promise<void>>();
  let settlement: Promise<void> | undefined;
  const settle = () => {
    // Claim synchronously, before another pipelined request can enter deferred work.
    closing = true;
    return settlement ??= (async () => {
      state = "stopping";
      // Control requests never wait on each other; drain only previously admitted work.
      await Promise.all([...ordinary]);
      await options.learning?.close();
      await options.settlePlugins?.();
      await options.storage.close();
      state = "settled";
    })().catch(error => { settlement = undefined; state = "held"; throw error; });
  };
  let selection: Promise<unknown> | undefined;
  /** Logical admission closes first, admitted work drains, and only then does the canonical writer settle. */
  const closeForSelection = async () => {
    closing = true;
    await Promise.all([...ordinary]);
    const { frontierDigest } = await options.storage.command({ type: "recovery.snapshot" });
    await settle();
    return frontierDigest;
  };
  const temporary = temporaryLearning(options.storage, options.temporary);
  const server = http.createServer((request, response) => {
    const send = (status: number, value: unknown) => {
      if (response.destroyed) return;
      response.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" });
      response.end(JSON.stringify(value));
    };
    const failure = (status: number, code: string) => send(status, { error: { code,
      message: "The local operation could not be completed. Inspect its current state before retrying.", retryable: status >= 500 } });
    if (!/^(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?$/.test(request.headers.host ?? "")) return failure(403, "invalid_host");
    const supplied = Buffer.from(String(request.headers["x-renulus-token"] ?? "")), expected = Buffer.from(options.token);
    if (supplied.length !== expected.length || !timingSafeEqual(supplied, expected)) return failure(401, "invalid_session");
    const origin = request.headers.origin;
    if (origin && origin !== "null") {
      try {
        const url = new URL(origin);
        if (!["http:", "https:"].includes(url.protocol) || !["localhost", "127.0.0.1"].includes(url.hostname)) return failure(403, "invalid_origin");
      } catch { return failure(403, "invalid_origin"); }
    }
    let url: URL;
    try { url = new URL(request.url ?? "/", "http://127.0.0.1"); }
    catch { return failure(422, "invalid_request"); }
    const shutdown = request.method === "POST" && url.pathname === "/api/v1/runtime/shutdown";
    const status = request.method === "GET" && ["/api/v1/meta", "/api/v1/runtime/status", "/api/v1/runtime/plugins"].includes(url.pathname);
    const selecting = request.method === "POST" && url.pathname === RECOVERY_SELECT;
    const control = shutdown || status || selecting;
    if (closing && !control) return failure(503, "runtime_stopping");
    if (!control && active >= 64) return failure(503, "runtime_overloaded");
    const stopping = shutdown ? settle() : undefined;
    if (!control) active++;
    const operation = Promise.resolve().then(async () => {
      if (stopping) {
        await stopping;
        send(200, { state: "settled", api_version: 1 });
        setImmediate(() => { void closeFacade().catch(() => {}); });
        return;
      }
      if (selecting) {
        if (!options.recovery) return failure(503, "recovery_unavailable");
        if (selection) return failure(409, "recovery_selection_in_progress");
        let closedWriter = false;
        const result = selection = recoveryCommand(request, options.recovery, () => { closedWriter = true; return closeForSelection(); });
        try { const { status, value } = await result; return send(status, value); }
        finally {
          selection = undefined;
          // Once the writer settled the process cannot resume; a failed publication leaves the old selector for relaunch.
          if (closedWriter) setImmediate(() => { void closeFacade().catch(() => {}); });
        }
      }
      if (request.method === "GET" && url.pathname === "/api/v1/meta")
        return send(200, { version: "0.1.0", api_version: 1, modules: { canonical: { status: "installed" } } });
      if (request.method === "GET" && url.pathname === "/api/v1/runtime/status")
        return send(200, { state, admission: closing ? "closed" : "open", active_operations: active, api_version: 1 });
      if (request.method === "GET" && url.pathname === "/api/v1/data/export")
        return send(200, await options.storage.command({ type: "records.export" }));
      if (url.pathname === '/api/v1/runtime/configuration') {
        if (!options.configuration) return failure(503, 'configuration_host_unavailable');
        if (request.method === 'GET') return send(200, await options.configuration.snapshot());
        if (request.method === 'POST') {
          const body = await readJsonObject(request, 128 * 1024);
          if (Object.keys(body).join(',') !== 'spec') return failure(422, 'invalid_request');
          return send(200, await options.configuration.activate(body.spec as never));
        }
      }
      if (request.method === 'GET' && url.pathname === '/api/v1/runtime/registry') {
        if (!options.inspect) return failure(503, 'plugin_host_unavailable');
        return send(200, await options.inspect());
      }
      const credential = await credentialCommand(request, url, options.credentials);
      if (credential) return send(credential.status, credential.value);
      const mcp = await mcpCommand(request, url, options.mcp);
      if (mcp) return send(mcp.status, mcp.value);
      const developer = await developerCommand(request, url, options.developer);
      if (developer) return send(developer.status, developer.value);
      const question = await questionCommand(request, url, options.questions);
      if (question) return send(question.status, question.value);
      const memory = await memoryCommand(request, url, options.storage, options.memory);
      if (memory) return send(memory.status, memory.value);
      const project = await projectCommand(request, url, options.storage);
      if (project) return send(project.status, project.value);
      const assessment = await assessmentCommand(request, url, options.storage, options.assessment);
      if (assessment) return send(assessment.status, assessment.value);
      const content = await contentCommand(request, url, options.storage, options.content);
      if (content) return send(content.status, content.value);
      const study = options.study ? await studyCommand(request, url, options.storage, options.study) : undefined;
      if (study) return send(study.status, study.value);
      const updates = options.updates ? await updatesCommand(request, url, options.storage, options.updates) : undefined;
      if (updates) return send(updates.status, updates.value);
      const found = await findCommand(request, url, options.find);
      if (found) return send(found.status, found.value);
      const knowledge = await knowledgeCommand(request, url, options.storage, options.knowledge);
      if (knowledge) {
        if ('body' in knowledge) {
          response.writeHead(knowledge.status, knowledge.headers); response.end(knowledge.body); return;
        }
        return send(knowledge.status, knowledge.value);
      }
      if (url.pathname === "/api/v1/runtime/plugins" || url.pathname.startsWith("/api/v1/runtime/plugins/")) {
        if (!options.plugins) return failure(503, "plugin_host_unavailable");
        return send(200, await pluginCommand(request, url, options.plugins));
      }
      if (await temporary(request, response, url)) return;
      if (await learningStream(request, response, url, options.storage, options.learning)) return;
      const learning = await learningCommand(request, url, options.storage, options.learning);
      if (learning) return send(learning.status, learning.value);
      const rename = /^\/api\/v1\/conversations\/learning\/([A-Za-z0-9_-]{1,120})$/.exec(url.pathname);
      if (request.method === "PATCH" && rename) {
        const body = await readJsonObject(request, 4096);
        if (Object.keys(body).sort().join(",") !== "expected_revision,title") return failure(422, "invalid_request");
        const result = await options.storage.command({ type: "learning.rename", threadId: rename[1],
          expectedRevision: body.expected_revision as number, title: body.title as string,
          idempotencyKey: String(request.headers["idempotency-key"] ?? "") });
        return send(200, result);
      }
      return failure(404, "not_found");
    }).catch(error => {
      const code = error instanceof StorageError || error instanceof PluginLifecycleError ? error.code :
        error instanceof RequestBodyError ? "invalid_request" : "backend_operation_failed";
      return failure(error instanceof RequestBodyError ? error.status : code === "assistance_restricted" ? 423 :
        error instanceof StorageError || error instanceof PluginLifecycleError ? 409 : 503, code);
    }).finally(() => { if (!control) { active--; ordinary.delete(operation); } });
    if (!control) ordinary.add(operation);
  });
  server.headersTimeout = 15_000;
  server.requestTimeout = 30_000;
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject); server.listen(options.port, "127.0.0.1", () => { server.off("error", reject); resolve(); });
  });
  let close: Promise<void> | undefined;
  const closeFacade = () => close ??= (async () => {
      await settle();
      await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
      closedResolve();
    })().catch(error => { close = undefined; throw error; });
  return { port: (server.address() as import("node:net").AddressInfo).port, closed, close: closeFacade };
}
