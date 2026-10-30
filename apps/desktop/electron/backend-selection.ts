import { createHash, randomBytes } from 'node:crypto';
import { lstatSync, mkdirSync, readFileSync, realpathSync, renameSync, unlinkSync, writeFileSync } from 'node:fs';
import path from 'node:path';

/** Same names and rules as packages/backend/src/host/handoff.ts and runtime/renulus/workers/profile_owner.py. */
export const BACKEND_SELECTOR = '.renulus-backend-selector.json';
export const GENERATION_MANIFEST = '.renulus-complete-generation.json';
/** The exact selected routes in docs/DECISIONS.md (packages/backend/src/dispatch/policy.ts ALLOWED_MODELS). */
export const SELECTED_MODELS = Object.freeze(['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna', 'mimo-v2.6-pro', 'deepseek-v4.1-flash']);
const SELECTOR_KEYS = ['authorityEpoch', 'cohortHash', 'contract', 'generation', 'generationPath', 'manifestSha256', 'profileId', 'schemaHash', 'state', 'writer'];

export class BackendSelectionError extends Error {
  constructor(readonly code: string, message: string) { super(message); this.name = 'BackendSelectionError'; }
}
const refuse: (code: string) => never = code => { throw new BackendSelectionError(code, 'Renulus could not confirm which backend owns this learning profile (' + code + '). Nothing was opened for writing and your records are unchanged.'); };

export type BackendSelection =
  | { route: 'python' }
  | { route: 'held'; writer: 'python' | 'ts' }
  | { route: 'ts'; profileRoot: string; generationRoot: string; profileId: string; authorityEpoch: number };

export interface DesktopProfileIdentity { profile_id: string; domain_store_id: string; runtime_store_id: string }
/** Mirrors runtime/renulus/runtime/desktop_harness.py create_desktop_app over its resolved root.
 * Python hashes str.casefold(); this equals toLowerCase for ASCII paths. A differing fold refuses below, never guesses. */
export function desktopProfileIdentity(resolvedRoot: string): DesktopProfileIdentity {
  const id = 'desktop-' + createHash('sha256').update(resolvedRoot.toLowerCase()).digest('hex').slice(0, 32);
  return { profile_id: id, domain_store_id: id + '-domain', runtime_store_id: id + '-runtime' };
}

function regularFile(file: string, maximum: number) {
  const info = lstatSync(file, { throwIfNoEntry: false });
  if (!info) return undefined;
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > maximum) refuse('backend_metadata_invalid');
  return readFileSync(file);
}
const sha256 = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const digest = (value: unknown) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const counter = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 1;

/** Absent selector keeps today's Python ownership. Any present selector must be
 * complete and consistent; ambiguity refuses instead of selecting a writer. */
export function readBackendSelection(resolvedRoot: string): BackendSelection {
  let bytes: Buffer | undefined;
  try { bytes = regularFile(path.join(resolvedRoot, BACKEND_SELECTOR), 16384); }
  catch (error) { if (error instanceof BackendSelectionError) throw error; refuse('backend_selector_unreadable'); }
  if (bytes === undefined) return { route: 'python' };
  let selector: Record<string, unknown>;
  try { selector = JSON.parse(bytes.toString('utf8')); } catch { return refuse('backend_selector_invalid'); }
  if (!selector || typeof selector !== 'object' || Array.isArray(selector) || Object.keys(selector).sort().join() !== SELECTOR_KEYS.join() ||
      selector.contract !== 'renulus-backend-selector/1' || (selector.writer !== 'python' && selector.writer !== 'ts') ||
      (selector.state !== 'held' && selector.state !== 'active') || !counter(selector.generation) || !counter(selector.authorityEpoch) ||
      typeof selector.profileId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$/.test(selector.profileId) ||
      ![selector.manifestSha256, selector.schemaHash, selector.cohortHash].every(digest) ||
      typeof selector.generationPath !== 'string' || !/^generations\/[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(selector.generationPath)) refuse('backend_selector_invalid');
  if (selector.profileId !== desktopProfileIdentity(resolvedRoot).profile_id) refuse('backend_selector_profile_mismatch');
  const generationRoot = path.join(resolvedRoot, ...(selector.generationPath as string).split('/'));
  try {
    for (const directory of [path.dirname(generationRoot), generationRoot]) {
      const info = lstatSync(directory);
      if (!info.isDirectory() || info.isSymbolicLink() || realpathSync.native(directory).toLowerCase() !== directory.toLowerCase()) refuse('backend_generation_unowned');
    }
    const manifestBytes = regularFile(path.join(generationRoot, GENERATION_MANIFEST), 16 * 1024 * 1024);
    if (!manifestBytes || sha256(manifestBytes) !== selector.manifestSha256) refuse('backend_generation_changed');
    const manifest = JSON.parse(manifestBytes!.toString('utf8'));
    if (manifest?.profileId !== selector.profileId || manifest.generation !== selector.generation ||
        manifest.schemaHash !== selector.schemaHash || manifest.cohortHash !== selector.cohortHash) refuse('backend_generation_changed');
  } catch (error) { if (error instanceof BackendSelectionError) throw error; refuse('backend_generation_unreadable'); }
  if (selector.state === 'held') return { route: 'held', writer: selector.writer as 'python' | 'ts' };
  if (selector.writer === 'python') return { route: 'python' };
  return { route: 'ts', profileRoot: resolvedRoot, generationRoot, profileId: selector.profileId as string, authorityEpoch: selector.authorityEpoch as number };
}

export function handoffHeldError(): BackendSelectionError {
  return new BackendSelectionError('backend_handoff_held', 'Renulus paused this learning profile while a data handoff completes. Nothing was opened for writing and your records are unchanged. Start Renulus again later to retry.');
}

/** Installed launch resources for packages/backend/src/main.ts --target-resources.
 * Only fixed bundle/profile locations: no deployment evidence is invented and no
 * account/model is discovered. The broker keeps the profile's existing credential
 * state; originals live in the selected generation, where the handoff placed them.
 * Electron does not yet bridge its chooser into the grant root, so the grant token
 * is held by nobody and native path grants stay unavailable; bytes import is unaffected. */
export function targetResources(options: { selection: Extract<BackendSelection, { route: 'ts' }>; sourceRoot: string; helpersRoot: string; processGeneration: string; grantTokenSha256: string }) {
  const { selection } = options, root = selection.profileRoot, generation = selection.generationRoot;
  const identity = desktopProfileIdentity(root);
  return {
    identity: { ...identity, authority_epoch: selection.authorityEpoch, process_generation: options.processGeneration },
    available_models: [...SELECTED_MODELS],
    evidence: [],
    helpers: { helpers_root: options.helpersRoot, cache_root: path.join(root, 'cache'), source_root: options.sourceRoot },
    derived: { root: path.join(root, 'derived'), namespace: identity.profile_id, library_tombstones: [], memory_tombstones: [] },
    broker: { profile_root: root, state_root: path.join(root, 'state') },
    native: { originals_root: path.join(generation, 'originals'), budget_root: generation, grants_root: path.join(generation, 'native-grants'),
      grant_token_sha256: options.grantTokenSha256 },
  };
}

/** One Electron-owned file, replaced whole; the app's profile lock excludes another writer. */
export function writeTargetResources(file: string, value: unknown) {
  const temporary = file + '.' + randomBytes(8).toString('hex') + '.tmp';
  try { writeFileSync(temporary, JSON.stringify(value), { flag: 'wx', mode: 0o600 }); renameSync(temporary, file); }
  finally { try { unlinkSync(temporary); } catch { /* renamed */ } }
}

/** The owner supervisor compares Path.resolve(); hand it the same final Windows path. */
export function resolveBackendSelection(profileRoot: string): BackendSelection {
  let root: string;
  try { root = realpathSync.native(profileRoot); } catch { return refuse('backend_profile_unavailable'); }
  return readBackendSelection(root);
}

/** Electron → Python profile_owner (mutex, kill-on-close job, private launch proof)
 * → bundled Node launch.mjs → packages/backend/dist/main.mjs as the selected writer. */
export function prepareSelectedOwnerLaunch(options: { selection: Extract<BackendSelection, { route: 'ts' }>; python: string; packaged: boolean;
  bundleRoot: string; workspace: string; port: number; node?: string }) {
  const { selection, packaged, bundleRoot } = options;
  if (packaged) {
    let contract: Record<string, unknown> | undefined;
    try { contract = JSON.parse(readFileSync(path.join(bundleRoot, 'backend-bundle.json'), 'utf8')); } catch { contract = undefined; }
    if (contract?.contract !== 'renulus-backend-bundle/1' || contract.node !== 'node/node.exe' || contract.python !== 'python/python.exe' || contract.entrypoint !== 'launch.mjs')
      throw new Error('The packaged TypeScript backend launch contract is invalid.');
  }
  const node = packaged ? path.join(bundleRoot, 'node', 'node.exe') : options.node;
  const entry = packaged ? path.join(bundleRoot, 'launch.mjs') : path.join(options.workspace, 'packages', 'backend', 'dist', 'main.mjs');
  const exact = (value: string) => realpathSync.native(value);
  if (!node || !path.isAbsolute(node) || lstatSync(node, { throwIfNoEntry: false })?.isFile() !== true || lstatSync(entry, { throwIfNoEntry: false })?.isFile() !== true)
    throw new Error('The selected TypeScript backend runtime is not available. Development requires an absolute RENULUS_NODE (Node 26.4.0) and a built packages/backend/dist.');
  const source = exact(packaged ? bundleRoot : options.workspace);
  const resources = path.join(selection.profileRoot, 'desktop', 'backend-target-resources.json');
  // The worker requires existing native directories; a handoff generation always has originals/.
  for (const directory of ['originals', 'native-grants']) mkdirSync(path.join(selection.generationRoot, directory), { recursive: true });
  writeTargetResources(resources, targetResources({ selection, sourceRoot: source, processGeneration: randomBytes(16).toString('hex'),
    grantTokenSha256: createHash('sha256').update(randomBytes(32)).digest('hex'),
    helpersRoot: packaged ? path.join(source, 'helper-assets') : path.join(selection.profileRoot, 'helpers') }));
  const identity = desktopProfileIdentity(selection.profileRoot);
  return {
    cwd: source, runtimeRoot: path.join(source, 'runtime'),
    args: [...(packaged ? ['-I'] : []), '-B', '-X', 'utf8', '-m', 'renulus.workers.profile_owner', '--profile', selection.profileRoot,
      '--node', exact(node), '--entrypoint', exact(entry), '--profile-id', identity.profile_id,
      '--domain-store-id', identity.domain_store_id, '--runtime-store-id', identity.runtime_store_id,
      '--', '--target', '--selected-owner', '--profile', selection.generationRoot, '--port', String(options.port),
      '--python', exact(options.python), '--source-root', source, '--target-resources', resources],
  };
}
