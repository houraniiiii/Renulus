// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import { createHash } from 'node:crypto';
import { exact, reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
import { commandKey, commandNumber } from './project-commands.ts';
import { ownNoteRights, type KnowledgeDomain } from '../domain/knowledge/index.ts';
import type { ImportRequest, KnowledgeStorage, Metadata, ReaderRequest } from '../domain/knowledge/contracts.ts';

export type KnowledgeResponse = { status: number; value: unknown } | { status: number; body: Uint8Array; headers: Record<string, string> };
const bytesResponse = (body: Uint8Array, type: string, filename?: string): KnowledgeResponse => ({ status: 200, body, headers: {
  'content-type': type, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff', 'content-security-policy': "default-src 'none'; sandbox",
  ...(filename ? { 'content-disposition': "attachment; filename*=UTF-8''" + encodeURIComponent(filename) } : {}) } });
const accepted = (i: { document_id: string; revision_id: string; state: string; job_id: string }) =>
  ({ document_id: i.document_id, revision_id: i.revision_id, status: i.state, job: { id: i.job_id, state: i.state }, maintenance_pending: false });
const refusal = (status: number, code: string, message: string) => ({ status, value: { error: { code, message, retryable: false } } });
const rawMedia: Record<string, string> = { '.pdf': 'application/pdf', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.tif': 'image/tiff',
  '.tiff': 'image/tiff', '.txt': 'text/plain', '.md': 'text/markdown', '.csv': 'text/csv', '.html': 'text/html', '.htm': 'text/html', '.xml': 'application/xml',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation' };
const MAX_FILE = 64 * 1024 * 1024;
/** Existing raw-file route: scope/options in a header, original bytes as the body (never multipart or disk staging). Old statuses/codes are kept. */
async function rawFileImport(request: IncomingMessage, knowledge: KnowledgeDomain): Promise<KnowledgeResponse> {
  let options: Record<string, unknown>;
  try {
    const header = String(request.headers['x-renulus-import-options']); if (header.length > 65536) throw new Error('options');
    options = { title: 'Personal study note', metadata: { source_id: 'R02' }, rights: ownNoteRights(), document_id: null, expected_revision_id: null, reserved: false, ...JSON.parse(header) };
    exact(options, ['title', 'metadata', 'rights', 'document_id', 'expected_revision_id', 'reserved', 'scope', 'idempotency_key']); exact(options.scope, ['kind', 'entity_id']);
  } catch { return refusal(422, 'invalid_import_options', 'Check the file import scope and permissions'); }
  const scope = options.scope as { kind: unknown; entity_id: unknown };
  if (scope.kind !== 'personal-library' || scope.entity_id !== null || options.reserved !== false) return refusal(422, 'import_scope_denied', 'This import scope is not available');
  let suffix = '';
  try { suffix = /\.[A-Za-z0-9]{1,8}$/.exec(decodeURIComponent(String(request.headers['x-renulus-filename'] ?? '')))?.[0].toLowerCase() ?? ''; } catch { /* unsupported */ }
  const mediaType = rawMedia[suffix]; if (!mediaType) return refusal(415, 'unsupported_file', 'Choose a PDF, image, text or supported Office file');
  const declared = request.headers['content-length'];
  if (declared !== undefined && (!/^[0-9]{1,16}$/.test(declared) || Number(declared) > MAX_FILE)) return refusal(413, 'document_limit', 'The maximum file size is 64 MiB');
  const parts: Buffer[] = []; let size = 0;
  for await (const chunk of request) { size += chunk.length; if (size > MAX_FILE) return refusal(413, 'document_limit', 'The maximum file size is 64 MiB'); parts.push(chunk); }
  const data = Buffer.concat(parts);
  if (suffix === '.pdf' && !data.subarray(0, 1024).toString('latin1').trimStart().startsWith('%PDF-')) return refusal(422, 'malformed_pdf', 'The selected file has no PDF signature');
  if (!size) return refusal(422, 'invalid_import_options', 'Choose a file with content');
  const digest = createHash('sha256').update(data).digest('hex');
  const input: ImportRequest = { title: options.title as string, media_type: mediaType, bytes: size, sha256: digest, metadata: { ...options.metadata as Metadata, original_sha256: digest },
    rights: options.rights as ImportRequest['rights'], document_id: options.document_id as string | null, expected_revision_id: options.expected_revision_id as string | null, project_id: null, note: false, idempotency_key: options.idempotency_key as string };
  return { status: 202, value: accepted(await knowledge.importBytes(input, data)) };
}
export async function knowledgeCommand(request: IncomingMessage, url: URL, storage: KnowledgeStorage, knowledge?: KnowledgeDomain): Promise<KnowledgeResponse | undefined> {
  const path = url.pathname, result = (value: unknown, status = 200) => ({ status, value });
  const domain = () => { if (!knowledge) reject('knowledge_host_unavailable'); return knowledge; };
  if (path === '/api/v1/library/documents' && request.method === 'GET') return result(await storage.command({ type: 'knowledge.list', limit: commandNumber(url, 'limit', 100), offset: commandNumber(url, 'offset', 0), query: url.searchParams.get('query') ?? '', status: url.searchParams.get('status') }));
  const doc = /^\/api\/v1\/library\/documents\/([A-Za-z0-9_-]{1,128})$/.exec(path);
  if (doc && request.method === 'GET') return result(await storage.command({ type: 'knowledge.get', documentId: doc[1] }));
  if (doc && request.method === 'DELETE') {
    // No expected revision resolves the current one inside the synchronous canonical transaction.
    const deleted = await domain().delete(doc[1], url.searchParams.get('expected_revision_id'), commandKey(request));
    return result({ document_id: deleted.document_id, status: 'deleted', cleanup_pending: deleted.cleanup_pending });
  }
  if (path === '/api/v1/library/import/file' && request.method === 'POST' && request.headers['x-renulus-import-options'] !== undefined) return rawFileImport(request, domain());
  if (['/api/v1/library/import/text', '/api/v1/library/import/file'].includes(path) && request.method === 'POST') {
    const selected = path.endsWith('/file'), body = await readJsonObject(request, selected ? 128 * 1024 : 25 * 1024 * 1024);
    const normalized: Record<string, unknown> = { title: 'Personal study note', metadata: { source_id: 'R02' }, rights: selected ? undefined : ownNoteRights(), document_id: null,
      expected_revision_id: null, project_id: null, reserved: false, ...body };
    exact(normalized, [selected ? 'selected_handle' : 'text', 'title', 'metadata', 'rights', 'document_id', 'expected_revision_id', 'project_id', 'reserved', 'scope', 'idempotency_key', ...(selected ? ['media_type', 'sha256', 'bytes'] : [])]);
    exact(normalized.scope, ['kind', 'entity_id']); if (normalized.scope.kind !== 'personal-library' || normalized.scope.entity_id !== null || normalized.reserved !== false) reject('import_scope_denied');
    const text = normalized.text as string; if (!selected && typeof text !== 'string') reject('storage_invalid_command');
    const data = selected ? null : Buffer.from(text, 'utf8');
    const input: ImportRequest = { title: normalized.title as string, media_type: selected ? normalized.media_type as string : 'text/plain', bytes: selected ? normalized.bytes as number : data!.byteLength,
      sha256: selected ? normalized.sha256 as string : createHash('sha256').update(data!).digest('hex'), metadata: normalized.metadata as Metadata, rights: normalized.rights as ImportRequest['rights'],
      document_id: normalized.document_id as string | null, expected_revision_id: normalized.expected_revision_id as string | null, project_id: normalized.project_id as string | null, note: false, idempotency_key: normalized.idempotency_key as string };
    const i = selected ? await domain().importSelected(input, normalized.selected_handle as string) : await domain().importText(input, text);
    return result(accepted(i), 202);
  }
  if (path === '/api/v1/library/notes') {
    if (request.method === 'GET') return result(await storage.command({ type: 'knowledge.notes.list', projectId: url.searchParams.get('project_id'), limit: commandNumber(url, 'limit', 100), offset: commandNumber(url, 'offset', 0) }));
    if (request.method === 'POST') {
      const body = { project_id: null, ...await readJsonObject(request, 25 * 1024 * 1024) }; exact(body, ['title', 'text', 'idempotency_key', 'project_id']);
      return result(await domain().saveNote(body as never), 201);
    }
  }
  const note = /^\/api\/v1\/library\/notes\/([A-Za-z0-9_-]{1,128})$/.exec(path);
  if (note) {
    if (request.method === 'GET') return result(await domain().note(note[1], url.searchParams.get('revision_id')));
    if (request.method === 'PUT') { const body = await readJsonObject(request, 25 * 1024 * 1024); exact(body, ['title', 'text', 'idempotency_key', 'expected_revision_id']); return result(await domain().saveNote({ ...body, document_id: note[1] } as never)); }
    if (request.method === 'DELETE') return result(await domain().delete(note[1], url.searchParams.get('expected_revision_id') ?? '', commandKey(request), true));
  }
  const original = /^\/api\/v1\/library\/revisions\/([A-Za-z0-9_-]{1,128})\/original$/.exec(path);
  if (original && request.method === 'GET') { const downloaded = await domain().original({ reference: { target: { type: 'library_revision', id: original[1] } } }); return bytesResponse(downloaded.body, 'application/octet-stream', downloaded.filename); }
  const reader = /^\/api\/v1\/readers\/(resolve|asset|original|passage|open|save)$/.exec(path);
  if (reader && request.method === 'POST') {
    const body = await readJsonObject(request, 16384);
    if (reader[1] === 'resolve') return result(await domain().resolve(body as unknown as ReaderRequest));
    if (reader[1] === 'asset') return bytesResponse(await domain().asset(body as never), 'image/png');
    if (reader[1] === 'passage') return result(await domain().passage(body as never));
    if (reader[1] === 'open' || reader[1] === 'save') {
      const { destination_handle = null, ...position } = body;
      return result(await domain().handoff(position as unknown as ReaderRequest, reader[1], destination_handle as string | null));
    }
    const downloaded = await domain().original(body as unknown as ReaderRequest); return bytesResponse(downloaded.body, 'application/octet-stream', downloaded.filename);
  }
  return undefined;
}
