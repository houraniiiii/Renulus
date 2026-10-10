import { useEffect, useRef, useState } from 'react';
import { api, isCancelled } from '../../platform/api';

interface Pending {
  path: string; method: string; body: object; controller: AbortController | null;
  completed: (value: unknown) => void;
}

/** Keep the exact command through a lost acknowledgement; explicit retry reuses it. */
export function useTestMutation() {
  const mounted = useRef(false), pending = useRef<Pending | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; pending.current?.controller?.abort(); };
  }, []);
  async function execute(command: Pending) {
    if (!mounted.current || command.controller) return;
    const controller = new AbortController(); command.controller = controller;
    setBusy(true); setError(null);
    try {
      const result = await api(command.path, { method: command.method, body: command.body, signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      pending.current = null; command.completed(result);
    } catch (caught) {
      if (mounted.current && !controller.signal.aborted && !isCancelled(caught)) setError(caught);
    } finally {
      command.controller = null;
      if (mounted.current && !controller.signal.aborted) setBusy(false);
    }
  }
  function mutate<T>(path: string, method: string, body: object, completed: (value: T) => void) {
    if (pending.current) return;
    const command: Pending = { path, method, body: { ...body, idempotency_key: crypto.randomUUID() },
      controller: null, completed: value => completed(value as T) };
    pending.current = command; void execute(command);
  }
  return { busy, error, locked: busy || error !== null, mutate,
    retry: () => { if (pending.current) void execute(pending.current); } };
}
