// SPDX-License-Identifier: MIT
/** Narrow OpenCode 4b6fea... / published 2.0.26 injection patch, MIT upstream.
 * Apply ONLY to owned build copies. Never patches the shared development cohort.
 * A byte-for-byte manifest is generated from the reviewed installed cohort.
 * Removal: upstream exposes equivalent per-attempt web/MCP and browser attachment/tunnel factories,
 * and the native execute journey proves redirect re-admission, byte bounds, revocation and header denial without this patch.
 */
import { readFile, writeFile, realpath, lstat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const cohort = '4b6fea2875e4f2e3e8a8fee181803e54f7056845';
export const version = '2.0.26';
export const sha = source => createHash('sha256').update(source).digest('hex');
const boundary = `// MIT Renulus narrow injection; native execution/protocol stays upstream.
import { Context } from 'effect';
export const CapabilityBoundary = Context.Reference('renulus/native-capability-boundary/1', { defaultValue: () => undefined });
`;
export const patches = [
  { package:'core', file:'dist/chunks/agent-82v73sw7.js', changes:[
    ['import { CodeMode, Namespace, Tool, toolError } from "@opencode/codemode";', 'import { CodeMode, Namespace, Tool, toolError, Extension } from "@opencode/codemode";\nimport { CapabilityBoundary } from "../renulus-boundary.js";'],
    ['      const callIndex = yield* Ref.make(0);', '      const boundary = yield* CapabilityBoundary;\n      if (!boundary) throw new Error("renulus_codemode_authority_required");\n      const callIndex = yield* Ref.make(0);'],
    ['}), progressHooks(record)).execute(code);', '}), progressHooks(record), boundary, context).execute(code);'],
    ['function runtime(inventory, executeTool, hooks) {','function runtime(inventory, executeTool, hooks, boundary, nativeContext) {'],
    ['return CodeMode.make({ tools, extensions: [extension2], hooks });','return CodeMode.make({ tools, extensions: [Extension.make({ name: "web", globals: { fetch: async (...args) => {\n    if (!boundary || !nativeContext) throw new Error("renulus_codemode_authority_required");\n    return boundary.fetch(nativeContext, ...args);\n  } } })], hooks, limits: { timeoutMs: 30000, maxToolCalls: 32, maxOutputBytes: 262144 } });'],
  ]},
  { package:'core',file:'dist/chunks/agent-63648xmm.js',changes:[
    ['const authProvider = yield* connectProvider(entry);','const authProvider = undefined; // Renulus worker owns OAuth; native credentials are never read/written.'],
  ]},
  { package:'core',file:'dist/mcp/client.js',changes:[
    ['import path from "node:path";','import path from "node:path";\nimport { CapabilityBoundary } from "../renulus-boundary.js";'],
    ['  const changed = { tools: () => {}, prompts: () => {}, resources: () => {} };','  const boundary = yield* CapabilityBoundary;\n  if (!boundary) throw new Error("renulus_mcp_authority_required");\n  const owner = yield* Effect.tryPromise(() => boundary.mcp(server, config));\n  yield* Effect.addFinalizer(() => Effect.promise(() => owner.close()));\n  const changed = { tools: () => {}, prompts: () => {}, resources: () => {} };'],
    ['const transport = yield* make2({','const transport = yield* owner.localTransport({'],
    ['const fetch = yield* McpOAuth.loggedFetch({ server, directory });','const fetch = owner.fetch;'],
    ['requestInit: config.headers ? { headers: config.headers } : undefined,','requestInit: undefined, // Worker alone injects protected headers.'],
  ]},
  { package:'core',file:'dist/chunks/agent-4ahpts8n.js',changes:[
    ['import { ToolFailure } from "@opencode/ai";','import { ToolFailure } from "@opencode/ai";\nimport { CapabilityBoundary } from "../renulus-boundary.js";'],
    ['execute: (input, context) => Effect.gen(function* () {','execute: (input, context) => Effect.gen(function* () {\n            const boundary = yield* CapabilityBoundary;\n            if (!boundary) throw new Error("renulus_mcp_authority_required");\n            return yield* boundary.mcpTool({server:tool.server,name:tool.name,inputSchema:tool.inputSchema,outputSchema:tool.outputSchema}, input, context, Effect.gen(function* () {'],
    ['          }).pipe(Effect.mapError((error) => error instanceof ToolFailure', '            }));\n          }).pipe(Effect.mapError((error) => error instanceof ToolFailure'],
  ]},
  { package:'plugin-browser',file:'dist/files.js',changes:[
    ['mkdtemp(join(tmpdir(), "opencode-browser-"))','mkdtemp(join(globalThis[Symbol.for("renulus.browser.downloads")] ?? (() => { throw new Error("renulus_browser_downloads_required"); })(), "opencode-browser-"))'],
  ]},
  { package:'plugin-browser',file:'dist/connection.js',changes:[
    ['import { BrowserTunnel } from "./tunnel.js";','import { CapabilityBoundary } from "@opencode/core/renulus-boundary";'],
    ['    const browsers = new Map();','    const boundary = yield* CapabilityBoundary;\n    if (!boundary) throw new Error("renulus_browser_authority_required");\n    const browsers = new Map();'],
    ['        browser.tunnels.dispose();','        yield* Effect.promise(() => browser.owned.revoke());'],
    ['                const browser = {','                const owned = yield* Effect.tryPromise(() => boundary.browser(input));\n                const browser = {\n                    owned,'],
    ['                    tunnels: BrowserTunnel.make(),','                    tunnels: owned.tunnels,'],
    ['            browser.state = input.state;','            yield* Effect.tryPromise(() => browser.owned.current());\n            browser.state = input.state;'],
    ['            return pending.command;','            yield* Effect.tryPromise(() => browser.owned.current());\n            return pending.command;'],
    ['            const pending = browser.pending.get(input.requestID);','            yield* Effect.tryPromise(() => browser.owned.current());\n            const pending = browser.pending.get(input.requestID);'],
    ['            const tab = "tabID" in action ?', '            yield* Effect.tryPromise(() => browser.owned.current());\n            const tab = "tabID" in action ?'],
  ]},
];
export function transform(source, patch) {
  for(const [from,to] of patch.changes) {
    if(source.split(from).length!==2) throw new Error('native_patch_seam_changed:'+patch.file);
    source=source.replace(from,to);
  }
  return source;
}
export async function applyNativeCapabilityPatch(root, manifest) {
  root=path.resolve(root);
  const resolved=await realpath(root);
  if(resolved.toLowerCase().includes('scratch\\ocf\\cohort')||resolved.toLowerCase().includes('scratch/ocf/cohort')) throw new Error('shared_cohort_patch_forbidden');
  // Validate every input and every parent realpath before the first write.
  const writes=[];
  for(const pkg of ['core','plugin-browser']) {
    const pkgRoot=path.join(root,'@opencode',pkg);
    const actual=await realpath(pkgRoot);
    if(!actual.toLowerCase().startsWith(resolved.toLowerCase()+path.sep)) throw new Error('native_patch_owned_copy_required');
    const metadata=JSON.parse(await readFile(path.join(pkgRoot,'package.json'),'utf8'));
    if(metadata.version!==version) throw new Error('native_patch_version_mismatch');
  }
  for(const patch of patches) {
    const file=path.join(root,'@opencode',patch.package,patch.file),source=await readFile(file,'utf8');
    if(sha(source)!==manifest[patch.package+'/'+patch.file])throw new Error('native_patch_hash_mismatch:'+patch.file);
    const fileReal=await realpath(file);if(!fileReal.toLowerCase().startsWith(resolved.toLowerCase()+path.sep)||!(await lstat(file)).isFile()) throw new Error('native_patch_owned_copy_required');
    writes.push([file,transform(source,patch)]);
  }
  const boundaryPath=path.join(root,'@opencode/core/dist/renulus-boundary.js');
  for(const [file,source] of [...writes,[boundaryPath,boundary]])await writeFile(file,source,'utf8');
  return {cohort,version,files:Object.fromEntries([...writes,[boundaryPath,boundary]].map(([file,source])=>[path.relative(root,file),sha(source)]))};
}
if(process.argv[1]===fileURLToPath(import.meta.url)) {
  const manifest=JSON.parse(await readFile(new URL('./native-patch-hashes.json',import.meta.url),'utf8'));
  if(!process.argv[2])throw new Error('owned_node_modules_root_required');
  process.stdout.write(JSON.stringify(await applyNativeCapabilityPatch(process.argv[2],manifest))+'\n');
}
