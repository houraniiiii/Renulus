import { useEffect, useRef, useState } from 'react';
import { api, ApiError, isCancelled } from '../../platform/api';

interface Pending { path: string; body: object; controller: AbortController | null; received: (value: unknown) => void }

/** An uncertain acknowledgement retains the exact body/key; retry is explicit. */
export function useImportCommand() {
  const mounted = useRef(false), pending = useRef<Pending | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; pending.current?.controller?.abort(); }; }, []);
  async function execute(command: Pending) {
    if (!mounted.current || command.controller) return;
    const controller = new AbortController(); command.controller = controller;
    setBusy(true); setError(null);
    try {
      const value = await api(command.path, { method: 'POST', body: command.body, signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      pending.current = null; command.received(value);
    } catch (caught) {
      if (mounted.current && !controller.signal.aborted && !isCancelled(caught)) setError(caught);
    } finally {
      command.controller = null;
      if (mounted.current && !controller.signal.aborted) setBusy(false);
    }
  }
  function mutate<T>(path: string, body: object, received: (value: T) => void) {
    if (pending.current) return;
    const command: Pending = { path, body: { ...body, idempotency_key: crypto.randomUUID() }, controller: null,
      received: value => received(value as T) };
    pending.current = command; void execute(command);
  }
  const canReload = error instanceof ApiError && error.status >= 400 && error.status < 500;
  return { busy, error, locked: busy || error !== null, mutate, canReload,
    clear: () => { pending.current?.controller?.abort(); pending.current = null; setBusy(false); setError(null); },
    retry: () => { if (pending.current) void execute(pending.current); },
    reload: () => { if (canReload) { pending.current = null; setError(null); } } };
}
