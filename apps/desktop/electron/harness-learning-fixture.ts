import path from 'node:path';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync } from 'node:fs';
import type { DesktopProfile } from './profile';

export type HarnessLearningFixtureLaunch = Readonly<{
  kind: 'harness-learning-synthetic-v1';
  startupDocument: string;
  startupSha256: string;
  helperAssets: string;
}>;
const pinnedNode = path.resolve('C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe');
function denied(): never { throw new Error('The fixed background learning fixture launch is invalid.'); }
function keys(value: unknown, expected: string[]): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join(',') === expected.sort().join(',');
}
function local(value: unknown): value is string {
  return typeof value === 'string' && path.isAbsolute(value) && !value.startsWith('\\')
    && !value.startsWith('//') && !value.split(/[\/]/).some(part => part === '..' || part === '.')
    && !/[\x00-\x1f]/.test(value) && path.resolve(value) !== path.parse(value).root;
}
function noLinks(file: string) {
  for (let cursor = path.resolve(file);;) {
    if (lstatSync(cursor).isSymbolicLink()) denied();
    const parent = path.dirname(cursor); if (parent === cursor) return; cursor = parent;
  }
}

export function validateHarnessLearningFixture(option: HarnessLearningFixtureLaunch, profile: DesktopProfile,
  workspace: string, packaged: boolean): void {
  try {
    const owner = process.env.RENULUS_BACKGROUND_OWNER_PID;
    if (packaged || process.env.RENULUS_BACKGROUND_TEST !== '1' || process.env.RENULUS_BACKEND_URL
      || process.env.RENULUS_BACKGROUND_HARNESS_SETTINGS !== undefined || !local(process.env.RENULUS_PYTHON)
      || !/^[1-9][0-9]*$/.test(owner ?? '') || !Number.isSafeInteger(Number(owner)) || Number(owner) === process.pid
      || !keys(option, ['kind', 'startupDocument', 'startupSha256', 'helperAssets'])
      || option.kind !== 'harness-learning-synthetic-v1' || !local(option.startupDocument)
      || !local(option.helperAssets) || !/^[a-f0-9]{64}$/.test(option.startupSha256)) denied();
    const directory = path.dirname(profile.root), name = path.basename(directory);
    const number = /^startup-([1-9][0-9]*)\.json$/.exec(path.basename(option.startupDocument));
    const relative = path.relative(directory, option.helperAssets), reverse = path.relative(option.helperAssets, directory);
    const contains = (value: string) => value === '' || value !== '..' && !value.startsWith('..' + path.sep) && !path.isAbsolute(value);
    if (path.basename(profile.root) !== 'p' || !/^s-[a-f0-9]{8}$/.test(name) || !number
      || contains(relative) || contains(reverse) || path.dirname(option.startupDocument) !== path.join(directory, 'out')) denied();
    noLinks(option.startupDocument); noLinks(profile.root); noLinks(option.helperAssets);
    if (!lstatSync(option.helperAssets).isDirectory() || !lstatSync(option.startupDocument).isFile()
      || lstatSync(option.startupDocument).size > 262144) denied();
    const raw = readFileSync(option.startupDocument);
    if (raw.length > 262144 || createHash('sha256').update(raw).digest('hex') !== option.startupSha256) denied();
    const data = JSON.parse(raw.toString('utf8'));
    if (!keys(data, ['version', 'process', 'artifact_root', 'candidate_root', 'attempt_timeout', 'initialize_new'])
      || data.version !== 1 || data.initialize_new !== (number[1] === '1') || data.attempt_timeout !== 45
      || data.artifact_root !== path.join(directory, 'a') || data.candidate_root !== path.join(directory, 'k')
      || !keys(data.process, ['node_executable', 'host_entry', 'profile_root', 'profile_id', 'store_id',
        'domain_store_id', 'domain_path', 'max_inflight', 'max_domain_inflight', 'max_frame_bytes', 'start_timeout'])) denied();
    const nativeProcess = data.process, identity = 'synthetic-learning-' + name;
    if (nativeProcess.node_executable !== pinnedNode || nativeProcess.host_entry !== path.join(workspace, 'packages/harness/src/main.mjs')
      || nativeProcess.profile_root !== profile.root || nativeProcess.profile_id !== identity
      || nativeProcess.store_id !== identity + '-runtime' || nativeProcess.domain_store_id !== identity + '-domain'
      || nativeProcess.domain_path !== 'state/renulus.sqlite3' || nativeProcess.max_inflight !== 1
      || nativeProcess.max_domain_inflight !== 1 || nativeProcess.max_frame_bytes !== 65536 || nativeProcess.start_timeout !== 45) denied();
  } catch { denied(); }
}

export function resolveHarnessLearningFixture(profile: DesktopProfile, packaged: boolean, workspace: string):
  { profile: DesktopProfile; learningFixture?: HarnessLearningFixtureLaunch } {
  const raw = process.env.RENULUS_BACKGROUND_HARNESS_LEARNING;
  if (raw === undefined) return { profile };
  let option: HarnessLearningFixtureLaunch;
  try {
    if (raw.length > 16384) denied();
    option = JSON.parse(raw);
    if (JSON.stringify(option) !== raw) denied();
  } catch { denied(); }
  validateHarnessLearningFixture(option, profile, workspace, packaged);
  const desktop = path.join(path.dirname(profile.root), 'd');
  return { profile: { ...profile, desktop, session: path.join(desktop, 'session') },
    learningFixture: Object.freeze(option) };
}
