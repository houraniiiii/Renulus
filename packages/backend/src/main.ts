// SPDX-License-Identifier: MIT
import { parseArgs } from "node:util";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { openCompatibilityApplication } from "./host/application.ts";
import { openTargetApplication } from "./host/target.ts";
import { loadMigrationInventory, type SyntheticSelector } from "./storage/index.ts";
import { readSelectedOwnerLaunch, resolveBackendSelection } from './host/handoff.ts';
import { createBundleVerifier } from './host/bundle-verify.ts';

// Explicit: under the supervisor's `-e` launch gate parseArgs' default would treat the entry path as an argument.
const { values } = parseArgs({ args: process.argv.slice(2), options: {
  profile: { type: "string" }, port: { type: "string" }, python: { type: "string" },
  "source-root": { type: "string" }, compatibility: { type: "boolean" }, "desktop-harness": { type: "boolean" },
  target: { type: "boolean" }, "schema-hash": { type: "string" },
  "target-resources": { type: "string" },
  'selected-owner': { type: 'boolean' },
  handoff: { type: 'string' }, 'expected-source-sha256': { type: 'string' },
} });
if (process.versions.node !== "26.4.0") throw new Error("The reviewed Node 26.4.0 runtime is required");
// The selected owner verifies the very bundle it runs from (dist/main.mjs -> bundle root); no bundle, no selected launch.
const bundle = () => createBundleVerifier({ root: fileURLToPath(new URL('../../../', import.meta.url)).replace(/[\\/]$/, ''),
  entry: fileURLToPath(import.meta.url) });

if (values.handoff) {
  // Maintenance launch under the native supervisor only: its profile mutex proves the application is closed.
  if (!values['selected-owner'] || !values.profile || !values.python || !values['source-root'] ||
      !path.isAbsolute(values.python) || !path.isAbsolute(values['source-root']))
    throw new Error('handoff_maintenance_launch_required');
  let line: Record<string, unknown>;
  try {
    const authority = readSelectedOwnerLaunch();
    if (authority.profileRoot !== path.resolve(values.profile)) throw new Error('selected_owner_target_mismatch');
    const verifier = bundle();
    const { runHandoffCommand } = await import('./host/initial-handoff.ts');
    const result = await runHandoffCommand(values.handoff, { authority, python: values.python, sourceRoot: values['source-root'],
      verifyBinaries: verifier.verifyBinaries, cohortHash: await verifier.cohortHash() }, values['expected-source-sha256']);
    line = { event: 'handoff', action: values.handoff, ok: true, result };
  } catch (error) {
    process.exitCode = 1;
    line = { event: 'handoff', action: values.handoff, ok: false,
      error: { code: error && typeof error === 'object' && 'code' in error ? String(error.code) : error instanceof Error ? error.message : 'handoff_failed',
        detail: error instanceof Error && 'code' in error && error.message !== error.code ? error.message : undefined } };
  }
  process.stdout.write(JSON.stringify(line) + '\n');
} else {
  if (Boolean(values.compatibility) === Boolean(values.target) || !values.profile ||
      !values.python || !values["source-root"] || !values.port ||
      !/^\d+$/.test(values.port) || !process.env.RENULUS_SESSION_TOKEN)
    throw new Error("Explicit compatibility/target mode, profile, source root, port and private session token are required");
  if (values.target && !values['selected-owner'] && (!values["schema-hash"] || !/^[a-f0-9]{64}$/.test(values["schema-hash"])))
    throw new Error("The independently previewed populated schema hash is required for target admission");
  if (values.target && (!values['target-resources'] || !path.isAbsolute(values['target-resources'])))
    throw new Error('Explicit installed target resources are required');
  const resources = values.target ? JSON.parse(readFileSync(values['target-resources']!, 'utf8')) : undefined;
  const selectedAuthority = values['selected-owner'] ? readSelectedOwnerLaunch() : undefined;
  const selected = selectedAuthority ? resolveBackendSelection(selectedAuthority.profileRoot) : undefined;
  if (selectedAuthority && (!values.target || selected?.writer !== 'ts' || selected.admission !== 'active' ||
      selected.profileRoot !== selectedAuthority.generationRoot || selected.profileRoot !== path.resolve(values.profile)))
    throw new Error('selected_owner_target_mismatch');
  // Launch subset now (running Node, entry, selected cohort); every byte again before any generation selection.
  const verifier = selectedAuthority ? bundle() : undefined;
  if (verifier && selected?.selection) await verifier.verifyLaunch(selected.selection.cohortHash);
  let connected;
  if (resources) {
    const { loadInstalledEvidence, loadDeveloperConfiguration } = await import('./host/composition.ts');
    connected = { identity: resources.identity, availableModels: resources.available_models,
      evidence: await loadInstalledEvidence(resources.evidence ?? []), resources: {
        python: values.python!, sourceRoot: values['source-root']!, helpers: resources.helpers,
        derived: resources.derived, broker: resources.broker, native: resources.native },
      // Persisted user settings: MCP connections live in canonical `mcp_connections` (none = no MCP server);
      // the developer plugin needs a separate hash-pinned configuration with `enabled: true`, otherwise Off.
      mcp: 'stored' as const, developer: resources.developer ? await loadDeveloperConfiguration(resources.developer) : undefined };
  }
  const app = values.target ? await openTargetApplication({ profileRoot: values.profile,
    ...(selectedAuthority ? { selectedAuthority } : { selection: JSON.parse(readFileSync(path.join(values.profile, "state/storage-selector.json"), "utf8")) as SyntheticSelector }),
    migrations: loadMigrationInventory(values["source-root"]), expectedSchemaHash: selected && 'expectedSchemaHash' in selected ? selected.expectedSchemaHash! : values["schema-hash"]!,
    port: Number(values.port), token: process.env.RENULUS_SESSION_TOKEN, connected, verifyBinaries: verifier?.verifyBinaries })
    : await openCompatibilityApplication({ profile: values.profile, python: values.python!,
      sourceRoot: values["source-root"], port: Number(values.port), token: process.env.RENULUS_SESSION_TOKEN,
      desktopHarness: values["desktop-harness"] ?? true });
  process.stdout.write(JSON.stringify({ event: "ready", api_version: 1, port: app.port,
    writer: values.target ? "ts" : "python" }) + "\n");
  let stopping = false;
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    try { await app.close(); }
    catch { stopping = false; process.stderr.write("renulus_backend_shutdown_held\n"); }
  };
  process.on("SIGINT", () => { void stop(); });
  process.on("SIGTERM", () => { void stop(); });
  if ("closed" in app) void app.closed.then(stop);
}
