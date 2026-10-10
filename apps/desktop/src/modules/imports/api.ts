import { api } from '../../platform/api';
import type { ImportCancellation, ImportDraft, ImportIntent, ImportOriginal, ImportPage } from './types';

export const importBase = '/assessment/imports';
export const importPath = (id: string) => importBase + '/' + encodeURIComponent(id);
export const listImports = (signal?: AbortSignal) => api<ImportPage>(importBase, { signal });
export const getImport = (id: string, signal?: AbortSignal) => api<ImportDraft>(importPath(id), { signal });
export const getImportOriginal = (id: string, signal?: AbortSignal) => api<ImportOriginal>(importPath(id) + '/original', { signal });
export const createImport = (intent: ImportIntent, idempotency_key: string, signal?: AbortSignal) =>
  api<ImportDraft>(importBase, { method: 'POST', body: { ...intent, idempotency_key }, signal });
export const cancelImport = (id: string, idempotency_key: string, signal?: AbortSignal) =>
  api<ImportCancellation>(importPath(id) + '/cancel', { method: 'POST', body: { idempotency_key }, signal });
