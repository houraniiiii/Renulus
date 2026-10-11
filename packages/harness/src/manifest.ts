import path from "node:path";
import { readFile, realpath, stat } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";

export const SOURCE = "4b6fea2875e4f2e3e8a8fee181803e54f7056845";
export const RUNTIME_PATH = "state/harness/opencode.sqlite";
export interface ProfileSelection {
  readonly root: string;
  readonly profileId: string;
  readonly storeId: string;
  readonly domainStoreId: string;
  readonly domainPath: string;
}

/** Read-only identity check of the Python-owned selection, before SDK writes. */
export async function verifyPreparedProfile(input: ProfileSelection) {
  const fail = () => { throw new Error("harness_manifest_mismatch"); };
  const identifier = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/;
  if (![input.profileId, input.storeId, input.domainStoreId].every(value => typeof value === "string" && identifier.test(value))
      || input.storeId === input.domainStoreId) fail();
  const domain = input.domainPath;
  const reserved = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i;
  if (typeof domain !== "string" || domain.length > 512
      || !/^[A-Za-z0-9_-](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?(?:\/[A-Za-z0-9_-](?:[A-Za-z0-9._-]*[A-Za-z0-9_-])?)*$/.test(domain)
      || domain.split("/").some(part => reserved.test(part))
      || domain.toLowerCase() === "state" || domain.toLowerCase() === "state/harness"
      || domain.toLowerCase().startsWith("state/harness/")) fail();
  if (!path.isAbsolute(input.root)) fail();
  const root = path.resolve(input.root);
  const file = path.join(root, "state/harness/manifest.json");
  const samePath = (a: string, b: string) => process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;
  try {
    for (const candidate of [root, file, path.join(root, RUNTIME_PATH), path.join(root, domain)]) {
      // realpath cannot resolve a missing leaf. Its nearest existing ancestor
      // still must be the selected path, including on Windows junctions.
      let ancestor = candidate;
      for (;;) {
        try { if (!samePath(await realpath(ancestor), ancestor)) fail(); break; }
        catch (error) {
          if ((error as NodeJS.ErrnoException).code !== "ENOENT" || ancestor === root) throw error;
          ancestor = path.dirname(ancestor);
        }
      }
    }
    if ((await stat(file)).size > 16384) fail();
    const manifest = JSON.parse(await readFile(file, "utf8"));
    const expected = {
      contract_version: "harness/1", profile_id: input.profileId, snapshot_generation: 1,
      cohort_source: SOURCE, state: "prepared",
      domain_store: { store_id: input.domainStoreId, engine: "renulus-sqlite", schema_version: 2,
        generation: 1, path: domain, validation: "pending" },
      runtime_store: { store_id: input.storeId, engine: { name: "opencode", version: "2.0.26", source_commit: SOURCE },
        schema_version: `source:${SOURCE}`, generation: 1, path: RUNTIME_PATH, validation: "pending" },
    };
    if (manifest?.state === "active") {
      expected.state = "active";
      expected.domain_store.validation = "valid";
      expected.runtime_store.validation = "valid";
    }
    if (!isDeepStrictEqual(manifest, expected)) fail();
    return expected;
  } catch { fail(); }
  throw new Error("harness_manifest_mismatch");
}
