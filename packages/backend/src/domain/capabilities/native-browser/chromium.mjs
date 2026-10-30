// MIT OpenCode; retained provenance in PROVENANCE.json.
import { Browser } from "@opencode/plugin-browser/rpc";
import electron from "electron";
import { Schema } from "effect";
import { createCdp, abortError, waitFor } from "./cdp.mjs";
import { createBrowserFiles } from "./files.mjs";
import { createDiagnostics } from "./diagnostics.mjs";
import { loadIcon } from "./icon.mjs";
import { createProfiling } from "./profiling.mjs";
import {
  allowedDestination,
  destinationOrigin,
  fileURLWithin,
  localFileURL,
  normalizeURL,
  refusal
} from "./policy.mjs";
const retainedOperations = [
  "navigate",
  "files.list",
  "files.get",
  "trace.stop",
  "trace.analyze",
  "cpu.stop",
  "cpu.analyze",
  "heap.summary",
  "heap.query",
  "heap.object",
  "heap.compare"
];
const pointerOperations = [
  "click",
  "hover",
  "drag",
  "fill",
  "fill_form",
  "select",
  "check",
  "press",
  "scroll",
  "files.drop"
];
const inspectHighlight = {
  showInfo: true,
  showStyles: true,
  showAccessibilityInfo: true,
  colorFormat: "hex",
  contrastAlgorithm: "aa",
  contentColor: { r: 111, g: 168, b: 220, a: 0.66 },
  paddingColor: { r: 147, g: 196, b: 125, a: 0.55 },
  borderColor: { r: 255, g: 229, b: 153, a: 0.66 },
  marginColor: { r: 246, g: 178, b: 107, a: 0.66 },
  eventTargetColor: { r: 255, g: 196, b: 196, a: 0.66 },
  // SAFETY: CDP's Overlay.HighlightConfig names these two fields; they are the protocol's, not ours to rename.
  /* oxlint-disable anti-slop/no-shape-in-symbol-names -- see SAFETY above */
  shapeColor: { r: 96, g: 82, b: 177, a: 0.8 },
  shapeMarginColor: { r: 96, g: 82, b: 127, a: 0.6 }
  /* oxlint-enable anti-slop/no-shape-in-symbol-names */
};
const pickedHighlight = { ...inspectHighlight, showInfo: false, showStyles: false, showAccessibilityInfo: false };
const inspectOff = { mode: "none", highlightConfig: inspectHighlight };
const zoomSteps = [0.25, 0.33, 0.5, 0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4, 5];
function zoomKey(input) {
  if (input.key === "=" || input.key === "+" || input.code === "NumpadAdd") return "in";
  if (input.key === "-" || input.code === "NumpadSubtract") return "out";
  if (input.key === "0") return "reset";
}
function cookieURL(cookie) {
  const domain = (cookie.domain ?? "").replace(/^\./, "");
  const host = domain.includes(":") && !domain.startsWith("[") ? `[${domain}]` : domain;
  return `${cookie.secure ? "https" : "http"}://${host}${cookie.path ?? "/"}`;
}
function zoomStep(current, direction) {
  if (direction === "reset") return 1;
  if (direction === "in") return zoomSteps.find((step) => step > current + 1e-3) ?? current;
  return zoomSteps.findLast((step) => step < current - 1e-3) ?? current;
}
function createBrowserPage(win, options) {
  const policy = {
    get fileRoots() {
      return options.fileRoots?.() ?? [];
    }
  };
  const view = new electron.WebContentsView({
    ...options.popupOptions,
    webPreferences: {
      partition: options.partition,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      webviewTag: false,
      devTools: false,
      backgroundThrottling: false,
      // Agent navigation, including in hidden tabs, must not take the user's keyboard focus.
      focusOnNavigation: false
    }
  });
  const contents = view.webContents;
  const detachNetwork = options.network?.attach(contents);
  contents.on("before-input-event", (event, input) => {
    if (input.type !== "keyDown") return;
    if (input.key === "F5" && !input.meta && !input.control && !input.alt && !input.shift) {
      event.preventDefault();
      contents.reload();
      return;
    }
    if (input.key === "Escape" && inspecting) {
      event.preventDefault();
      void toggleInspect(false);
      return;
    }
    if (input.alt || !(process.platform === "darwin" ? input.meta : input.control)) return;
    if (input.shift && input.code === "KeyC") {
      event.preventDefault();
      void toggleInspect(!inspecting);
      return;
    }
    if (!input.shift && input.code === "KeyL") {
      event.preventDefault();
      options.address?.();
      return;
    }
    const direction = zoomKey(input);
    if (!direction) return;
    event.preventDefault();
    zoom(direction);
  });
  contents.on("zoom-changed", (_event, direction) => zoom(direction));
  const zoom = (direction) => {
    const current = contents.getZoomFactor();
    const next = zoomStep(current, direction);
    if (next === current) return;
    contents.setZoomFactor(next);
    options.zoomed?.();
  };
  let icon;
  let iconRequest = 0;
  let reported = "";
  const detail = () => {
    if (closed) return;
    const next = { zoom: Math.min(5, Math.max(0.25, contents.getZoomFactor())) };
    if (icon) next.icon = icon;
    const key2 = `${next.zoom}:${next.icon ?? ""}`;
    if (key2 === reported) return;
    reported = key2;
    options.detail?.(next);
  };
  contents.on("page-favicon-updated", (_event, favicons) => {
    const request = ++iconRequest;
    void loadIcon(favicons, options.network).then((value) => {
      if (closed || request !== iconRequest) return;
      icon = value;
      detail();
    });
  });
  const cdp = createCdp(contents);
  const documents = /* @__PURE__ */ new Map();
  const sourceURLs = () => [.../* @__PURE__ */ new Set([contents.getURL(), ...documents.values()])].sort();
  const files = createBrowserFiles(sourceURLs);
  const diagnostics = createDiagnostics(cdp);
  const profiling = createProfiling(contents, cdp, files, sourceURLs, options.shared);
  const refs = /* @__PURE__ */ new Map();
  const picked = /* @__PURE__ */ new Map();
  let inspecting = false;
  let picks = 0;
  let flash;
  const sessions = /* @__PURE__ */ new Map();
  const parents = /* @__PURE__ */ new Map();
  const contexts = /* @__PURE__ */ new Map();
  const dialogs = /* @__PURE__ */ new Set();
  let dialog = null;
  let dialogURL = "";
  let dialogRevision = 0;
  let generation = options.restore ? options.restore.generation - 1 : 0;
  let revision = 0;
  cdp.on("Page.frameNavigated", ({ frame }) => {
    documents.set(frame.id, frame.url);
    revision++;
  });
  cdp.on("Page.frameDetached", ({ frameId }) => {
    documents.delete(frameId);
    revision++;
  });
  let closed = false;
  let origin = "";
  let content = false;
  let failure;
  const state = () => {
    const page = {
      id: options.id,
      url: (failure?.url ?? contents.getURL()).slice(0, 16384),
      title: contents.getTitle().slice(0, 2048),
      loading: contents.isLoading()
    };
    const history = {
      canGoBack: contents.navigationHistory.canGoBack(),
      canGoForward: contents.navigationHistory.canGoForward(),
      generation
    };
    return failure ? { ...page, loadError: failure.message, ...history } : { ...page, ...history };
  };
  const publish = () => {
    if (!closed) options.publish();
  };
  const reset = (event) => {
    if (!event.isMainFrame || event.isSameDocument) return;
    failure = void 0;
    generation++;
    documents.clear();
    refs.clear();
    picked.clear();
    diagnostics.clear();
    if (inspecting) void toggleInspect(false);
    publish();
  };
  const settle = () => {
    content = contents.getURL() !== "about:blank" && !failure;
    updateVisibility();
  };
  contents.on("did-start-navigation", reset);
  contents.on("did-navigate", (_event, url, status, statusText) => {
    if (status === 502) failure = { url, message: `${status} ${statusText}`.trim().slice(0, 2048) };
    const next = destinationOrigin(url) ?? url;
    if (next !== origin) {
      icon = void 0;
      iconRequest++;
    }
    origin = next;
    if (url === "about:blank" || failure) settle();
    publish();
    detail();
  });
  contents.on("did-fail-load", (_event, code, description, url, isMainFrame) => {
    if (!isMainFrame || code === -3) return;
    failure = { url, message: description.slice(0, 2048) };
    settle();
    publish();
  });
  contents.on("dom-ready", settle);
  contents.on("did-stop-loading", () => {
    settle();
    publish();
  });
  contents.on("did-navigate-in-page", publish);
  contents.on("page-title-updated", publish);
  contents.on("render-process-gone", () => {
    if (!closed) options.fail();
  });
  contents.debugger.on("detach", () => {
    if (!closed) options.fail();
  });
  contents.session.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  contents.session.setPermissionCheckHandler(() => false);
  contents.session.setDevicePermissionHandler(() => false);
  contents.session.setDisplayMediaRequestHandler((_request, callback) => callback({}));
  contents.on("content-bounds-updated", (event) => event.preventDefault());
  const guard = (event) => {
    if (event.url === "about:blank") return;
    if (event.isMainFrame ? allowedDestination(event.url, policy) : !localFileURL(event.url)) return;
    if (!event.isMainFrame && fileURLWithin(event.url, policy.fileRoots ?? [])) return;
    event.preventDefault();
    options.publish(refusal(event.url, policy) ?? "ERR_BLOCKED_BY_CLIENT");
  };
  contents.on("will-frame-navigate", guard);
  contents.on("will-redirect", guard);
  contents.setWindowOpenHandler(
    ({ url, disposition }) => url === "about:blank" || destinationOrigin(url) ? {
      action: "allow",
      outlivesOpener: true,
      overrideBrowserWindowOptions: {
        webPreferences: {
          nodeIntegration: false,
          contextIsolation: true,
          sandbox: true,
          webSecurity: true,
          webviewTag: false,
          devTools: false,
          // Electron applies these preferences before the popup is adopted by our view.
          focusOnNavigation: false,
          partition: options.partition
        }
      },
      createWindow: (popupOptions) => options.popup(popupOptions, disposition === "background-tab")
    } : { action: "deny" }
  );
  const download = (_event, item, source) => {
    if (source !== contents) return;
    try {
      const file = files.add(item.getFilename(), item.getMimeType() || "application/octet-stream", [
        ...sourceURLs(),
        ...item.getURLChain()
      ]);
      item.setSavePath(file.path);
      item.on("updated", () => {
        file.bytes = item.getReceivedBytes();
        if (file.bytes > Browser.MAX_FILE_BYTES) item.cancel();
      });
      item.once("done", (_event2, status) => {
        file.bytes = item.getReceivedBytes();
        file.state = status === "completed" ? "completed" : "failed";
      });
    } catch {
      item.cancel();
      options.publish("download_failed");
    }
  };
  contents.session.on("will-download", download);
  cdp.on("Runtime.executionContextCreated", ({ context }, sessionID) => {
    const aux = context.auxData;
    if (aux?.frameId && aux.isDefault) contexts.set(aux.frameId, { id: context.id, sessionID });
  });
  cdp.on("Runtime.executionContextDestroyed", ({ executionContextId }, sessionID) => {
    contexts.forEach((context, key2) => {
      if (context.id === executionContextId && context.sessionID === sessionID) contexts.delete(key2);
    });
  });
  cdp.on("Target.attachedToTarget", ({ sessionId, targetInfo }, parentSessionID) => {
    if (targetInfo.type !== "iframe") return;
    const parentID = targetInfo.parentFrameId ?? Array.from(sessions).find(([, id]) => id === parentSessionID)?.[0];
    if (parentID) parents.set(targetInfo.targetId, parentID);
    sessions.set(targetInfo.targetId, sessionId);
    void Promise.all([
      diagnostics.enable(sessionId),
      cdp.send("Page.enable", {}, sessionId),
      cdp.send(
        "Target.setAutoAttach",
        {
          autoAttach: true,
          waitForDebuggerOnStart: false,
          flatten: true,
          filter: [{ type: "iframe", exclude: false }, { exclude: true }]
        },
        sessionId
      ),
      ...inspecting ? [arm(sessionId)] : []
    ]).catch(() => void 0);
  });
  cdp.on("Overlay.inspectNodeRequested", ({ backendNodeId }, sessionID) => {
    if (!inspecting) return;
    void inspected(backendNodeId, sessionID).catch(() => {
      void hideHighlight();
      options.inspect?.({ active: false });
    });
  });
  cdp.on("Target.detachedFromTarget", ({ sessionId }) => {
    sessions.forEach((id, frameID) => {
      if (id === sessionId) {
        sessions.delete(frameID);
        parents.delete(frameID);
      }
    });
  });
  cdp.on("Page.javascriptDialogOpening", (event) => {
    dialogURL = event.url;
    dialogRevision++;
    dialog = {
      type: event.type,
      message: event.message.slice(0, Browser.MAX_TEXT),
      defaultValue: event.defaultPrompt ?? ""
    };
    dialogs.forEach((reject) => reject());
    publish();
  });
  cdp.on("Page.javascriptDialogClosed", () => {
    dialogRevision++;
    dialog = null;
    publish();
  });
  view.setBounds({ x: 0, y: 0, width: 1e3, height: 700 });
  const embed = options.embeds.create(view, win);
  embed.on("visible", (visible) => {
    if (visible || closed) return;
    picks++;
    void (inspecting ? toggleInspect(false) : hideHighlight());
  });
  const updateVisibility = () => embed.show(content);
  const ready = Promise.all([
    files.ready,
    ...options.initialize === false ? [] : [
      contents.loadURL(normalizeURL(options.restore?.url || "about:blank", policy)).catch((error) => {
        if (!options.restore) throw error;
        options.publish(error.message);
      })
    ],
    diagnostics.enable(),
    cdp.send("Page.enable"),
    cdp.send("DOM.enable"),
    cdp.send("Target.setAutoAttach", {
      autoAttach: true,
      waitForDebuggerOnStart: false,
      flatten: true,
      filter: [{ type: "iframe", exclude: false }, { exclude: true }]
    })
  ]).then(() => void 0);
  return {
    view,
    contents,
    state,
    ready,
    /** The host embed the renderer lays this page out with. */
    embed: embed.id,
    async inspect(enabled) {
      if (closed) return;
      await ready;
      await toggleInspect(enabled);
    },
    async highlight(ref) {
      if (closed) return;
      await highlightPicked(ref).catch(() => void 0);
    },
    zoom(direction) {
      if (!closed) zoom(direction);
    },
    async site() {
      const url = contents.getURL();
      if (closed || !destinationOrigin(url)) return { cookies: 0 };
      return { cookies: (await contents.session.cookies.get({ url })).length };
    },
    /**
     * Deletes what the page's site stored: the cookies its address can read, and its origin's storage. Resolves once
     * the page reloaded without them, so a count read next includes what the reload set again.
     */
    async clearSite() {
      const url = contents.getURL();
      const origin2 = destinationOrigin(url);
      if (closed || !origin2) return;
      const cookies = await contents.session.cookies.get({ url });
      await Promise.all(cookies.map((cookie) => contents.session.cookies.remove(cookieURL(cookie), cookie.name)));
      await contents.session.clearStorageData({
        origin: origin2,
        storages: ["localstorage", "indexdb", "serviceworkers", "cachestorage", "filesystem", "shadercache"]
      });
      if (closed) return;
      contents.reload();
      await waitFor(() => closed || !contents.isLoading(), new AbortController().signal, 3e4).catch(() => void 0);
    },
    /** Reports the page's icon and zoom when either changed since the last report. */
    detail,
    async execute(command, signal) {
      await ready;
      abortError(signal);
      if (closed)
        throw new Error(
          "Browser tab was closed. Call browser.tabs.list({}) and choose an existing tabID; do not reuse the closed tab's refs."
        );
      if (inspecting && pointerOperations.includes(command.action.type)) await toggleInspect(false);
      if (dialog && command.action.type !== "dialog")
        throw new Error(
          'A JavaScript dialog is open. Inspect it with browser.dialog({tabID,action:"get"}), then explicitly accept or dismiss it before continuing.'
        );
      if (command.inspect) return { value: await inspect(command.action), files: [] };
      if (command.target && JSON.stringify(await inspect(command.action)) !== JSON.stringify(command.target))
        throw new Error(
          "Browser target changed while permission was pending. Take a fresh snapshot or listing and request the action again; it was not executed."
        );
      if (command.generation !== void 0 && command.generation !== generation && !retainedOperations.includes(command.action.type))
        throw new Error(
          "The document changed before this operation ran. Call browser.tabs.list({}) to check its current URL, then browser.snapshot({tabID}) for fresh refs. Reconsider the action before retrying on the new page."
        );
      const modal = Promise.withResolvers();
      const cancelled = Promise.withResolvers();
      const run = new AbortController();
      const cancel = () => {
        run.abort();
        cancelled.reject(
          new Error(
            "Browser operation was cancelled. Inspect the tab before deciding to repeat an action; cancellation does not undo changes already made."
          )
        );
      };
      signal.addEventListener("abort", cancel, { once: true });
      const reject = () => {
        if (command.action.type !== "navigate") run.abort();
        modal.reject(
          new Error(
            'A JavaScript dialog opened while the action was running. Inspect it with browser.dialog({tabID,action:"get"}) and accept or dismiss it. Do not repeat the original action just to close the dialog.'
          )
        );
      };
      if (command.action.type !== "dialog") dialogs.add(reject);
      try {
        return await Promise.race([
          execute(command.action, command.files, run.signal, command.target),
          modal.promise,
          cancelled.promise
        ]);
      } finally {
        signal.removeEventListener("abort", cancel);
        dialogs.delete(reject);
      }
    },
    async dispose() {
      if (closed) return;
      closed = true;
      clearTimeout(flash);
      detachNetwork?.();
      contents.session.off("will-download", download);
      await profiling.dispose();
      cdp.dispose();
      refs.clear();
      picked.clear();
      embed.dispose();
      if (!contents.isDestroyed()) contents.close({ waitForBeforeUnload: false });
      await files.dispose();
    }
  };
  async function execute(action, transfers, signal, approved) {
    const captureSources = sourceURLs();
    const transfer = (id) => files.transfer(id, approved?.resources);
    const result = (value, attached = []) => {
      const json = Schema.decodeUnknownSync(Schema.Json)(value);
      if (JSON.stringify(json).length > 512e3)
        throw new Error(
          "Browser result exceeds 512000 JSON characters. Request fewer entries, reduce snapshot depth, or return only selected fields from the evaluation script. Repeating the same request will not reduce its output."
        );
      return { value: json, files: attached };
    };
    switch (action.type) {
      case "navigate": {
        const url = normalizeURL(action.url, policy);
        const cancel = () => contents.stop();
        signal.addEventListener("abort", cancel, { once: true });
        try {
          await contents.loadURL(url);
        } finally {
          signal.removeEventListener("abort", cancel);
        }
        abortError(signal);
        return result(state());
      }
      case "back":
      case "forward":
      case "reload":
      case "stop": {
        if (action.type === "back" && contents.navigationHistory.canGoBack()) contents.navigationHistory.goBack();
        if (action.type === "forward" && contents.navigationHistory.canGoForward())
          contents.navigationHistory.goForward();
        if (action.type === "reload") contents.reload();
        if (action.type === "stop") contents.stop();
        if (action.type !== "stop") await waitFor(() => !contents.isLoading(), signal, 3e4);
        return result(state());
      }
      case "frames":
        return result({ tab: state(), frames: await frames() });
      case "snapshot":
      case "find":
        return result({ tab: state(), ...await snapshot(action) });
      case "evaluate": {
        if (action.ref && action.frameID)
          throw new Error(
            "Pass either ref or frameID to browser.evaluate, not both. A ref already runs in its element's frame."
          );
        const context = action.frameID ? contexts.get(action.frameID) : void 0;
        if (action.frameID && !context)
          throw new Error(
            "Frame context is unavailable. Call browser.frames({tabID}) and use a current frameID from this tab, or omit frameID to target the main frame."
          );
        const element = action.ref ? target(action.ref) : void 0;
        const objectId = element ? await resolve(element) : void 0;
        const value = await (element && objectId ? cdp.send(
          "Runtime.callFunctionOn",
          {
            objectId,
            functionDeclaration: action.script,
            arguments: [{ objectId }],
            awaitPromise: true,
            returnByValue: true,
            userGesture: true
          },
          element.sessionID
        ).finally(() => cdp.send("Runtime.releaseObject", { objectId }, element.sessionID).catch(() => void 0)) : cdp.send(
          "Runtime.evaluate",
          {
            expression: action.script,
            contextId: context?.id,
            awaitPromise: true,
            returnByValue: true,
            userGesture: true
          },
          context?.sessionID
        ));
        if (value.exceptionDetails)
          throw new Error(
            `Page JavaScript threw an exception. Check the script and ${action.ref ? "ref" : "frameID"}; inspect the page before repeating code with side effects. Details: ${(value.exceptionDetails.exception?.description ?? value.exceptionDetails.text).slice(0, 800)}`
          );
        abortError(signal);
        return result({ tab: state(), value: value.result.value ?? null });
      }
      case "click":
        await click(target(action.ref), action.button ?? "left", action.count ?? 1, action.modifiers);
        break;
      case "hover":
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...await point(target(action.ref)) });
        break;
      case "drag": {
        const source = target(action.from);
        const destination = target(action.to);
        await point(destination);
        const from = await point(source);
        const box = await rect(destination);
        const to = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
        const html5 = await call(source, "function() { return this.draggable; }");
        let data;
        const off = cdp.on("Input.dragIntercepted", (event) => {
          data = event.data;
        });
        await cdp.send("Input.setInterceptDrags", { enabled: true });
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...from });
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mousePressed",
          ...from,
          button: "left",
          buttons: 1,
          clickCount: 1
        });
        try {
          for (let i = 1; i <= 10; i++) {
            abortError(signal);
            await cdp.send("Input.dispatchMouseEvent", {
              type: "mouseMoved",
              x: from.x + (to.x - from.x) * i / 10,
              y: from.y + (to.y - from.y) * i / 10,
              button: "left",
              buttons: 1
            });
          }
          if (html5) await waitFor(() => data !== void 0, signal, 2e3);
          if (data) {
            for (const type of ["dragEnter", "dragOver", "drop"])
              await cdp.send("Input.dispatchDragEvent", { type, ...to, data });
          }
        } finally {
          off();
          await cdp.send("Input.setInterceptDrags", { enabled: false });
          await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", ...to, button: "left", clickCount: 1 });
        }
        break;
      }
      case "fill":
        await fill(target(action.ref), action.text, signal);
        break;
      case "fill_form":
        for (const field of action.fields) {
          abortError(signal);
          if (field.type === "text") await fill(target(field.ref), field.value, signal);
          if (field.type === "select") await select(target(field.ref), field.values);
          if (field.type === "check") await check(target(field.ref), field.checked);
        }
        break;
      case "select":
        await select(target(action.ref), action.values);
        break;
      case "check":
        await check(target(action.ref), action.checked);
        break;
      case "press":
        await key(action.key);
        break;
      case "scroll": {
        const bounds = view.getBounds();
        await cdp.send("Input.dispatchMouseEvent", {
          type: "mouseWheel",
          x: bounds.width / 2,
          y: bounds.height / 2,
          deltaX: action.deltaX ?? 0,
          deltaY: action.deltaY
        });
        break;
      }
      case "wait": {
        if (action.condition !== "load" && !action.text)
          throw new Error(
            'browser.wait requires non-empty text for condition "text" or "textGone". Use condition "load" without text to wait for loading.'
          );
        await waitFor(
          async () => {
            if (action.condition === "load") return !contents.isLoading();
            const context = action.frameID ? contexts.get(action.frameID) : void 0;
            if (action.frameID && !context)
              throw new Error(
                "Frame context is unavailable. Call browser.frames({tabID}) and use a frameID from this tab."
              );
            const value = await cdp.send(
              "Runtime.evaluate",
              {
                expression: `document.body?.innerText.includes(${JSON.stringify(action.text)}) ?? false`,
                returnByValue: true,
                contextId: context?.id
              },
              context?.sessionID
            );
            return Boolean(value.result.value) === (action.condition === "text");
          },
          signal,
          action.timeoutMs
        ).catch((error) => {
          if (signal.aborted) throw error;
          throw new Error(
            `browser.wait failed for condition ${JSON.stringify(action.condition)} (timeoutMs: ${action.timeoutMs ?? 1e4}). Inspect browser.snapshot({tabID}) and check text/frameID before retrying; timeoutMs can be increased up to 30000 for a genuinely slow page. Details: ${error instanceof Error ? error.message : String(error)}`
          );
        });
        break;
      }
      case "screenshot": {
        if (action.ref && action.fullPage)
          throw new Error(
            "Choose either ref for an element screenshot or fullPage:true for the whole page. Remove the other argument before retrying."
          );
        await waitFor(() => view.getVisible() && win.isVisible() && !win.isMinimized(), signal, 3e3).catch(
          (error) => {
            if (signal.aborted) throw error;
            throw new Error(
              "Screenshot needs a visible tab. Call browser.tabs.focus and keep its desktop window visible."
            );
          }
        );
        const element = action.ref ? await rect(target(action.ref), true) : void 0;
        const metrics = await cdp.send("Page.getLayoutMetrics");
        const bounds = element ? {
          ...element,
          x: element.x + metrics.cssVisualViewport.pageX,
          y: element.y + metrics.cssVisualViewport.pageY
        } : action.fullPage ? metrics.cssContentSize : {
          x: metrics.cssVisualViewport.pageX,
          y: metrics.cssVisualViewport.pageY,
          width: metrics.cssVisualViewport.clientWidth,
          height: metrics.cssVisualViewport.clientHeight
        };
        const pixelRatio = contents.getZoomFactor() * electron.screen.getDisplayMatching(win.getBounds()).scaleFactor;
        const scale = Math.min(1, (action.maxWidth ?? 2e3) / (bounds.width * pixelRatio));
        if (bounds.width <= 0 || bounds.height <= 0)
          throw new Error(
            "Element or page has no visible screenshot area. Take a fresh snapshot and choose a visible element, or omit ref to capture the viewport."
          );
        if (bounds.width * bounds.height * (scale * pixelRatio) ** 2 > 16e6)
          throw new Error("Screenshot exceeds 16 megapixels; capture an element or use a smaller maxWidth.");
        const format = action.format ?? "png";
        const capture = await cdp.send("Page.captureScreenshot", {
          format,
          quality: format === "png" ? void 0 : action.quality ?? 80,
          captureBeyondViewport: true,
          clip: { ...bounds, scale }
        });
        const id = await files.save(`screenshot.${format}`, `image/${format}`, Buffer.from(capture.data, "base64"), [
          ...captureSources,
          ...sourceURLs()
        ]);
        return result({ tab: state() }, [await transfer(id)]);
      }
      case "dialog": {
        if (action.action !== "get") {
          if (!dialog)
            throw new Error(
              'This tab has no JavaScript dialog to handle. browser.dialog({tabID,action:"get"}) returns null when none is open; continue without accepting or dismissing one.'
            );
          await cdp.send("Page.handleJavaScriptDialog", {
            accept: action.action === "accept",
            promptText: action.promptText
          });
          dialog = null;
        }
        return result({ tab: state(), dialog });
      }
      case "files.upload":
      case "files.drop": {
        if (!transfers.length)
          throw new Error(
            "Upload command has no file bytes. Supply server-local paths to browser.files.upload/drop; do not call the desktop RPC directly with desktop paths. If paths were supplied, report a client/server transfer mismatch."
          );
        const local = await Promise.all(
          transfers.map(async (file) => files.get(await files.save(file.name, file.mime, file.data)).path)
        );
        const element = target(action.ref);
        if (action.type === "files.upload")
          await cdp.send("DOM.setFileInputFiles", { files: local, backendNodeId: element.backendID }, element.sessionID);
        if (action.type === "files.drop") {
          const position = await point(element);
          for (const type of ["dragEnter", "dragOver", "drop"])
            await cdp.send("Input.dispatchDragEvent", {
              type,
              ...position,
              data: { items: [], files: local, dragOperationsMask: 1 }
            });
        }
        break;
      }
      case "files.list":
        return result({ tab: state(), files: files.list() });
      case "files.get":
        return result({ tab: state() }, [await transfer(action.fileID)]);
      case "console":
        return result({ tab: state(), ...diagnostics.console(action) });
      case "network.list":
        return result({ tab: state(), ...diagnostics.list(action) });
      case "network.get":
        return result({ tab: state(), ...await diagnostics.get(action) });
      case "trace.start":
        await profiling.startTrace(action.durationMs);
        return result({ tab: state(), recording: true });
      case "trace.stop": {
        const value = await profiling.stopTrace();
        return result({ tab: state(), durationMs: value.durationMs, incomplete: value.incomplete }, [
          await transfer(value.id)
        ]);
      }
      case "cpu.start":
        await profiling.startCpu();
        return result({ tab: state(), recording: true });
      case "cpu.stop": {
        const value = await profiling.stopCpu();
        return result({ tab: state(), durationMs: value.durationMs }, [await transfer(value.id)]);
      }
      case "heap.snapshot":
        return result({ tab: state() }, [await transfer(await profiling.heap())]);
      case "trace.analyze":
      case "cpu.analyze":
      case "heap.summary":
      case "heap.query":
      case "heap.object":
      case "heap.compare":
        return result({ tab: state(), ...await profiling.analyze(action) });
      case "lighthouse": {
        const { audit } = await import("./lighthouse");
        const report = await audit(contents, files, cdp, captureSources);
        return result(
          { tab: state(), scores: report.scores, failures: report.failures },
          await Promise.all(report.files.map(transfer))
        );
      }
      default:
        throw new Error(
          "This operation was routed to a page instead of the tab manager. Report a desktop/plugin routing mismatch; changing tab IDs or repeating the operation will not fix it."
        );
    }
    abortError(signal);
    return result(state());
  }
  async function inspect(action) {
    if (action.type === "dialog")
      return {
        resources: [dialog ? dialogURL : contents.getURL()],
        key: `${generation}:${dialogRevision}:${Boolean(dialog)}`
      };
    const fileIDs = action.type === "heap.compare" ? [action.before, action.after] : "fileID" in action ? [action.fileID] : [];
    if (fileIDs.length)
      return {
        resources: [...new Set(fileIDs.flatMap((id) => files.get(id).resources))].sort(),
        key: JSON.stringify(fileIDs)
      };
    if (action.type === "network.get") return { resources: [diagnostics.info(action.id).url], key: action.id };
    if (action.type === "trace.stop" || action.type === "cpu.stop")
      return profiling.target(action.type === "trace.stop" ? "trace" : "cpu");
    const tree = await frames();
    tree.forEach((frame) => documents.set(frame.id, frame.url));
    const refs2 = action.type === "drag" ? [action.from, action.to] : action.type === "fill_form" ? action.fields.map((field) => field.ref) : "ref" in action && action.ref ? [action.ref] : [];
    const selected = refs2.map(target);
    const frameIDs = selected.length ? selected.map((element) => element.frameID) : "frameID" in action && action.frameID ? [action.frameID] : [];
    const urls = frameIDs.map((id) => {
      const frame = tree.find((frame2) => frame2.id === id);
      if (!frame) throw new Error("Frame is unavailable. Call browser.frames({tabID}) and use a current frameID.");
      return frame.url;
    });
    const capture = ["screenshot", "lighthouse", "trace.start", "cpu.start", "heap.snapshot"].includes(action.type);
    return {
      resources: [
        ...new Set(
          action.type === "navigate" ? [new URL(normalizeURL(action.url, policy)).href] : capture ? sourceURLs() : urls.length ? urls : [contents.getURL()]
        )
      ].sort(),
      key: JSON.stringify([generation, revision, selected])
    };
  }
  function target(ref) {
    const key2 = ref.replace(/^@/, "");
    const value = refs.get(key2) ?? picked.get(key2);
    if (!value)
      throw new Error(
        "Element ref is stale or belongs to another tab. Call browser.snapshot({tabID}) and use a ref from that tab's newest snapshot. Do not reuse refs after navigation or a newer snapshot."
      );
    return value;
  }
  async function frames() {
    const root = await cdp.send("Page.getFrameTree");
    const result = [];
    const walk = (tree, parentID) => {
      if (!result.some((frame) => frame.id === tree.frame.id))
        result.push(
          tree.frame.parentId || parentID ? {
            id: tree.frame.id,
            parentID: tree.frame.parentId ?? parentID,
            url: tree.frame.url,
            name: tree.frame.name ?? ""
          } : { id: tree.frame.id, url: tree.frame.url, name: tree.frame.name ?? "" }
        );
      tree.childFrames?.forEach((child) => walk(child, tree.frame.id));
    };
    walk(root.frameTree);
    const children = await Promise.all(
      Array.from(sessions, async ([id, sessionID]) => ({
        id,
        tree: await cdp.send("Page.getFrameTree", {}, sessionID).catch(() => void 0)
      }))
    );
    children.forEach(({ id, tree }) => {
      if (tree) walk(tree.frameTree, parents.get(id) ?? root.frameTree.frame.id);
    });
    return result;
  }
  async function call(element, functionDeclaration, args = []) {
    const objectId = await resolve(element);
    try {
      const result = await cdp.send(
        "Runtime.callFunctionOn",
        {
          objectId,
          functionDeclaration,
          arguments: args.map((value) => ({ value })),
          returnByValue: true,
          awaitPromise: true,
          userGesture: true
        },
        element.sessionID
      );
      if (result.exceptionDetails)
        throw new Error(result.exceptionDetails.exception?.description ?? result.exceptionDetails.text);
      return result.result.value;
    } finally {
      await cdp.send("Runtime.releaseObject", { objectId }, element.sessionID).catch(() => void 0);
    }
  }
  async function resolve(element) {
    const object = await cdp.send("DOM.resolveNode", { backendNodeId: element.backendID }, element.sessionID);
    if (!object.object.objectId)
      throw new Error(
        "Element is no longer available. Call browser.snapshot({tabID}) and use a fresh ref; the page may have replaced the element."
      );
    return object.object.objectId;
  }
  async function rect(element, scroll = false) {
    if (scroll) {
      await cdp.send("DOM.scrollIntoViewIfNeeded", { backendNodeId: element.backendID }, element.sessionID);
      await contents.capturePage(void 0, { stayHidden: false, stayAwake: true });
    }
    const bounds = Schema.Struct({ x: Schema.Finite, y: Schema.Finite, width: Schema.Finite, height: Schema.Finite });
    const value = {
      ...Schema.decodeUnknownSync(bounds)(
        await call(
          element,
          "function() { const r = this.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; }"
        )
      )
    };
    const tree = await frames();
    let frame = tree.find((frame2) => frame2.id === element.frameID);
    while (frame?.parentID) {
      const parent = { frameID: frame.parentID, sessionID: sessionFor(frame.parentID, tree) };
      const owner = await cdp.send("DOM.getFrameOwner", { frameId: frame.id }, parent.sessionID);
      const box = Schema.decodeUnknownSync(
        Schema.Struct({ ...bounds.fields, scaleX: Schema.Finite, scaleY: Schema.Finite })
      )(
        await call(
          { backendID: owner.backendNodeId, ...parent },
          "function() { const r = this.getBoundingClientRect(); const sx = this.offsetWidth ? r.width / this.offsetWidth : 1; const sy = this.offsetHeight ? r.height / this.offsetHeight : 1; return {x:r.x+this.clientLeft*sx,y:r.y+this.clientTop*sy,width:r.width,height:r.height,scaleX:sx,scaleY:sy}; }"
        )
      );
      value.x = box.x + value.x * box.scaleX;
      value.y = box.y + value.y * box.scaleY;
      value.width *= box.scaleX;
      value.height *= box.scaleY;
      frame = tree.find((item) => item.id === frame?.parentID);
    }
    return value;
  }
  function sessionFor(frameID, tree) {
    let id = frameID;
    while (id && !sessions.has(id)) id = tree.find((frame) => frame.id === id)?.parentID;
    return id ? sessions.get(id) : void 0;
  }
  async function point(element) {
    const box = await rect(element, true);
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  }
  async function click(element, button = "left", count = 1, modifiers = []) {
    const position = await point(element);
    const flags = modifiers.reduce((mask, key2) => mask | ({ Alt: 1, Control: 2, Meta: 4, Shift: 8 }[key2] ?? 0), 0);
    await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved", ...position, modifiers: flags });
    for (let clickCount = 1; clickCount <= count; clickCount++) {
      await cdp.send("Input.dispatchMouseEvent", {
        type: "mousePressed",
        ...position,
        button,
        clickCount,
        modifiers: flags
      });
      await cdp.send("Input.dispatchMouseEvent", {
        type: "mouseReleased",
        ...position,
        button,
        clickCount,
        modifiers: flags
      });
    }
  }
  async function fill(element, value, signal) {
    const kind = await call(
      element,
      "function() { if (this.disabled || this.readOnly) return; if (this instanceof HTMLTextAreaElement || this.isContentEditable) return 'text'; if (!(this instanceof HTMLInputElement)) return; if (['date','time','datetime-local','month','week'].includes(this.type)) return 'structured'; if (!['file','checkbox','radio','button','submit','reset','image','hidden','range','color'].includes(this.type)) return 'text'; }"
    );
    if (!kind)
      throw new Error(
        "Target is not an enabled editable text field. Take a fresh snapshot and choose a textbox; use browser.select for dropdowns, browser.check for checkboxes/radios, or browser.files.upload for file inputs."
      );
    if (kind === "structured") {
      await call(
        element,
        "function(value) { const previous = this.value; this.focus(); this.value = value; if (this.value !== value) { this.value = previous; throw new Error('The ' + this.type + ' input rejected this value and keeps its previous one. Use its required format, for example 2026-09-07 for date, 14:45 for time, 2026-09-07T14:45 for datetime-local, 2026-09 for month, or 2026-W37 for week.'); } this.dispatchEvent(new Event('input',{bubbles:true})); this.dispatchEvent(new Event('change',{bubbles:true})); }",
        [value]
      );
      return;
    }
    await cdp.send("DOM.focus", { backendNodeId: element.backendID }, element.sessionID);
    abortError(signal);
    await key(process.platform === "darwin" ? "Meta+A" : "Control+A");
    await key("Backspace");
    abortError(signal);
    await cdp.send("Input.insertText", { text: value });
  }
  async function select(element, values) {
    await call(
      element,
      `function(values) { if (!(this instanceof HTMLSelectElement) || this.disabled) throw new Error('Target is not an enabled HTML select. Take a fresh snapshot and choose an enabled dropdown ref.'); if (!this.multiple && values.length !== 1) throw new Error('This dropdown accepts exactly one value; pass a one-item values array.'); for (const value of values) if (!Array.from(this.options).some(option => option.value === value && !option.disabled)) throw new Error('Option value was not found or is disabled. Inspect option values with browser.evaluate before retrying browser.select; values are not visible labels.'); for (const option of this.options) option.selected = values.includes(option.value); this.dispatchEvent(new Event('input',{bubbles:true})); this.dispatchEvent(new Event('change',{bubbles:true})); }`,
      [values]
    );
  }
  async function check(element, checked) {
    const current = await call(
      element,
      "function(checked) { if (!(this instanceof HTMLInputElement) || !['checkbox','radio'].includes(this.type) || this.disabled) throw new Error('Target is not an enabled checkbox or radio. Take a fresh snapshot and choose the correct ref.'); if (this.type === 'radio' && this.checked && !checked) throw new Error('A selected radio cannot be cleared by clicking it. Select a different radio in its group instead.'); return this.checked; }",
      [checked]
    );
    if (current !== checked) await click(element);
    if (await call(element, "function() { return this.checked; }") !== checked)
      throw new Error(
        "The page did not keep the requested checked state. Inspect the current snapshot and page validation before retrying; do not blindly toggle the control again."
      );
  }
  async function key(chord) {
    if (!chord)
      throw new Error(
        "A key is required. Use a named key such as Enter or ArrowDown, a single character, or a chord such as Control+A."
      );
    const parts = (chord.endsWith("+") ? chord.slice(0, -1) : chord).split("+");
    const key2 = parts.pop() || "+";
    const modifiers = parts.reduce((mask, key3) => {
      const bit = { Alt: 1, Control: 2, Meta: 4, Shift: 8 }[key3];
      if (!bit)
        throw new Error(
          `Unknown key modifier ${JSON.stringify(key3)}. Supported modifiers are Alt, Control, Meta, and Shift; for example Control+A. Use Meta for macOS command shortcuts.`
        );
      return mask | bit;
    }, 0);
    const codes = {
      Enter: 13,
      Tab: 9,
      Escape: 27,
      Backspace: 8,
      Delete: 46,
      ArrowUp: 38,
      ArrowDown: 40,
      ArrowLeft: 37,
      ArrowRight: 39,
      PageUp: 33,
      PageDown: 34,
      Home: 36,
      End: 35,
      Space: 32
    };
    const code = codes[key2] ?? (key2.length === 1 ? key2.toUpperCase().charCodeAt(0) : /^F([1-9]|1[0-2])$/.test(key2) ? 111 + Number(key2.slice(1)) : void 0);
    if (code === void 0)
      throw new Error(
        `Unknown key ${JSON.stringify(key2)}. Use Enter, Tab, Escape, Backspace, Delete, ArrowUp/Down/Left/Right, PageUp/Down, Home, End, Space, F1\u2013F12, or one character. Use browser.fill for text.`
      );
    const text = key2 === "Enter" ? "\r" : key2 === "Space" ? " " : key2.length === 1 ? key2 : void 0;
    const event = { key: key2 === "Space" ? " " : key2, windowsVirtualKeyCode: code, modifiers };
    const params = text !== void 0 && !(modifiers & 6) ? { ...event, text } : event;
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", ...params });
    await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", ...params });
  }
  async function snapshot(action) {
    const tree = await frames();
    const selected = action.type === "snapshot" && action.ref ? target(action.ref) : void 0;
    const frameID = selected?.frameID ?? action.frameID ?? tree[0]?.id;
    if (!frameID || !tree.some((frame) => frame.id === frameID))
      throw new Error(
        "Frame is unavailable. Call browser.frames({tabID}) and use a current frameID from this tab; omit frameID for the main frame."
      );
    const sessionID = sessionFor(frameID, tree);
    const depth = action.type === "snapshot" ? action.depth ?? 8 : 8;
    const ax = await cdp.send("Accessibility.getFullAXTree", { frameId: frameID, depth }, sessionID);
    const nodes = new Map(ax.nodes.map((node) => [node.nodeId, node]));
    const root = selected ? ax.nodes.find((node) => node.backendDOMNodeId === selected.backendID) : ax.nodes[0];
    if (!root)
      throw new Error(
        "Element is absent from this frame's accessibility snapshot. Retry browser.snapshot with the same tabID and no ref to refresh the frame, then choose a returned ref."
      );
    refs.clear();
    const pinned = new Map(Array.from(picked, ([ref, element]) => [`${element.frameID}:${element.backendID}`, ref]));
    const lines = [];
    let truncated = false;
    const walk = async (node, level) => {
      if (level > depth || lines.length >= 500) {
        truncated = true;
        return;
      }
      const role = String(node.role?.value ?? "node").replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 40);
      const properties = new Map(node.properties?.map((property) => [property.name, property.value.value]) ?? []);
      if (!node.ignored) {
        const actionable = role !== "RootWebArea" && (properties.get("focusable") || /^(button|link|textbox|combobox|checkbox|radio|option)$/.test(role));
        const known = node.backendDOMNodeId ? pinned.get(`${frameID}:${node.backendDOMNodeId}`) : void 0;
        const ref = known ?? (actionable && node.backendDOMNodeId ? options.shared.ref() : "");
        const element = node.backendDOMNodeId ? { backendID: node.backendDOMNodeId, frameID, sessionID } : void 0;
        if (ref && element && !known) refs.set(ref, element);
        const flags = ["checked", "disabled", "expanded", "selected"].flatMap(
          (name) => properties.has(name) ? [`${name}=${properties.get(name)}`] : []
        );
        const box = action.type === "snapshot" && action.boxes && ref && element ? await rect(element).catch(() => void 0) : void 0;
        lines.push(
          `${"  ".repeat(level)}${ref ? `@${ref} ` : ""}[${role}] ${JSON.stringify(
            String(node.name?.value ?? "").replace(/\s+/g, " ").slice(0, 300)
          )} ${flags.join(" ")}${box ? ` box=${JSON.stringify(box)}` : ""}`
        );
      }
      if (["textbox", "searchbox"].includes(role) || properties.get("editable")) return;
      for (const childID of node.childIds ?? []) {
        const child = nodes.get(childID);
        if (child) await walk(child, level + 1);
      }
    };
    await walk(root, 0);
    const content2 = (action.type === "find" ? lines.filter((line) => line.toLowerCase().includes(action.text.toLowerCase())) : lines).join("\n");
    return { content: content2.slice(0, Browser.MAX_TEXT), truncated: truncated || content2.length > Browser.MAX_TEXT };
  }
  async function toggleInspect(enabled) {
    picks++;
    if (enabled !== inspecting) {
      inspecting = enabled;
      clearTimeout(flash);
      await Promise.all(
        [void 0, ...sessions.values()].map(
          (sessionID) => (enabled ? arm(sessionID) : cdp.send("Overlay.setInspectMode", inspectOff, sessionID)).catch(() => void 0)
        )
      );
      if (!enabled) await hideHighlight();
    }
    options.inspect?.({ active: inspecting });
  }
  async function arm(sessionID) {
    if (sessionID) await cdp.send("DOM.enable", {}, sessionID);
    await cdp.send("Overlay.enable", {}, sessionID);
    if (!inspecting) return;
    await cdp.send("Overlay.setInspectMode", { mode: "searchForNode", highlightConfig: inspectHighlight }, sessionID);
  }
  async function inspected(backendID, sessionID) {
    inspecting = false;
    const pick = ++picks;
    const navigation = generation;
    await Promise.all(
      [void 0, ...sessions.values()].map(
        (id) => cdp.send("Overlay.setInspectMode", inspectOff, id).catch(() => void 0)
      )
    );
    await cdp.send("Overlay.highlightNode", { backendNodeId: backendID, highlightConfig: pickedHighlight }, sessionID);
    const element = { backendID, frameID: await frameOf(backendID, sessionID), sessionID };
    const [details, box, accessible] = await Promise.all([describe(element), rect(element), accessibility(element)]);
    await painted(sessionID);
    if (closed) return;
    if (pick !== picks || navigation !== generation) {
      if (!inspecting) await hideHighlight();
      options.inspect?.({ active: inspecting });
      return;
    }
    const ref = options.shared.ref();
    picked.set(ref, element);
    const zoom2 = contents.getZoomFactor();
    options.inspect?.({
      active: false,
      element: {
        ref: Browser.Ref.make(ref),
        ...details,
        ...accessible,
        rect: { x: box.x * zoom2, y: box.y * zoom2, width: box.width * zoom2, height: box.height * zoom2 }
      }
    });
  }
  async function highlightPicked(ref) {
    clearTimeout(flash);
    const element = ref ? picked.get(ref.replace(/^@/, "")) : void 0;
    if (!element) return hideHighlight();
    await cdp.send("DOM.scrollIntoViewIfNeeded", { backendNodeId: element.backendID }, element.sessionID);
    await cdp.send(
      "Overlay.highlightNode",
      { backendNodeId: element.backendID, highlightConfig: pickedHighlight },
      element.sessionID
    );
    flash = setTimeout(() => void hideHighlight(), 1500);
  }
  async function hideHighlight() {
    await Promise.all(
      [void 0, ...sessions.values()].map(
        (sessionID) => cdp.send("Overlay.hideHighlight", {}, sessionID).catch(() => void 0)
      )
    );
  }
  async function frameOf(backendID, sessionID) {
    const tree = await frames();
    const owned = tree.filter((frame) => sessionFor(frame.id, tree) === sessionID);
    const root = owned.find((frame) => !frame.parentID || sessionFor(frame.parentID, tree) !== sessionID) ?? tree[0];
    const nested = owned.filter((frame) => frame !== root);
    if (!nested.length) return root.id;
    const objectGroup = `frame-of-${crypto.randomUUID()}`;
    const described = await (async () => {
      const node = await cdp.send("DOM.resolveNode", { backendNodeId: backendID, objectGroup }, sessionID);
      const document = node.object.objectId ? await cdp.send(
        "Runtime.callFunctionOn",
        {
          objectId: node.object.objectId,
          functionDeclaration: "function() { return this.ownerDocument; }",
          objectGroup
        },
        sessionID
      ) : void 0;
      return document?.result.objectId ? await cdp.send("DOM.describeNode", { objectId: document.result.objectId }, sessionID) : void 0;
    })().finally(() => void cdp.send("Runtime.releaseObjectGroup", { objectGroup }, sessionID).catch(() => void 0));
    const owners = await Promise.all(
      nested.map(async (frame) => {
        const owner = await cdp.send("DOM.getFrameOwner", { frameId: frame.id }, sessionID).catch(() => void 0);
        const iframe = owner ? await cdp.send("DOM.describeNode", { backendNodeId: owner.backendNodeId }, sessionID).catch(() => void 0) : void 0;
        return { id: frame.id, document: iframe?.node.contentDocument?.backendNodeId };
      })
    );
    return owners.find((owner) => owner.document === described?.node.backendNodeId)?.id ?? root.id;
  }
  async function describe(element) {
    return Schema.decodeUnknownSync(
      Schema.Struct({ label: Schema.String, selector: Schema.String, text: Schema.optionalKey(Schema.String) })
    )(
      await call(
        element,
        `function() {
          const clip = (value, max) => (value.length > max ? value.slice(0, max - 1) + "\u2026" : value)
          const label = this.localName + (this.id ? "#" + this.id : "") + Array.from(this.classList, (name) => "." + name).join("")
          // One segment per document or shadow root, outermost first; " >>> " steps into a host's shadow root.
          const segments = []
          for (let start = this; start; ) {
            const root = start.getRootNode()
            const path = []
            for (let node = start; node; node = node.parentElement) {
              if (node.id && root.querySelectorAll("#" + CSS.escape(node.id)).length === 1) {
                path.unshift("#" + CSS.escape(node.id))
                break
              }
              if (node === node.ownerDocument.body) {
                path.unshift("body")
                break
              }
              const same = Array.from(node.parentNode?.children ?? []).filter((child) => child.localName === node.localName)
              path.unshift(CSS.escape(node.localName) + (same.length > 1 ? ":nth-of-type(" + (same.indexOf(node) + 1) + ")" : ""))
            }
            segments.unshift(path.join(" > "))
            start = root instanceof ShadowRoot ? root.host : undefined
          }
          const selector = segments.join(" >>> ")
          const text = clip((this.innerText ?? this.textContent ?? "").replace(/\\s+/g, " ").trim(), 160)
          // A cut selector is invalid syntax; leave it out rather than pass it off as usable.
          return { label: clip(label, 200), selector: selector.length > 2000 ? "" : selector, ...(text ? { text } : {}) }
        }`
      )
    );
  }
  async function accessibility(element) {
    const tree = await cdp.send(
      "Accessibility.getPartialAXTree",
      { backendNodeId: element.backendID, fetchRelatives: false },
      element.sessionID
    ).catch(() => void 0);
    const node = tree?.nodes.find((node2) => node2.backendDOMNodeId === element.backendID && !node2.ignored);
    const role = String(node?.role?.value ?? "");
    const name = String(node?.name?.value ?? "").replace(/\s+/g, " ").trim().slice(0, 160);
    const labeled = role && !["generic", "none", "presentation"].includes(role) ? { role: role.slice(0, 128) } : {};
    return name ? { ...labeled, name } : labeled;
  }
  async function painted(sessionID) {
    await Promise.race([
      cdp.send(
        "Runtime.evaluate",
        {
          expression: "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))",
          awaitPromise: true
        },
        sessionID
      ).catch(() => void 0),
      new Promise((resolve2) => setTimeout(resolve2, 150))
    ]);
  }
}
export {
  createBrowserPage
};
