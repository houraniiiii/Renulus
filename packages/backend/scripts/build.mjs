// SPDX-License-Identifier: MIT
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
const root = fileURLToPath(new URL("..", import.meta.url));
// Reuse the desktop's pinned build dependency; no runtime acquisition.
const require = createRequire(new URL("../../desktop-build.cjs", import.meta.url));
const esbuild = require(path.resolve(root, "../../apps/desktop/node_modules/esbuild"));
// The bundle has no repository tree beside it: embed every text file the sources read relative to themselves
// (SQL schemas, the source register) as it is on disk at build time.
const staticRead = /readFileSync\(new URL\('([^']+)', import\.meta\.url\), 'utf8'\)/g;
const embedStaticReads = { name: "embed-static-reads", setup(build) {
  build.onLoad({ filter: /[\\/]src[\\/].*\.ts$/ }, args => {
    const code = readFileSync(args.path, "utf8");
    return { contents: code.replace(staticRead, (_, relative) => JSON.stringify(readFileSync(path.resolve(path.dirname(args.path), relative), "utf8"))), loader: "ts" };
  });
} };
await esbuild.build({ plugins: [embedStaticReads], entryPoints: { main: path.join(root, "src/main.ts"),
  "storage-worker": path.join(root, "src/storage/worker.ts") }, outdir: path.join(root, "dist"), outExtension: { ".js": ".mjs" },
  bundle: true, platform: "node", target: "node26.4", format: "esm", packages: "external", sourcemap: false });
