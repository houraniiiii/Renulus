// SPDX-License-Identifier: MIT
import type { IncomingMessage } from "node:http";
import type { createPluginLifecycle } from "../plugins/lifecycle.ts";
import type { CapabilityManifest, SelectedPlugin } from "../plugins/types.ts";
import { readJsonObject, RequestBodyError } from "./body.ts";

export type PluginCommands = ReturnType<typeof createPluginLifecycle>;

/** Authenticated user/admin commands only, never part of the model catalogue. */
export async function pluginCommand(request: IncomingMessage, url: URL, plugins: PluginCommands) {
  const root = "/api/v1/runtime/plugins";
  if (request.method === "GET" && url.pathname === root) return plugins.status();
  if (request.method !== "POST") throw new RequestBodyError(422);
  const body = await readJsonObject(request, 1_048_576);
  const exact = (...keys: string[]) => {
    if (Object.keys(body).sort().join(",") !== keys.sort().join(",")) throw new RequestBodyError(422);
  };
  switch (url.pathname.slice(root.length)) {
    case "/stage": exact("selection"); return plugins.stage(body.selection as SelectedPlugin[]);
    case "/add": exact("manifest"); return plugins.add(body.manifest as CapabilityManifest);
    case "/edit": exact("manifest"); return plugins.edit(body.manifest as CapabilityManifest);
    case "/disable": exact("plugin_id"); return plugins.disable(String(body.plugin_id));
    case "/remove": exact("plugin_id"); return plugins.remove(String(body.plugin_id));
    case "/activate": exact(); return plugins.activate();
    case "/recover": exact(); return plugins.recover();
    default: throw new RequestBodyError(404);
  }
}
