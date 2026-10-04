import { useCallback, useEffect, useRef, useState } from 'react';
import { isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';

/** Keep visible records and drafts mounted during refresh; invalidate older reads after a mutation. */
export function useMemoryResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const generation = useRef(0);
  const [data, setData] = useState<T>();
  const { resource, retry } = useResource(async signal => {
    const version = generation.current;
    return { version, value: await load(signal) };
  });
  useEffect(() => {
    if (resource.status === 'ready' && resource.data.version === generation.current) setData(resource.data.value);
  }, [resource]);
  const refresh = useCallback(() => { generation.current += 1; retry(); }, [retry]);
  const update = useCallback((change: (previous: T | undefined) => T | undefined) => {
    generation.current += 1;
    setData(change);
    retry();
  }, [retry]);
  return { data, refresh, update, loading: resource.status === 'loading', error: resource.status === 'error' ? resource.error : null };
}

/** The callback runs only for the current, mounted request, including transports that resolve after abort. */
export function useMemoryRequest() {
  const active = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => () => { active.current?.abort(); active.current = null; }, []);
  const cancel = useCallback(() => {
    active.current?.abort(); active.current = null; setBusy(false); setError(null);
  }, []);
  const clearError = useCallback(() => setError(null), []);
  const run = useCallback(async <T,>(request: (signal: AbortSignal) => Promise<T>, accept: (result: T) => void) => {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError(null);
    try {
      const result = await request(controller.signal);
      if (!controller.signal.aborted && active.current === controller) accept(result);
    } catch (failure) {
      if (!controller.signal.aborted && active.current === controller && !isCancelled(failure)) setError(failure);
    } finally {
      if (!controller.signal.aborted && active.current === controller) { active.current = null; setBusy(false); }
    }
  }, []);
  return { busy, error, run, cancel, clearError };
}
