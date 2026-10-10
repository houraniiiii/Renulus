import { api } from '../../platform/api';
import type { NightlyPreferencesUpdate, NightlyPreferencesValue, NightlyState } from './types';

export const readNightly = (signal?: AbortSignal) => api<NightlyState>('/nightly', { signal });
export const readPreferences = (signal?: AbortSignal) => api<NightlyPreferencesValue>('/nightly/preferences', { signal });
export const savePreferences = (body: NightlyPreferencesUpdate, key: string, signal?: AbortSignal) =>
  api<NightlyPreferencesValue>('/nightly/preferences', { method: 'PUT', body, headers: { 'Idempotency-Key': key }, signal });
export const cancelNightly = (id: string, key: string, signal?: AbortSignal) =>
  api<{ id: string; state: string }>('/nightly/jobs/' + encodeURIComponent(id) + '/cancel', {
    method: 'POST', headers: { 'Idempotency-Key': key }, signal,
  });
