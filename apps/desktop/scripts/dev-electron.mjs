import { spawn } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import electron from 'electron';

const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const profile = process.env.RENULUS_PROFILE ?? path.join(desktop, 'test-results', 'native-' + randomUUID());
if (!path.isAbsolute(profile)) throw new Error('RENULUS_PROFILE must be absolute.');
mkdirSync(profile, { recursive: true });
// Build with the platform's npm CLI JS entry, avoiding cmd/batch shell quoting.
const npm = process.env.npm_execpath;
if (!npm) throw new Error('Run this launcher with npm run dev:electron.');
const build = spawn(process.execPath, [npm, 'run', 'build'], { cwd: desktop, stdio: 'inherit', windowsHide: true });
const code = await new Promise(resolve => { build.once('exit', resolve); build.once('error', () => resolve(1)); });
if (code !== 0) process.exit(Number(code ?? 1));
const child = spawn(electron, ['.'], { cwd: desktop, stdio: 'inherit', windowsHide: true, env: { ...process.env, RENULUS_PROFILE: profile } });
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
child.once('error', error => { console.error(error.message); process.exitCode = 1; });
child.once('exit', code => { process.exitCode = code ?? 1; });
