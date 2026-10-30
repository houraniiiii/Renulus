import { createHash } from 'node:crypto';
import { lstatSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { BACKEND_SELECTOR, GENERATION_MANIFEST, SELECTED_MODELS, desktopProfileIdentity, prepareSelectedOwnerLaunch, readBackendSelection, resolveBackendSelection, targetResources } from './backend-selection';

let scratch: string;
let root: string;
const sha = (value: string) => createHash('sha256').update(value).digest('hex');
const schemaHash = sha('synthetic schema'), cohortHash = sha('synthetic cohort');

function publish(overrides: Record<string, unknown> = {}, manifestOverrides: Record<string, unknown> = {}) {
  const profileId = desktopProfileIdentity(root).profile_id;
  const generation = path.join(root, 'generations', 'g1');
  mkdirSync(generation, { recursive: true });
  const manifest = JSON.stringify({ profileId, generation: 1, authorityEpoch: 2, schemaHash, cohortHash, frontierDigest: sha('frontier'), members: [], ...manifestOverrides });
  writeFileSync(path.join(generation, GENERATION_MANIFEST), manifest);
  const selector = { contract: 'renulus-backend-selector/1', profileId, generation: 1, authorityEpoch: 2, writer: 'ts', state: 'active',
    generationPath: 'generations/g1', manifestSha256: sha(manifest), schemaHash, cohortHash, ...overrides };
  writeFileSync(path.join(root, BACKEND_SELECTOR), JSON.stringify(selector));
  return { generation, profileId };
}

beforeEach(() => {
  scratch = realpathSync.native(mkdtempSync(path.join(os.tmpdir(), 'rn-sel-')));
  root = path.join(scratch, 'profile');
  mkdirSync(root);
});
afterEach(() => rmSync(scratch, { recursive: true, force: true }));

describe('backend selector routing', () => {
  it('derives the Python desktop profile identity', () => {
    // Value computed by runtime/renulus/runtime/desktop_harness.py's derivation over this path.
    expect(desktopProfileIdentity('C:\\Users\\Synthetic\\AppData\\Local\\Renulus')).toEqual({ profile_id: 'desktop-69d52074a6f33b3e7404ef5906e13215',
      domain_store_id: 'desktop-69d52074a6f33b3e7404ef5906e13215-domain', runtime_store_id: 'desktop-69d52074a6f33b3e7404ef5906e13215-runtime' });
  });

  it('keeps the existing Python owner when no selector exists', () => {
    expect(resolveBackendSelection(root)).toEqual({ route: 'python' });
  });

  it('selects the TypeScript owner only for a complete active ts selection', () => {
    const { generation, profileId } = publish();
    expect(readBackendSelection(root)).toEqual({ route: 'ts', profileRoot: root, generationRoot: generation, profileId, authorityEpoch: 2 });
  });

  it('keeps Python for an active python selection and holds every held selection', () => {
    publish({ writer: 'python' });
    expect(readBackendSelection(root)).toEqual({ route: 'python' });
    publish({ state: 'held' });
    expect(readBackendSelection(root)).toEqual({ route: 'held', writer: 'ts' });
    publish({ writer: 'python', state: 'held' });
    expect(readBackendSelection(root)).toEqual({ route: 'held', writer: 'python' });
  });

  it.each([
    ['an extra field', { extra: true }, {}, 'backend_selector_invalid'],
    ['an unknown writer', { writer: 'both' }, {}, 'backend_selector_invalid'],
    ['an unknown state', { state: 'selected' }, {}, 'backend_selector_invalid'],
    ['a zero authority epoch', { authorityEpoch: 0 }, {}, 'backend_selector_invalid'],
    ['an escaping generation path', { generationPath: 'generations/../state' }, {}, 'backend_selector_invalid'],
    ['another profile identity', { profileId: 'desktop-0000' }, {}, 'backend_selector_profile_mismatch'],
    ['a changed generation manifest', { manifestSha256: sha('other') }, {}, 'backend_generation_changed'],
    ['a manifest for another schema', {}, { schemaHash: sha('other schema') }, 'backend_generation_changed'],
  ])('refuses %s', (_label, overrides, manifestOverrides, code) => {
    publish(overrides, manifestOverrides);
    expect(() => readBackendSelection(root)).toThrow(expect.objectContaining({ code }));
  });

  it('refuses malformed JSON and a missing generation without guessing', () => {
    writeFileSync(path.join(root, BACKEND_SELECTOR), '{"contract":');
    expect(() => readBackendSelection(root)).toThrow(expect.objectContaining({ code: 'backend_selector_invalid' }));
    publish();
    rmSync(path.join(root, 'generations'), { recursive: true });
    expect(() => readBackendSelection(root)).toThrow(expect.objectContaining({ code: 'backend_generation_unreadable' }));
  });

  it('refuses a generation reached through a junction', () => {
    const { generation } = publish();
    const outside = path.join(scratch, 'outside');
    mkdirSync(outside);
    writeFileSync(path.join(outside, GENERATION_MANIFEST), readFileSync(path.join(generation, GENERATION_MANIFEST)));
    rmSync(generation, { recursive: true });
    symlinkSync(outside, generation, 'junction');
    expect(() => readBackendSelection(root)).toThrow(expect.objectContaining({ code: 'backend_generation_unowned' }));
  });
});

describe('selected owner launch', () => {
  function ts() {
    publish();
    const selection = readBackendSelection(root);
    if (selection.route !== 'ts') throw new Error('expected ts');
    return selection;
  }

  it('builds installed target resources from the profile and the five selected routes only', () => {
    const selection = ts();
    const value = targetResources({ selection, sourceRoot: 'C:\\bundle', helpersRoot: 'C:\\bundle\\helper-assets', processGeneration: 'a'.repeat(32), grantTokenSha256: 'b'.repeat(64) });
    const identity = desktopProfileIdentity(root);
    expect(value).toEqual({
      identity: { ...identity, authority_epoch: 2, process_generation: 'a'.repeat(32) },
      available_models: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna', 'mimo-v2.6-pro', 'deepseek-v4.1-flash'], evidence: [],
      helpers: { helpers_root: 'C:\\bundle\\helper-assets', cache_root: path.join(root, 'cache'), source_root: 'C:\\bundle' },
      derived: { root: path.join(root, 'derived'), namespace: identity.profile_id, library_tombstones: [], memory_tombstones: [] },
      broker: { profile_root: root, state_root: path.join(root, 'state') },
      native: { originals_root: path.join(selection.generationRoot, 'originals'), budget_root: selection.generationRoot,
        grants_root: path.join(selection.generationRoot, 'native-grants'), grant_token_sha256: 'b'.repeat(64) },
    });
    expect(SELECTED_MODELS).toHaveLength(5);
  });

  it('launches the bundled supervisor, Node and launch.mjs with explicit owner identity', () => {
    const selection = ts();
    const bundle = path.join(scratch, 'resources', 'backend');
    for (const file of ['node/node.exe', 'python/python.exe', 'launch.mjs']) {
      mkdirSync(path.dirname(path.join(bundle, file)), { recursive: true }); writeFileSync(path.join(bundle, file), '');
    }
    mkdirSync(path.join(root, 'desktop'));
    expect(() => prepareSelectedOwnerLaunch({ selection, python: path.join(bundle, 'python/python.exe'), packaged: true, bundleRoot: bundle, workspace: scratch, port: 18777 }))
      .toThrow('The packaged TypeScript backend launch contract is invalid.');
    writeFileSync(path.join(bundle, 'backend-bundle.json'), JSON.stringify({ contract: 'renulus-backend-bundle/1', node: 'node/node.exe', python: 'python/python.exe', entrypoint: 'launch.mjs' }));
    const launch = prepareSelectedOwnerLaunch({ selection, python: path.join(bundle, 'python', 'python.exe'), packaged: true, bundleRoot: bundle, workspace: scratch, port: 18777, node: 'C:\\ignored\\node.exe' });
    const identity = desktopProfileIdentity(root);
    const resources = path.join(root, 'desktop', 'backend-target-resources.json');
    expect(launch).toEqual({ cwd: bundle, runtimeRoot: path.join(bundle, 'runtime'), args: ['-I', '-B', '-X', 'utf8', '-m', 'renulus.workers.profile_owner',
      '--profile', root, '--node', path.join(bundle, 'node', 'node.exe'), '--entrypoint', path.join(bundle, 'launch.mjs'),
      '--profile-id', identity.profile_id, '--domain-store-id', identity.domain_store_id, '--runtime-store-id', identity.runtime_store_id,
      '--', '--target', '--selected-owner', '--profile', selection.generationRoot, '--port', '18777',
      '--python', path.join(bundle, 'python', 'python.exe'), '--source-root', bundle, '--target-resources', resources] });
    const written = JSON.parse(readFileSync(resources, 'utf8'));
    expect(written.helpers.helpers_root).toBe(path.join(bundle, 'helper-assets'));
    expect(written.identity.process_generation).toMatch(/^[a-f0-9]{32}$/);
    expect(written.evidence).toEqual([]);
    expect(written.native.grant_token_sha256).toMatch(/^[a-f0-9]{64}$/);
    for (const directory of ['originals', 'native-grants']) expect(lstatSync(path.join(selection.generationRoot, directory)).isDirectory()).toBe(true);
  });

  it('requires an explicit development Node and the built backend entry', () => {
    const selection = ts();
    const workspace = path.join(scratch, 'workspace');
    mkdirSync(path.join(workspace, 'packages', 'backend', 'dist'), { recursive: true });
    mkdirSync(path.join(root, 'desktop'));
    const python = path.join(scratch, 'python.exe'), node = path.join(scratch, 'node.exe');
    writeFileSync(python, ''); writeFileSync(node, '');
    const options = { selection, python, packaged: false, bundleRoot: path.join(scratch, 'none'), workspace, port: 1 };
    expect(() => prepareSelectedOwnerLaunch(options)).toThrow(/RENULUS_NODE/);
    expect(() => prepareSelectedOwnerLaunch({ ...options, node })).toThrow(/packages\/backend\/dist/);
    writeFileSync(path.join(workspace, 'packages', 'backend', 'dist', 'main.mjs'), '');
    const launch = prepareSelectedOwnerLaunch({ ...options, node });
    expect(launch.args.slice(0, 5)).toEqual(['-B', '-X', 'utf8', '-m', 'renulus.workers.profile_owner']);
    expect(launch.args).toContain(path.join(workspace, 'packages', 'backend', 'dist', 'main.mjs'));
    expect(JSON.parse(readFileSync(path.join(root, 'desktop', 'backend-target-resources.json'), 'utf8')).helpers.helpers_root).toBe(path.join(root, 'helpers'));
  });
});
