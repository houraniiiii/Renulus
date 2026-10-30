// SPDX-License-Identifier: MIT
/** Local verifier of the staged backend bundle (`packaging/backend_bundle.py`), same rules as its `verify`:
 * the inventory file hash is pinned by `backend-bundle.json`, and every inventoried file is an owned regular
 * file inside the bundle with its exact size and SHA-256. It also pins the running Node and entry to that bundle. */
import { createHash } from 'node:crypto';
import { createReadStream, lstatSync, readdirSync, readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';
import { reject } from '../storage/contracts.ts';

/** Reviewed Node 26.4.0 win-x64 binary; identical to `NODE_SHA256` in packaging/backend_bundle.py. */
export const NODE_SHA256 = '3193d7f751b8a07bd4acc70e81946ae9c6efdee83e07ad1c8d0e4089df7c5cef';
interface Item { path: string; sha256: string; bytes: number }
interface Manifest { contract: string; node: string; nodeSha256: string; python: string; cohortHash: string; inventorySha256: string }
const same = (a: string, b: string) => a.toLowerCase() === b.toLowerCase();
const digest = (file: string) => new Promise<string>((resolve, fail) => {
  const hash = createHash('sha256');
  createReadStream(file).on('data', chunk => hash.update(chunk)).on('error', fail).on('end', () => resolve(hash.digest('hex')));
});

export function createBundleVerifier(options: { root: string; entry: string; execPath?: string }) {
  const root = options.root;
  if (!path.isAbsolute(root) || !same(realpathSync(root), path.resolve(root))) reject('bundle_root_invalid');
  function member(relative: string) {
    if (typeof relative !== 'string' || !relative || relative.includes('\\') || path.isAbsolute(relative) || relative.includes(':') ||
        relative.split('/').some(part => !part || part === '.' || part === '..')) reject('bundle_inventory_path_invalid');
    const file = path.join(root, ...relative.split('/'));
    const stat = lstatSync(file, { throwIfNoEntry: false });
    if (!stat?.isFile() || stat.nlink !== 1 || !same(realpathSync(file), file)) reject('bundle_member_changed:' + relative);
    return { file, bytes: stat.size };
  }
  async function load() {
    const manifest = JSON.parse(readFileSync(member('backend-bundle.json').file, 'utf8')) as Manifest;
    if (manifest.contract !== 'renulus-backend-bundle/1' || await digest(member('backend-inventory.json').file) !== manifest.inventorySha256)
      reject('bundle_inventory_changed');
    const items = JSON.parse(readFileSync(member('backend-inventory.json').file, 'utf8')) as Item[];
    if (!Array.isArray(items)) reject('bundle_inventory_changed');
    const listed = new Map(items.map(item => [item.path, item]));
    if (manifest.nodeSha256 !== NODE_SHA256 || listed.get(manifest.node)?.sha256 !== NODE_SHA256) reject('bundle_node_pin_mismatch');
    // The running process and entry must be this bundle's verified files, never a developer PATH lookup.
    const relative = (file: string) => path.relative(root, realpathSync(file)).split(path.sep).join('/');
    if (!same(relative(options.execPath ?? process.execPath), manifest.node)) reject('bundle_node_not_running');
    if (!listed.has(relative(options.entry))) reject('bundle_entry_not_inventoried');
    return { manifest, items, listed };
  }
  /** Closed membership, as backend_bundle.verify: every present file is inventoried (only the two
   * self-referencing contract files are exempt), and no link, junction or other entry type exists. */
  function membership(listed: Map<string, Item>) {
    const present = new Set<string>(), pending = [''];
    while (pending.length) {
      const directory = pending.pop()!;
      for (const entry of readdirSync(path.join(root, ...directory.split('/').filter(Boolean)), { withFileTypes: true })) {
        const name = directory ? directory + '/' + entry.name : entry.name;
        if (entry.isSymbolicLink()) reject('bundle_link_refused:' + name);
        if (entry.isDirectory()) { if (lstatSync(path.join(root, ...name.split('/'))).isSymbolicLink()) reject('bundle_link_refused:' + name); pending.push(name); }
        else if (entry.isFile()) present.add(name);
        else reject('bundle_file_type_refused:' + name);
      }
    }
    for (const name of ['backend-bundle.json', 'backend-inventory.json']) present.delete(name);
    const extra = [...present].filter(name => !listed.has(name)), missing = [...listed.keys()].filter(name => !present.has(name));
    if (extra.length || missing.length) reject('bundle_membership_changed:' + [...extra, ...missing].slice(0, 5).join(','));
  }
  async function check(item: Item) {
    const { file, bytes } = member(item.path);
    if (bytes !== item.bytes || await digest(file) !== item.sha256) reject('bundle_member_changed:' + item.path);
  }
  return {
    /** This bundle's cohort; a handoff seals it into the prepared generation. */
    async cohortHash() { return (await load()).manifest.cohortHash; },
    /** Launch: the running Node/entry are this bundle's, required members exist, and the whole closed payload matches. */
    async verifyLaunch(cohortHash: string) {
      const { manifest, items, listed } = await load();
      if (manifest.cohortHash !== cohortHash) reject('bundle_cohort_mismatch');
      for (const name of [manifest.node, 'cohort/source-inventory.json', 'packages/backend/dist/main.mjs', 'packages/backend/dist/storage-worker.mjs'])
        if (!listed.has(name)) reject('bundle_member_missing:' + name);
      // Before the selected writer opens or any worker starts, every executable byte must be the attested one.
      membership(listed);
      for (const item of items) await check(item);
    },
    /** Exact compatible cohort for a selection: every inventoried byte, as `backend_bundle.verify`. */
    async verifyBinaries(writer: 'python' | 'ts', schemaHash: string, cohortHash: string) {
      if (!['python', 'ts'].includes(writer) || !/^[a-f0-9]{64}$/.test(schemaHash)) reject('bundle_selection_invalid');
      const { manifest, items, listed } = await load();
      if (manifest.cohortHash !== cohortHash) reject('bundle_cohort_mismatch');
      if (writer === 'python' && !listed.has(manifest.python)) reject('bundle_python_missing');
      membership(listed);
      for (const item of items) await check(item);
      if (await digest(member('cohort/source-inventory.json').file) !== manifest.cohortHash) reject('bundle_cohort_mismatch');
    },
  };
}
