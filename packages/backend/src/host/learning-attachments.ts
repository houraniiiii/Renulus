// SPDX-License-Identifier: MIT
import { lstat, readFile, rm } from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { reject } from '../storage/contracts.ts';
import type { LearningStorage, SavedSendIntent } from '../domain/learning/contracts.ts';

async function owned(root: string, relative: string) {
  const base = path.resolve(root), target = path.resolve(base, relative);
  const parts = path.relative(base, target).split(path.sep);
  if (parts.some(p => p === '..' || p.includes(':')) || target === base) reject('attachment_cleanup_path');
  let current = base;
  for (const part of parts) {
    current = path.join(current, part);
    const stat = await lstat(current).catch(error => { if (error.code === 'ENOENT') return null; throw error; });
    if (!stat) break;
    if (stat.isSymbolicLink() || stat.isFile() && stat.nlink !== 1) reject('attachment_cleanup_path');
  }
  return target;
}
export async function readAttachmentImage(root: string, attachment: { id: string; path: string | null; bytes: number; sha256: string; mediaType: string }): Promise<NonNullable<SavedSendIntent['images']>[number]> {
  if (!attachment.path || attachment.bytes > 8 * 1024 * 1024) reject('learning_attachment_unavailable');
  const relative = path.relative(path.resolve(root), path.resolve(root, attachment.path));
  const directory = 'library/attachments/' + attachment.id;
  if (!relative.replaceAll('\\', '/').startsWith(directory + '/')) reject('learning_attachment_unavailable');
  const body = await readFile(await owned(root, relative));
  if (body.length !== attachment.bytes || createHash('sha256').update(body).digest('hex') !== attachment.sha256) reject('original_digest_mismatch');
  return { type: 'image', media_type: attachment.mediaType as 'image/png', data: body.toString('base64') };
}
export async function drainAttachmentCleanup(root: string, storage: LearningStorage) {
  const pending = await storage.command({ type: 'learning.attachment.cleanup', removed: [] });
  const removed: string[] = [];
  for (const entry of pending) {
    if (!/^[A-Za-z0-9_-]{1,128}$/.test(entry.attachment_id) || entry.relative_directory !== 'library/attachments/' + entry.attachment_id) reject('attachment_cleanup_path');
    try { await rm(await owned(root, entry.relative_directory), { recursive: true, force: true }); removed.push(entry.attachment_id); }
    catch { /* Locked originals retain their durable cleanup intent. */ }
  }
  await storage.command({ type: 'learning.attachment.cleanup', removed });
}
