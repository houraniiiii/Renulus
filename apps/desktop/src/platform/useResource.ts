import { useCallback, useEffect, useRef, useState } from 'react';
import { isCancelled } from './api';

export type Resource<T> =
  | { status: 'loading' }
  | { status: 'ready'; data: T }
  | { status: 'error'; error: unknown };

/** Abort on unmount/retry; superseded results cannot replace the current request. */
export function useResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const loader = useRef(load);
  loader.current = load;
  const [version, setVersion] = useState(0);
  const [resource, setResource] = useState<Resource<T>>({ status: 'loading' });
  const retry = useCallback(() => setVersion(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setResource({ status: 'loading' });
    loader.current(controller.signal).then(
      data => { if (!controller.signal.aborted) setResource({ status: 'ready', data }); },
      error => { if (!controller.signal.aborted && !isCancelled(error)) setResource({ status: 'error', error }); },
    );
    return () => controller.abort();
  }, [version]);
  return { resource, retry };
}
