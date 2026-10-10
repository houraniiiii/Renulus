import { api } from '../../platform/api';
import type { HomePreferences, HomeState } from './types';

export const readHome = (signal?: AbortSignal) => api<HomeState>('/home', { signal });
export const refreshHome = (signal?: AbortSignal) => api<HomeState>('/home/suggestions/refresh', {
  method: 'POST', signal, headers: { 'Idempotency-Key': crypto.randomUUID() },
});
export const readName = (signal?: AbortSignal) => api<HomePreferences>('/home/preferences', { signal });
export const saveName = (doctor_name: string | null, expected_revision: number, key: string) =>
  api<HomePreferences>('/home/preferences', { method: 'PUT', headers: { 'Idempotency-Key': key },
    body: { doctor_name, expected_revision } });
