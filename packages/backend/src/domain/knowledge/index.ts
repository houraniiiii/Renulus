// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import type { createEngineArtifacts } from '../../workers/artifacts.ts';
import { integer, reject, text } from '../../storage/contracts.ts';
import { eligibleKnowledge, validateImportRequest, validateReaderRequest } from '../../storage/knowledge.ts';
import type { ContentReference, ImportIntent, ImportRequest, Json, KnowledgeNativeIO, KnowledgeStorage, Metadata, Passage, ReaderPayload, ReaderRequest, Rights, SourcePin } from './contracts.ts';
export type * from './contracts.ts';

const sha = (body: Uint8Array) => createHash('sha256').update(body).digest('hex');
const failCode = (error: unknown) => error && typeof error === 'object' && 'code' in error && /^[a-z0-9_-]{1,128}$/.test(String(error.code)) ? String(error.code) : 'import_failed';
const suffixes: Record<string, string> = { 'text/plain': 'txt', 'text/markdown': 'md', 'text/csv': 'csv', 'text/html': 'html',
  'application/xml': 'xml', 'text/xml': 'xml', 'application/pdf': 'pdf', 'image/png': 'png', 'image/jpeg': 'jpg', 'image/tiff': 'tiff',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx' };
export function ownNoteRights(): Rights { return { display: true, cache: true, index: true, embedding: true, model_input: true, derivation: true,
  evaluation: false, redistribution: false, licence: 'user-owned', permission_reference: 'User deliberately added their own text to the library', attribution: '' }; }
export interface KnowledgeDomainOptions { storage: KnowledgeStorage; engines: ReturnType<typeof createEngineArtifacts>; native: KnowledgeNativeIO }
export function createKnowledgeDomain({ storage, engines, native }: KnowledgeDomainOptions) {
  let closed = false;
  const operations = new Set<Promise<unknown>>(), controllers = new Set<AbortController>();
  function operation<T>(signal: AbortSignal | undefined, run: (signal: AbortSignal) => Promise<T>): Promise<T> {
    if (closed) reject('knowledge_closed');
    const controller = new AbortController(); controllers.add(controller);
    const cancel = () => controller.abort(); signal?.addEventListener('abort', cancel, { once: true }); if (signal?.aborted) cancel();
    const task = Promise.resolve().then(() => { controller.signal.throwIfAborted(); return run(controller.signal); }).finally(() => {
      controllers.delete(controller); signal?.removeEventListener('abort', cancel); operations.delete(task);
    }); operations.add(task); return task;
  }
  async function current(i: ImportIntent, signal: AbortSignal) {
    signal.throwIfAborted(); const result = await storage.command({ type: 'knowledge.import.check', intentId: i.id }); signal.throwIfAborted(); return result;
  }
  async function recheck(pin: SourcePin, signal: AbortSignal, use: 'display' | 'model_input' = 'display') {
    signal.throwIfAborted(); await storage.command({ type: 'knowledge.source.recheck', pin, operation: use }); signal.throwIfAborted();
  }
  async function readBody(pin: SourcePin, signal: AbortSignal) {
    const body = await native.read(pin, signal); if (body.byteLength !== pin.bytes || sha(body) !== pin.sha256) reject('reader_original_integrity');
    await recheck(pin, signal); return body;
  }
  async function removeDerived(ids: string[], binding: { operation_id: string; attempt_id: string }) {
    for (let offset = 0; offset < ids.length; offset += 256) {
      const batch = ids.slice(offset, offset + 256), output = engines.output(16384, Date.now() + 120_000);
      try { await engines.run('library.remove', { revision_ids: batch, output }, binding);
        await storage.command({ type: 'knowledge.cleanup', revisionIds: batch });
      } finally { await engines.release(output.artifact_handle, binding); }
    }
  }
  async function importOriginal(request: ImportRequest, source: { text: string } | { selected_handle: string }, signal: AbortSignal) {
    validateImportRequest(request); const format = suffixes[request.media_type]; if (!format) reject('document_format_unsupported');
    let i = await storage.command({ type: 'knowledge.import.begin', request }); if (i.state === 'ready') return i;
    const binding = { operation_id: i.job_id, attempt_id: i.id }; let staged = false, reserved = false;
    const handles = new Set<string>();
    try {
      await native.reserve(i); reserved = true; await current(i, signal);
      const body = 'text' in source ? Buffer.from(source.text, 'utf8') : await native.readSelection({ handle: source.selected_handle, intent: i }, signal);
      if (body.byteLength !== request.bytes || sha(body) !== request.sha256) reject('original_digest_mismatch');
      await current(i, signal);
      if (i.state === 'prepared') {
        const published = await native.publish({ intent: i, body }, signal); await current(i, signal);
        i = await storage.command({ type: 'knowledge.import.original', intentId: i.id, originalHandle: published.original_handle });
      }
      if (!eligibleKnowledge(request.metadata, request.rights)) reject('import_index_rights_denied');
      const original = await engines.upload(body, binding, ['read', 'extract'], Date.now() + 600_000, signal); handles.add(original.artifact_handle);
      const output = engines.output(32 * 1024 * 1024, Date.now() + 600_000); handles.add(output.artifact_handle);
      const ref = await engines.run('document.extract', { artifact_handle: original.artifact_handle, artifact_revision: original.artifact_revision,
        offset: 0, length: original.bytes, format: format as 'txt', title: request.title.slice(0, 256), output }, binding, signal);
      const extracted = JSON.parse((await engines.read(ref, output.max_bytes, binding, signal)).toString('utf8'));
      // Selected extractor already runs Docling HybridChunker with the pinned 480-token budget.
      if (extracted.tag !== 'document' || !Array.isArray(extracted.passages) || extracted.passages.length > 12000) reject('document_invalid');
      const passages: Passage[] = extracted.passages.map((p: any, n: number) => {
        text(p.text, 1, 200000); text(p.context_text, 1, 200000);
        if (!Array.isArray(p.locators) || !Array.isArray(p.headings)) reject('document_invalid');
        return { id: 'passage_' + createHash('sha256').update(i.revision_id + ':' + n).digest('hex').slice(0, 32),
          text: p.text, context_text: p.context_text, locators: p.locators, headings: p.headings };
      });
      if (!passages.length) reject('document_empty');
      // Page masks remain canonical; excluded pages never reach the derived index.
      const excluded = new Set(request.metadata.excluded_pages ?? []);
      const accepted = passages.filter(p => !p.locators.some(l => l && typeof l === 'object' && !Array.isArray(l) && excluded.has(Number(l.page))));
      if (!accepted.length) reject('document_empty');
      await current(i, signal);
      const batch = await engines.upload(Buffer.from(JSON.stringify({ passages: accepted.map(p => ({ passage_id: p.id, text: p.context_text })) })), binding, ['read'], Date.now() + 600_000, signal); handles.add(batch.artifact_handle);
      const stageOutput = engines.output(2 * 1024 * 1024, Date.now() + 600_000); handles.add(stageOutput.artifact_handle);
      // Staged indexes grant no eligibility; the final canonical ready transaction does.
      staged = true;
      const stagedRef = await engines.run('library.stage', { artifact_handle: batch.artifact_handle, artifact_revision: batch.artifact_revision,
        offset: 0, length: batch.bytes, document_id: i.document_id, revision_id: i.revision_id, output: stageOutput }, binding, signal);
      const receipt = JSON.parse((await engines.read(stagedRef, stageOutput.max_bytes, binding, signal)).toString('utf8'));
      if (receipt.tag !== 'library_staged' || receipt.document_id !== i.document_id || receipt.revision_id !== i.revision_id || receipt.eligible !== false || receipt.input_sha256 !== batch.artifact_sha256 ||
        JSON.stringify(receipt.passage_ids) !== JSON.stringify(accepted.map(p => p.id))) reject('library_stage_invalid');
      await current(i, signal);
      i = await storage.command({ type: 'knowledge.import.ready', intentId: i.id, extraction: extracted as Json, passages: accepted,
        embeddingModel: 'BAAI/bge-small-en-v1.5', chunkTokens: 480 });
      await native.settle(i); return i;
    } catch (error) {
      if (i.state === 'ready') throw error; // A settlement failure cannot unpublish an already committed revision.
      // Local failure recording/cleanup retains immutable originals and prior active revision.
      i = await storage.command({ type: 'knowledge.import.fail', intentId: i.id, code: failCode(error) });
      if (staged) await removeDerived([i.revision_id], binding);
      if (reserved) await native.settle(i); throw error;
    } finally { for (const handle of handles) await engines.release(handle, binding); }
  }
  const api = {
    importSelected(request: ImportRequest, selectedHandle: string, signal?: AbortSignal) {
      text(selectedHandle, 1, 256); return operation(signal, s => importOriginal(request, { selected_handle: selectedHandle }, s));
    },
    importText(request: ImportRequest, body: string, signal?: AbortSignal) {
      text(body, 1, 4 * 1024 * 1024); if (Buffer.byteLength(body) > 4 * 1024 * 1024 || body.includes('\0') || !body.trim()) reject('note_limit');
      return operation(signal, s => importOriginal(request, { text: body }, s));
    },
    saveNote(input: { title: string; text: string; idempotency_key: string; document_id?: string | null; expected_revision_id?: string | null; project_id?: string | null }, signal?: AbortSignal) {
      return operation(signal, async s => {
        text(input.title, 1, 500); text(input.text, 1, 4 * 1024 * 1024); if (Buffer.byteLength(input.text) > 4 * 1024 * 1024 || input.text.includes('\0') || !input.text.trim()) reject('note_limit');
        let rights = ownNoteRights(), metadata: Metadata = { source_id: 'R02', source_owner: 'User', access_class: 'user-owned', asset_role: ['study-note'] };
        if (input.document_id) {
          const previous = await storage.command({ type: 'knowledge.notes.pin', documentId: input.document_id, revisionId: input.expected_revision_id ?? null });
          rights = previous.pin.rights; metadata = previous.pin.metadata;
        }
        const body = Buffer.from(input.text, 'utf8'); metadata = { ...metadata, original_sha256: sha(body),
          notes: [...(metadata.notes as string[] ?? []).filter(v => !v.startsWith('renulus:note-title:')), 'renulus:note-title:' + input.title] };
        const request: ImportRequest = { title: input.title, media_type: 'text/plain', bytes: body.byteLength, sha256: sha(body), metadata, rights,
          document_id: input.document_id ?? null, expected_revision_id: input.expected_revision_id ?? null, project_id: input.project_id ?? null, note: true, idempotency_key: input.idempotency_key };
        const i = await importOriginal(request, { text: input.text }, s);
        return api.note(i.document_id, i.revision_id, s);
      });
    },
    note(documentId: string, revisionId: string | null = null, signal?: AbortSignal) {
      return operation(signal, async s => {
        const { summary, pin } = await storage.command({ type: 'knowledge.notes.pin', documentId, revisionId });
        if (pin.bytes > 4 * 1024 * 1024) reject('note_limit');
        const body = await readBody(pin, s); let content: string;
        try { content = new TextDecoder('utf-8', { fatal: true }).decode(body); } catch { reject('reader_encoding'); }
        await recheck(pin, s); return { ...summary, text: content };
      });
    },
    resolve(request: ReaderRequest, signal?: AbortSignal) {
      validateReaderRequest(request); return operation(signal, async s => {
        const pin = await storage.command({ type: 'knowledge.source.pin', request, operation: 'display' });
        const body = await readBody(pin, s); let payload: ReaderPayload | null = null, error: { code: string; message: string } | null = null;
        try { payload = await native.payload({ pin, request: position(request), body }, s); } catch (e) { const code = failCode(e); error = { code, message: code }; }
        await recheck(pin, s);
        const state = payload ? 'ready' : error?.code === 'reader_format_unsupported' ? 'unsupported' : 'failed';
        return { schema_version: 'reader/1', reference: request.reference, title: pin.title, media_type: pin.media_type, authority: 'knowledge',
          original: { id: pin.revision_id, sha256: pin.sha256, bytes: pin.bytes, filename: pin.filename, available: true },
          attachment_revision: pin.attachment_revision, preview_state: state, policy_revision: pin.policy_revision, context_epoch: pin.context_epoch,
          extraction_state: payload && (payload.blocks?.length || payload.table) ? 'ready' : 'unavailable',
          capabilities: { read: !!payload, original: true, passage: pin.rights.model_input && !!payload && !!(payload.blocks?.length || payload.table), ocr: false, model_image: false }, payload, error };
      });
    },
    asset(request: ReaderRequest & { asset_id: string; original_sha256: string }, signal?: AbortSignal) {
      const { asset_id, original_sha256, ...reader } = request; text(asset_id, 1, 160); validateReaderRequest(reader);
      return operation(signal, async s => {
        const pin = await storage.command({ type: 'knowledge.source.pin', request: reader, operation: 'display' });
        if (pin.sha256 !== original_sha256) reject('reader_revision_conflict');
        const body = await readBody(pin, s), asset = await native.asset({ pin, request: position(reader), body, asset_id }, s);
        await recheck(pin, s); return asset;
      });
    },
    original(request: ReaderRequest, signal?: AbortSignal) {
      validateReaderRequest(request); return operation(signal, async s => {
        const pin = await storage.command({ type: 'knowledge.source.pin', request, operation: 'display' });
        const body = await readBody(pin, s); await recheck(pin, s); return { body, filename: pin.filename, media_type: pin.media_type };
      });
    },
    passage(request: ReaderRequest & { locator: import('./contracts.ts').Locator; original_sha256: string }, signal?: AbortSignal) {
      const { locator, original_sha256, ...reader } = request; validateReaderRequest({ ...reader, reference: { ...reader.reference, locator } });
      return operation(signal, async s => {
        const selected = { ...reader, reference: { ...reader.reference, locator } };
        const pin = await storage.command({ type: 'knowledge.source.pin', request: selected, operation: 'model_input' });
        if (pin.sha256 !== original_sha256) reject('reader_revision_conflict');
        const body = await readBody(pin, s), payload = await native.payload({ pin, request: position(selected), body }, s);
        let content: string | undefined;
        if (locator.kind === 'text') { const block = payload.blocks.find(b => b.item_ref === locator.item_ref); const chars = block ? [...block.text] : [];
          if (locator.end <= chars.length) content = chars.slice(locator.start, locator.end).join(''); }
        if (locator.kind === 'pdf' && payload.kind === 'pdf') content = payload.blocks.map(b => b.text).join('\n');
        if (locator.kind === 'table' && payload.table) { const t = payload.table;
          if (t.format === locator.format && (t.sheet_name ?? null) === (locator.sheet_name ?? null) && locator.first_row >= t.first_row && locator.last_row < t.first_row + t.rows.length && locator.last_column <= t.total_columns)
            content = t.rows.slice(locator.first_row - t.first_row, locator.last_row - t.first_row + 1).map(row => row.slice(locator.first_column - 1, locator.last_column).map(c => c.display).join('\t')).join('\n'); }
        if (!content?.trim() || [...content].length > 8000) reject('reader_selection_unavailable');
        await recheck(pin, s, 'model_input'); return { text: content, reference: selected.reference, title: pin.title };
      });
    },
    source(request: ReaderRequest, maxCharacters = 8000, signal?: AbortSignal) {
      validateReaderRequest(request); integer(maxCharacters, 1, 16000);
      return operation(signal, async s => {
        const pin = await storage.command({ type: 'knowledge.source.pin', request, operation: 'model_input' });
        const body = await readBody(pin, s), payload = await native.payload({ pin, request: position(request), body }, s);
        const content = payload.table ? payload.table.rows.map(row => row.map(c => c.display).join('\t')).join('\n') : payload.blocks.map(b => b.text).join('\n');
        await recheck(pin, s, 'model_input');
        const dependency = await storage.command({ type: 'knowledge.source.dependency', pin });
        return { text: [...content].slice(0, maxCharacters).join(''), reference: request.reference, title: pin.title,
          truncated: [...content].length > maxCharacters, source_sha256: pin.sha256, dependency };
      });
    },
    handoff(request: ReaderRequest, action: 'open' | 'save', destinationHandle: string | null, signal?: AbortSignal) {
      validateReaderRequest(request); if (!['open', 'save'].includes(action) || action === 'save' && !destinationHandle) reject('original_handoff_invalid');
      return operation(signal, async s => {
        const pin = await storage.command({ type: 'knowledge.source.pin', request, operation: 'display' });
        await readBody(pin, s); await recheck(pin, s);
        const result = await native.handoff({ pin, action, destination_handle: destinationHandle }, s); await recheck(pin, s); return result;
      });
    },
    delete(documentId: string, expectedRevisionId: string, idempotencyKey: string, note = false, signal?: AbortSignal) {
      return operation(signal, async s => {
        s.throwIfAborted(); const result = await storage.command({ type: 'knowledge.delete', documentId, expectedRevisionId, idempotencyKey, note });
        // Canonical tombstones suppress reads immediately, even if native cleanup fails.
        try { await removeDerived(result.revision_ids, { operation_id: 'delete_' + sha(Buffer.from(idempotencyKey)).slice(0, 32), attempt_id: 'cleanup' }); }
        catch { return { ...result, cleanup_pending: true }; }
        return { ...result, cleanup_pending: false };
      });
    },
    async close() { closed = true; controllers.forEach(c => c.abort()); await Promise.allSettled([...operations]); },
  };
  return api;
}
export type KnowledgeDomain = ReturnType<typeof createKnowledgeDomain>;
/** UI positions and all four locator families share the retained Python reader contract. */
export function position(request: ReaderRequest): ReaderRequest {
  const r = structuredClone(request), loc = r.reference.locator;
  if (loc?.kind === 'pdf' && r.page === undefined) r.page = loc.physical_page;
  if (loc?.kind === 'image' && r.page === undefined) r.page = loc.frame ?? 1;
  if (loc?.kind === 'table') { if (r.sheet === undefined) r.sheet = loc.sheet_name ?? null; if (r.first_row === undefined) r.first_row = loc.first_row; }
  if (loc?.kind === 'text' && loc.item_ref.startsWith('reader-v1:pdf:') && r.page === undefined) { r.page = Number(loc.item_ref.split(':').at(-1)); integer(r.page, 1, 300); }
  return r;
}
