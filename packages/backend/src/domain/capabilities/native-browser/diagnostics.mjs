// MIT OpenCode; retained provenance in PROVENANCE.json.
import { Browser } from "@opencode/plugin-browser/rpc";
const levels = ["debug", "info", "warning", "error"];
const redacted = ["cookie", "set-cookie", "authorization", "proxy-authorization"];
function createDiagnostics(cdp) {
  const messages = [];
  const requests = /* @__PURE__ */ new Map();
  const hops = /* @__PURE__ */ new Map();
  const latest = (key) => hops.get(key)?.at(-1);
  const extra = /* @__PURE__ */ new Map();
  const scope = crypto.randomUUID();
  let sequence = 0;
  let droppedMessages = 0;
  let droppedRequests = 0;
  const add = (level, text, timestampMs, source) => {
    messages.push({
      id: `${scope}:${++sequence}`,
      timestampMs,
      level,
      text: text.slice(0, 2e3),
      textTruncated: text.length > 2e3,
      ...source ? { source } : {}
    });
    if (messages.length > 500) {
      messages.shift();
      droppedMessages++;
    }
  };
  cdp.on("Runtime.consoleAPICalled", (event) => {
    const source = event.stackTrace?.callFrames[0];
    add(
      event.type === "error" || event.type === "assert" ? "error" : event.type === "warning" ? "warning" : event.type === "debug" ? "debug" : "info",
      event.args.map(
        (arg) => typeof arg.value === "string" ? arg.value : arg.value !== void 0 ? JSON.stringify(arg.value) : arg.description ?? arg.unserializableValue ?? arg.type
      ).join(" "),
      event.timestamp,
      source ? { url: source.url.slice(0, Browser.MAX_TEXT), line: source.lineNumber + 1, column: source.columnNumber + 1 } : void 0
    );
  });
  cdp.on("Log.entryAdded", (event) => {
    const entry = event.entry;
    add(
      entry.level === "verbose" ? "debug" : entry.level,
      entry.text,
      entry.timestamp,
      entry.url ? { url: entry.url.slice(0, Browser.MAX_TEXT), line: (entry.lineNumber ?? 0) + 1, column: 1 } : void 0
    );
  });
  cdp.on("Runtime.exceptionThrown", (event) => {
    const error = event.exceptionDetails;
    add(
      "error",
      error.exception?.description ?? error.text,
      event.timestamp,
      error.url ? { url: error.url, line: error.lineNumber + 1, column: error.columnNumber + 1 } : void 0
    );
  });
  const begin = (key, sessionID, nativeID, started, wallTime, info, request) => {
    const headers = trimHeaders(request.headers);
    const entry = {
      nativeID,
      sessionID,
      started,
      request: { ...request, headers: headers.headers, postData: request.postData?.slice(0, 2e4) },
      headersTruncated: headers.truncated,
      postDataTruncated: (request.postData?.length ?? 0) > 2e4,
      wire: { request: false, response: false },
      info: {
        id: `${scope}:${++sequence}`,
        ...info,
        url: info.url.slice(0, 16384),
        timestampMs: wallTime * 1e3,
        state: "pending"
      }
    };
    requests.set(entry.info.id, entry);
    hops.set(key, [...hops.get(key) ?? [], entry]);
    const stashed = extra.get(key);
    if (stashed?.request) requestHeaders(entry, stashed.request);
    if (stashed?.response) responseInfo(entry, stashed.response);
    extra.delete(key);
    if (requests.size > 500) {
      const first = requests.values().next().value;
      if (first) {
        requests.delete(first.info.id);
        const firstKey = `${first.sessionID ?? ""}:${first.nativeID}`;
        const rest = hops.get(firstKey)?.filter((hop) => hop !== first) ?? [];
        if (rest.length) hops.set(firstKey, rest);
        if (!rest.length) hops.delete(firstKey);
      }
      droppedRequests++;
    }
    return entry;
  };
  const requestHeaders = (request, headers) => {
    const trimmed = trimHeaders({ ...request.request.headers, ...headers });
    request.request = { ...request.request, headers: trimmed.headers };
    request.headersTruncated ||= trimmed.truncated;
    request.wire.request = true;
  };
  const responseInfo = (request, wire) => {
    const trimmed = trimHeaders({ ...request.response?.headers, ...wire.headers });
    request.response = { mimeType: request.response?.mimeType ?? "", headers: trimmed.headers };
    request.headersTruncated ||= trimmed.truncated;
    request.info = { ...request.info, statusCode: wire.statusCode };
    request.wire.response = true;
  };
  const finish = (key, timestamp, failure) => {
    const request = latest(key);
    if (!request) return;
    const durationMs = request.started === void 0 ? 0 : Math.max(0, (timestamp - request.started) * 1e3);
    request.info = failure === void 0 ? { ...request.info, state: "completed", durationMs } : { ...request.info, state: "failed", failure: failure.slice(0, 2048), durationMs };
  };
  cdp.on("Network.requestWillBeSent", (event, sessionID) => {
    const key = `${sessionID ?? ""}:${event.requestId}`;
    const previous = latest(key);
    if (previous && event.redirectResponse) {
      const response = trimHeaders({ ...event.redirectResponse.headers, ...previous.response?.headers });
      previous.response = { mimeType: event.redirectResponse.mimeType, headers: response.headers };
      previous.headersTruncated ||= response.truncated;
      previous.redirected = true;
      if (!event.redirectHasExtraInfo) previous.wire = { request: true, response: true };
      previous.info = {
        ...previous.info,
        state: "completed",
        statusCode: previous.info.statusCode ?? event.redirectResponse.status,
        durationMs: Math.max(0, (event.timestamp - (previous.started ?? event.timestamp)) * 1e3)
      };
    }
    begin(
      key,
      sessionID,
      event.requestId,
      event.timestamp,
      event.wallTime,
      {
        url: event.request.url,
        method: event.request.method,
        resourceType: resourceType((event.type ?? "other").toLowerCase())
      },
      { headers: event.request.headers, hasPostData: event.request.hasPostData, postData: event.request.postData }
    );
  });
  cdp.on("Network.requestWillBeSentExtraInfo", (event, sessionID) => {
    const key = `${sessionID ?? ""}:${event.requestId}`;
    const request = hops.get(key)?.find((hop) => !hop.wire.request);
    if (request) return requestHeaders(request, event.headers);
    extra.set(key, { ...extra.get(key), request: event.headers });
  });
  cdp.on("Network.responseReceived", (event, sessionID) => {
    const request = latest(`${sessionID ?? ""}:${event.requestId}`);
    if (!request) return;
    const headers = trimHeaders({ ...event.response.headers, ...request.response?.headers });
    request.response = { mimeType: event.response.mimeType, headers: headers.headers };
    request.headersTruncated ||= headers.truncated;
    request.info = { ...request.info, statusCode: request.info.statusCode ?? event.response.status };
    if (!event.hasExtraInfo) request.wire = { request: true, response: true };
  });
  cdp.on("Network.responseReceivedExtraInfo", (event, sessionID) => {
    const key = `${sessionID ?? ""}:${event.requestId}`;
    const request = hops.get(key)?.find((hop) => !hop.wire.response);
    if (request) return responseInfo(request, event);
    extra.set(key, { ...extra.get(key), response: event });
  });
  cdp.on("Network.webSocketCreated", (event, sessionID) => {
    begin(
      `${sessionID ?? ""}:${event.requestId}`,
      sessionID,
      event.requestId,
      void 0,
      Date.now() / 1e3,
      { url: event.url, method: "GET", resourceType: "websocket" },
      { headers: {}, hasPostData: false }
    );
  });
  cdp.on("Network.webSocketWillSendHandshakeRequest", (event, sessionID) => {
    const request = latest(`${sessionID ?? ""}:${event.requestId}`);
    if (!request) return;
    request.started = event.timestamp;
    request.info = { ...request.info, timestampMs: event.wallTime * 1e3 };
    requestHeaders(request, event.request.headers);
  });
  cdp.on("Network.webSocketHandshakeResponseReceived", (event, sessionID) => {
    const key = `${sessionID ?? ""}:${event.requestId}`;
    const request = latest(key);
    if (!request) return;
    responseInfo(request, { headers: event.response.headers, statusCode: event.response.status });
    finish(key, event.timestamp);
  });
  cdp.on(
    "Network.webSocketFrameError",
    (event, sessionID) => finish(`${sessionID ?? ""}:${event.requestId}`, event.timestamp, event.errorMessage)
  );
  cdp.on("Network.webSocketClosed", (event, sessionID) => {
    const key = `${sessionID ?? ""}:${event.requestId}`;
    if (latest(key)?.info.state === "pending") finish(key, event.timestamp, "Closed before the handshake completed");
  });
  cdp.on(
    "Network.loadingFinished",
    (event, sessionID) => finish(`${sessionID ?? ""}:${event.requestId}`, event.timestamp)
  );
  cdp.on(
    "Network.loadingFailed",
    (event, sessionID) => finish(`${sessionID ?? ""}:${event.requestId}`, event.timestamp, event.errorText)
  );
  return {
    clear() {
      messages.length = 0;
      requests.clear();
      hops.clear();
      extra.clear();
      droppedMessages = 0;
      droppedRequests = 0;
    },
    async enable(sessionID) {
      await cdp.send("Runtime.enable", {}, sessionID);
      await cdp.send("Log.enable", {}, sessionID);
      await cdp.send(
        "Network.enable",
        { maxTotalBufferSize: 5 * 1024 * 1024, maxResourceBufferSize: 1024 * 1024, maxPostDataSize: 2e4 },
        sessionID
      );
    },
    console(input) {
      const matching = messages.filter((entry) => levels.indexOf(entry.level) >= levels.indexOf(input.level ?? "info"));
      const result = bounded(matching, input.limit ?? 100);
      return { messages: result, truncated: matching.length > result.length, dropped: droppedMessages };
    },
    list(input) {
      const matching = Array.from(requests.values()).map((request) => request.info).filter(
        (request) => (!input.urlContains || request.url.includes(input.urlContains)) && (!input.resourceType || input.resourceType === request.resourceType)
      );
      const result = bounded(matching, input.limit ?? 100);
      return { requests: result, truncated: matching.length > result.length, dropped: droppedRequests };
    },
    info(id) {
      const request = requests.get(id);
      if (!request)
        throw new Error(
          "Request is no longer retained. Call browser.network.list({tabID}) and use a current request id. Do not reload or resend it just to inspect it."
        );
      return request.info;
    },
    async get(input) {
      const request = requests.get(input.id);
      if (!request)
        throw new Error(
          "Request ID is no longer retained in this tab or belongs to another tab. Call browser.network.list({tabID}) and copy a current id into browser.network.get with the same tabID. Do not reload or resend a request just to inspect it."
        );
      const max = input.maxBodyChars ?? 2e4;
      const text = (value) => ({
        state: "text",
        text: value.slice(0, max),
        truncated: value.length > max
      });
      const responseBody = async () => {
        if (!input.includeBody) return { state: "notRequested" };
        if (request.info.state === "pending") return { state: "pending" };
        if (request.redirected || !request.response || request.info.resourceType === "websocket")
          return { state: "unavailable", reason: "notCaptured" };
        if (!/^(text\/|application\/(json|.*\+json|javascript|xml|.*\+xml|x-www-form-urlencoded))/i.test(
          request.response.mimeType
        ))
          return { state: "unavailable", reason: "binary" };
        const body = await cdp.send("Network.getResponseBody", { requestId: request.nativeID }, request.sessionID).catch(() => void 0);
        if (!body) return { state: "unavailable", reason: "backendUnavailable" };
        const value = body.base64Encoded ? Buffer.from(body.body, "base64").toString("utf8") : body.body;
        return value.length ? text(value) : { state: "empty" };
      };
      const requestBody = !input.includeBody ? { state: "notRequested" } : request.request.postData !== void 0 ? {
        state: "text",
        text: request.request.postData.slice(0, max),
        truncated: request.postDataTruncated || request.request.postData.length > max
      } : request.request.hasPostData ? { state: "unavailable", reason: "notCaptured" } : { state: "empty" };
      return {
        request: request.info,
        requestHeaders: headerEntries(request.request.headers),
        responseHeaders: headerEntries(request.response?.headers ?? {}),
        headersTruncated: request.headersTruncated,
        requestBody,
        responseBody: await responseBody()
      };
    }
  };
}
function resourceType(type) {
  switch (type) {
    case "document":
    case "stylesheet":
    case "image":
    case "media":
    case "font":
    case "script":
    case "xhr":
    case "fetch":
    case "eventsource":
    case "websocket":
    case "manifest":
      return type;
    default:
      return "other";
  }
}
function trimHeaders(headers) {
  const entries = Object.entries(headers);
  const kept = [];
  let size = 0;
  let truncated = entries.length > 100;
  for (const [key, value] of entries.slice(0, 100)) {
    const name = key.toLowerCase().slice(0, 2048);
    const text = redacted.includes(name) ? "<redacted>" : String(value);
    const remaining = Math.max(0, 16e3 - size - name.length);
    if (!remaining) {
      truncated = true;
      break;
    }
    const bounded2 = text.slice(0, Math.min(2e3, remaining));
    truncated ||= bounded2.length < text.length || name.length < key.length;
    kept.push([name, bounded2]);
    size += name.length + bounded2.length;
  }
  return { headers: Object.fromEntries(kept), truncated };
}
function bounded(items, limit) {
  const selected = [];
  let size = 0;
  for (const item of items.slice(-limit).reverse()) {
    size += JSON.stringify(item).length;
    if (size > Browser.MAX_TEXT) break;
    selected.push(item);
  }
  return selected.reverse();
}
function headerEntries(headers) {
  return Object.entries(headers).map(([name, value]) => ({ name, value: String(value) }));
}
export {
  createDiagnostics
};
