import { api } from '../../platform/api';
import type { GenerationCancellation, GenerationIntent, GenerationJob, GenerationJobPage } from './types';

export const generationBase = '/assessment/generation';
const jobPath = (id: string) => generationBase + '/jobs/' + encodeURIComponent(id);
export const listGenerationJobs = (signal?: AbortSignal) => api<GenerationJobPage>(generationBase + '/jobs', { signal });
export const getGenerationJob = (id: string, signal?: AbortSignal) => api<GenerationJob>(jobPath(id), { signal });
export const createGenerationJob = (intent: GenerationIntent, idempotency_key: string, signal?: AbortSignal) =>
  api<GenerationJob>(generationBase + '/jobs', { method: 'POST', body: { ...intent, idempotency_key }, signal });
export const createQuickPractice = (intent: Omit<GenerationIntent, 'count'>, idempotency_key: string, signal?: AbortSignal) =>
  api<GenerationJob>(generationBase + '/quick-practice', { method: 'POST', body: { ...intent, count: 5, idempotency_key }, signal });
export const retryGenerationJob = (id: string, idempotency_key: string, signal?: AbortSignal) =>
  api<GenerationJob>(jobPath(id) + '/retry', { method: 'POST', body: { idempotency_key }, signal });
export const cancelGenerationJob = (id: string, idempotency_key: string, signal?: AbortSignal) =>
  api<GenerationCancellation>(jobPath(id) + '/cancel', { method: 'POST', body: { idempotency_key }, signal });
export const acceptShorterGeneration = (id: string, accepted_count: number, idempotency_key: string, signal?: AbortSignal) =>
  api<GenerationJob>(jobPath(id) + '/accept-shorter', { method: 'POST', body: { accepted_count, idempotency_key }, signal });
