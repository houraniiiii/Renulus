// SPDX-License-Identifier: MIT
import path from 'node:path';
import { lstat, open, readdir } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import type { ContentPorts } from '../http/content-commands.ts';
import { reject } from '../storage/contracts.ts';
import { createEngineArtifacts } from './artifacts.ts';
import type { WorkerChannel } from './channel.ts';

export function createWorkerContent(channel: WorkerChannel, maxChunkBytes: number, packRoot: string): ContentPorts {
  const artifacts = createEngineArtifacts(channel, maxChunkBytes);
  const root = path.resolve(packRoot);
  return { async validatePack(selected) {
    const candidate = path.resolve(root, selected);
    const relative = path.relative(root, candidate);
    if (!selected || selected.length > 200 || path.isAbsolute(relative) || relative === '..' || relative.startsWith('..' + path.sep)) reject('invalid_pack_path');
    const files: Record<string, string> = Object.create(null);
    try {
      let directory = root;
      for (const part of ['', ...relative.split(path.sep).filter(Boolean)]) {
        directory = path.join(directory, part);
        const stat = await lstat(directory);
        if (!stat.isDirectory() || stat.isSymbolicLink()) reject('invalid_pack_path');
      }
      const entries = (await readdir(candidate)).filter(name => name.endsWith('.json'));
      if (!entries.length || entries.length > 128) reject('invalid_content_pack');
      let total = 0;
      for (const name of entries) {
        const filename = path.join(candidate, name), stat = await lstat(filename);
        if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1 || stat.size > 8 * 1024 * 1024) reject('invalid_content_pack');
        const file = await open(filename, 'r');
        try {
          const current = await file.stat();
          if (current.dev !== stat.dev || current.ino !== stat.ino) reject('invalid_pack_path');
          const bytes = Buffer.alloc(8 * 1024 * 1024 + 1);
          let size = 0, read;
          do { read = (await file.read(bytes, size, bytes.length - size, size)).bytesRead; size += read; } while (read && size < bytes.length);
          if (size > 8 * 1024 * 1024 || (total += size) > 40 * 1024 * 1024) reject('invalid_content_pack');
          files[name] = bytes.subarray(0, size).toString('base64');
        } finally { await file.close(); }
      }
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error && ['ENOENT', 'ENOTDIR', 'EACCES'].includes(String(error.code))) reject('invalid_content_pack');
      throw error;
    }
    const binding = { operation_id: 'content_' + randomUUID().replaceAll('-', ''), attempt_id: 'validate' };
    const expires = Date.now() + 120_000;
    const input = await artifacts.upload(Buffer.from(JSON.stringify(files)), binding, ['read'], expires);
    const output = artifacts.output(64 * 1024 * 1024, expires);
    try {
      const reference = await artifacts.run('content.validate', { artifact_handle: input.artifact_handle,
        artifact_revision: input.artifact_revision, offset: 0, length: input.bytes, output }, binding);
      return JSON.parse((await artifacts.read(reference, output.max_bytes, binding)).toString('utf8'));
    } catch (error) {
      if (error && typeof error === 'object' && 'code' in error && error.code === 'invalid_content_pack') reject('invalid_content_pack');
      throw error;
    } finally {
      await artifacts.release(input.artifact_handle, binding);
      await artifacts.release(output.artifact_handle, binding);
    }
  } };
}
