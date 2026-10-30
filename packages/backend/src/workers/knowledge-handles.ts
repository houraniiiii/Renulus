// SPDX-License-Identifier: MIT
import { createHash, randomBytes } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

/** Main-process only. Each callback must be a direct Electron chooser result.
 * Tests inject a chooser over owned synthetic files; no HTTP/model path setter.
 * The one-use binary grant keeps native paths outside the worker JSON protocol.
 */
export async function createKnowledgeHandleAuthority(options: {
  root: string;
  chooseSelection: () => Promise<string | null>;
  chooseDestination: () => Promise<string | null>;
}) {
  if (!path.isAbsolute(options.root) || path.parse(options.root).root === path.resolve(options.root)) throw new Error('native_grant_root');
  const token = randomBytes(32);
  const root = path.join(options.root, 'chooser-' + randomBytes(16).toString('hex'));
  await mkdir(root, { recursive: true });
  async function issue(kind: 1 | 2, choose: () => Promise<string | null>) {
    const selected = await choose();
    if (selected === null) return null;
    if (!path.isAbsolute(selected) || selected.includes('\0') || selected.length > 4096) throw new Error('native_selection_invalid');
    const handle = 'selected_' + randomBytes(24).toString('hex');
    const header = Buffer.alloc(49);
    header.write('RENKIO1\0', 0, 'ascii'); token.copy(header, 8); header[40] = kind;
    header.writeBigUInt64LE(BigInt(Date.now() + 600_000), 41);
    await writeFile(path.join(root, handle), Buffer.concat([header, Buffer.from(selected, 'utf16le')]), { flag: 'wx', mode: 0o600 });
    return handle;
  }
  const select = () => issue(1, options.chooseSelection);
  return { launch: { grants_root: root, grant_token_sha256: createHash('sha256').update(token).digest('hex') },
    select, grantSelection: select, destination: () => issue(2, options.chooseDestination) };
}
