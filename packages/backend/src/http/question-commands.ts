// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { PendingQuestion } from '../plugins/questions.ts';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';

export interface QuestionCommands {
  list(): PendingQuestion[];
  answer(id: string, grantEpoch: number, answers: unknown): Promise<void>;
  reject(id: string): void;
}

/** Authenticated user answers for the native `question` tool; the model never reaches these routes. */
export async function questionCommand(request: IncomingMessage, url: URL, questions?: QuestionCommands): Promise<{ status: number; value: unknown } | undefined> {
  const match = /^\/api\/v1\/learning\/questions(?:\/([A-Za-z0-9_-]{1,128})\/(answer|reject))?$/.exec(url.pathname);
  if (!match) return undefined;
  if (!questions) reject('question_host_unavailable');
  const [, id, action] = match;
  if (!id) { if (request.method !== 'GET') reject('storage_invalid_command'); return { status: 200, value: questions.list() }; }
  if (request.method !== 'POST') reject('storage_invalid_command');
  if (action === 'reject') { exact(await readJsonObject(request, 1024), []); questions.reject(id); return { status: 200, value: { rejected: id } }; }
  const body = await readJsonObject(request, 64 * 1024); exact(body, ['grant_epoch', 'answers']);
  if (!Number.isSafeInteger(body.grant_epoch)) reject('storage_invalid_command');
  await questions.answer(id, body.grant_epoch as number, body.answers);
  return { status: 200, value: { answered: id } };
}
