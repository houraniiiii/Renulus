import path from 'node:path';
import { createHash } from 'node:crypto';

export interface DesktopProfile { root: string; desktop: string; session: string; instance: string }
export function resolveProfile(profile: string | undefined, packaged: boolean, localAppData?: string): DesktopProfile {
  let root = profile;
  if (!root && packaged && localAppData) root = path.join(localAppData, 'Renulus');
  if (!root || !path.isAbsolute(root)) throw new Error('An explicit absolute RENULUS_PROFILE is required for development.');
  root = path.resolve(root);
  if (root === path.parse(root).root) throw new Error('The state profile cannot be a filesystem root.');
  const instance = createHash('sha256').update(root.toLowerCase()).digest('hex').slice(0, 16);
  return { root, desktop: path.join(root, 'desktop'), session: path.join(root, 'desktop', 'session'), instance };
}

/** Environment allowlist prevents inherited provider keys or another app's config reaching Hermes. */
export function backendEnvironment(profile: DesktopProfile, token: string, runtimeRoot: string, upstreamRoot: string, inherited: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const result: NodeJS.ProcessEnv = {};
  for (const name of ['SystemRoot', 'SYSTEMROOT', 'WINDIR', 'PATH', 'Path', 'PATHEXT', 'TEMP', 'TMP', 'USERPROFILE', 'LOCALAPPDATA', 'APPDATA', 'COMSPEC']) {
    if (inherited[name]) result[name] = inherited[name];
  }
  return { ...result, PYTHONPATH: [runtimeRoot, upstreamRoot].join(path.delimiter), PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1', RENULUS_SESSION_TOKEN: token, HERMES_HOME: path.join(profile.root, 'hermes') };
}

export function allowedAuthorizationUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password && !url.port && url.hostname === 'auth.openai.com' && url.pathname === '/api/accounts/authorize';
  } catch { return false; }
}
