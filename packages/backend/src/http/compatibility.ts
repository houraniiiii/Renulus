// SPDX-License-Identifier: MIT
import http, { type IncomingMessage, type ServerResponse } from "node:http";
import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";
import { createConnection } from "node:net";
import { pipeline } from "node:stream/promises";

export interface CompatibilityFacadeOptions {
  readonly token: string;
  readonly upstreamPort: number;
  readonly port: number;
  readonly maxInflight?: number;
  readonly peerKey?: string;
}

/** The probe contains no credentials or request body. Reuse only its proven
 * TCP connection; an Agent is forbidden to reconnect after the proof.
 */
interface OwnedTransport {
  agent(agent: http.Agent): void;
  request(request: http.ClientRequest): void;
}
async function authenticatedConnection(options: CompatibilityFacadeOptions, owned: OwnedTransport) {
  if (!options.peerKey) return undefined; // Explicit isolated transport fixtures.
  const agent = new http.Agent({ keepAlive: true, maxSockets: 1 });
  owned.agent(agent);
  let opened = false;
  agent.createConnection = (configuration, callback) => {
    if (opened) { callback?.(new Error("owned_peer_connection_lost"), undefined as never); return undefined as never; }
    opened = true;
    return createConnection({ host: "127.0.0.1", port: options.upstreamPort });
  };
  try {
    const nonce = randomBytes(32).toString("hex");
    const expected = createHmac("sha256", options.peerKey).update("renulus-domain-http/1:" + nonce).digest("hex");
    const proof = await new Promise<string>((resolve, reject) => {
      const probe = http.get({ hostname: "127.0.0.1", port: options.upstreamPort,
        path: "/__renulus_peer?nonce=" + nonce, agent }, response => {
        let bytes = 0, value = "";
        response.on("data", chunk => { bytes += chunk.length; if (bytes > 256) response.destroy(new Error("peer_proof_invalid")); else value += chunk.toString("utf8"); });
        response.once("error", reject);
        response.once("end", () => response.statusCode === 200 ? resolve(value) : reject(new Error("peer_proof_denied")));
      });
      owned.request(probe);
      // Socket inactivity can be refreshed forever by informational responses.
      // This deadline covers the entire proof, regardless of incoming traffic.
      const deadline = setTimeout(() => probe.destroy(new Error("peer_proof_timeout")), 2000);
      probe.once("close", () => { clearTimeout(deadline); reject(new Error("peer_proof_closed")); });
      probe.once("error", reject);
    });
    if (!matches(proof, expected)) throw new Error("peer_proof_invalid");
    return agent;
  } catch (error) { agent.destroy(); throw error; }
}

const hopHeaders = new Set(["connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade"]);

function publicHeaders(headers: IncomingMessage["headers"]) {
  const connection = String(headers.connection ?? "").toLowerCase().split(",").map(value => value.trim());
  return Object.fromEntries(Object.entries(headers).filter(([key]) => !hopHeaders.has(key) && !connection.includes(key)));
}

function error(response: ServerResponse, status: number, code: string, message: string) {
  if (response.headersSent || response.destroyed) return;
  response.writeHead(status, { "content-type": "application/json", "cache-control": "no-store" });
  response.end(JSON.stringify({ error: { code, message, retryable: status >= 500 } }));
}

function matches(actual: string, expected: string) {
  const left = Buffer.from(actual), right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

/** Migration adapter: Python remains the one canonical and dispatch owner.
 * Streams are piped with backpressure; neither an observer loss nor an HTTP
 * retry submits a new generation. The upstream owner decides retention policy.
 */
export async function openCompatibilityFacade(options: CompatibilityFacadeOptions) {
  if (!options.token || !Number.isSafeInteger(options.upstreamPort) || options.upstreamPort < 1 ||
      options.upstreamPort > 65535 || !Number.isSafeInteger(options.port) || options.port < 0 || options.port > 65535)
    throw new Error("invalid_facade_configuration");
  const limit = options.maxInflight ?? 64;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 1024) throw new Error("invalid_facade_capacity");
  let closing = false, blocked = false, stoppingTransport = false, active = 0;
  const transports = new Set<() => void>();
  const drains = new Set<Promise<void>>();
  const server = http.createServer((request, response) => {
    const host = request.headers.host ?? "";
    if (!/^(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?$/.test(host))
      return error(response, 403, "invalid_host", "Local access only");
    if (!request.url?.startsWith("/api/v1/") || request.url.startsWith("//") || request.url.includes("\\"))
      return error(response, 404, "not_found", "Unknown application command");
    const origin = request.headers.origin;
    if (origin && origin !== "null") {
      try {
        const parsed = new URL(origin);
        if (!["http:", "https:"].includes(parsed.protocol) || !["localhost", "127.0.0.1"].includes(parsed.hostname))
          return error(response, 403, "invalid_origin", "Local app origin required");
      } catch { return error(response, 403, "invalid_origin", "Local app origin required"); }
    }
    if (request.url !== "/api/v1/health" && !matches(String(request.headers["x-renulus-token"] ?? ""), options.token))
      return error(response, 401, "invalid_session", "Reconnect the application");
    if (blocked || stoppingTransport) return error(response, 503, "backend_owner_uncertain", "The owned backend disconnected; recovery is required");
    const control = ["/api/v1/health", "/api/v1/meta", "/api/v1/runtime/status", "/api/v1/runtime/shutdown"].includes(request.url);
    if (closing && !control) return error(response, 503, "runtime_stopping", "Renulus is closing this profile");
    // Keep control capacity independent from blocked data streams.
    if (!control && active >= limit) return error(response, 503, "runtime_overloaded", "Wait for current local work to settle");
    if (!control) active++;
    let finish!: () => void;
    const drain = new Promise<void>(resolve => { finish = resolve; });
    drains.add(drain);
    const requests = new Set<http.ClientRequest>(), agents = new Set<http.Agent>();
    const sockets = new Set<import("node:net").Socket>(), socketDrains: Promise<void>[] = [];
    let cancelled = false, settled = false;
    const cancel = () => {
      cancelled = true;
      for (const request of requests) request.destroy(new Error("owned_transport_closed"));
      for (const agent of agents) agent.destroy();
    };
    transports.add(cancel);
    const owned: OwnedTransport = {
      agent: agent => { agents.add(agent); },
      request: request => {
        requests.add(request);
        request.once("close", () => requests.delete(request));
        request.once("socket", socket => {
          if (sockets.has(socket)) return;
          sockets.add(socket);
          socketDrains.push(new Promise<void>(resolve => { socket.once("close", () => resolve()); }));
        });
      },
    };
    const settle = async () => {
      if (settled) return;
      settled = true;
      cancel();
      await Promise.all(socketDrains);
      if (!control) active--;
      transports.delete(cancel); drains.delete(drain); finish();
    };
    response.once("close", () => {
      // Observation loss cancels the transport, including an unfinished proof.
      // The upstream owner alone decides saved-operation cancellation.
      if (!response.writableFinished) cancel();
    });
    request.once("aborted", cancel);
    const forward = async () => {
      const agent = await authenticatedConnection(options, owned);
      if (cancelled || blocked || stoppingTransport || response.destroyed) throw new Error("backend_owner_uncertain");
      const headers = { ...publicHeaders(request.headers), host: `127.0.0.1:${options.upstreamPort}` };
      const upstream = http.request({ hostname: "127.0.0.1", port: options.upstreamPort,
        method: request.method, path: request.url, headers, agent: agent ?? false });
      owned.request(upstream);
      upstream.once("error", () => {
        error(response, 503, "backend_disconnected", "The owned backend disconnected; reconnect to inspect the operation");
        if (response.headersSent && !response.writableEnded) response.destroy();
        void settle();
      });
      upstream.once("response", reply => {
        response.writeHead(reply.statusCode ?? 502, { ...publicHeaders(reply.headers), "cache-control": "no-store" });
        void pipeline(reply, response).catch(() => {}).finally(settle);
      });
      void pipeline(request, upstream).catch(() => upstream.destroy());
    };
    void forward().catch(() => {
      error(response, 503, "backend_owner_uncertain", "The owned backend could not authenticate; recovery is required");
      void settle();
    });
  });
  server.requestTimeout = 0; // Active native operations own their own finite budgets.
  server.headersTimeout = 15_000;
  server.maxHeadersCount = 64;
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(options.port, "127.0.0.1", () => { server.off("error", reject); resolve(); });
  });
  const port = (server.address() as import("node:net").AddressInfo).port;
  let close: Promise<void> | undefined;
  return {
    port,
    state: () => ({ admission: closing ? "closed" : "open", active }),
    seal: () => { closing = true; },
    block: () => {
      closing = blocked = true;
      for (const cancel of transports) cancel();
      return Promise.all([...drains]).then(() => {});
    },
    close: () => close ??= (async () => {
      closing = stoppingTransport = true;
      // Settlement belongs to upstream Services. Call its authenticated shutdown
      // first, then stop observation transport; no lease release is inferred.
      for (const cancel of transports) cancel();
      await Promise.all([...drains]);
      await new Promise<void>((resolve, reject) => server.close(err => err ? reject(err) : resolve()));
    })().catch(error => { close = undefined; throw error; }),
  };
}
