// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, isCancelled, type ApiOptions } from '../../platform/api';
import { stream } from '../../platform/stream';
import type { CaseCapabilities, CaseEvent, CaseHandoff, CaseSession, CaseSummary, StartCase, TeachingSummary } from './types';

interface ActiveStream { controller: AbortController; caseId: string; runId?: string; epoch: number }
const casePath = (id: string) => '/cases/sessions/' + encodeURIComponent(id);
const cancelPath = (id: string) => '/cases/runs/' + encodeURIComponent(id) + '/cancel';

export function useCases(resumeCaseId?: string) {
  const [session, setSession] = useState<CaseSession | null>(null);
  const [capabilities, setCapabilities] = useState<CaseCapabilities>();
  const [saved, setSaved] = useState<CaseSummary[]>([]);
  const [teaching, setTeaching] = useState<TeachingSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>();
  const [catalogueError, setCatalogueError] = useState<unknown>();
  const [running, setRunning] = useState(false);
  const [partial, setPartial] = useState('');
  const [pendingQuestion, setPendingQuestion] = useState('');
  const [purgePending, setPurgePending] = useState<string>();
  const alive = useRef(false);
  const epoch = useRef(0);
  const current = useRef<CaseSession | null>(null);
  const active = useRef<ActiveStream | null>(null);
  const requests = useRef(new Set<AbortController>());

  const request = useCallback(async <T,>(path: string, options: ApiOptions = {}) => {
    const controller = new AbortController();
    requests.current.add(controller);
    try { return await api<T>(path, { ...options, signal: controller.signal }); }
    finally { requests.current.delete(controller); }
  }, []);

  const update = useCallback((next: CaseSession | null) => {
    current.current = next;
    setSession(next);
  }, []);

  const reload = useCallback(async () => {
    setLoading(true);
    setCatalogueError(undefined);
    const outcomes = await Promise.allSettled([
      request<CaseCapabilities>('/cases/capabilities'),
      request<{ cases: CaseSummary[] }>('/cases/saved'),
      request<{ cases: TeachingSummary[] }>('/cases/teaching'),
    ]);
    if (!alive.current) return;
    const [caps, snapshots, authored] = outcomes;
    if (caps.status === 'fulfilled') setCapabilities(caps.value);
    else if (!isCancelled(caps.reason)) setCatalogueError(caps.reason);
    if (snapshots.status === 'fulfilled') setSaved(snapshots.value.cases);
    else if (!isCancelled(snapshots.reason)) setCatalogueError(snapshots.reason);
    if (authored.status === 'fulfilled') setTeaching(authored.value.cases);
    else if (caps.status === 'fulfilled' && caps.value.teaching.content_installed && !isCancelled(authored.reason)) {
      setCatalogueError(authored.reason);
    }
    setLoading(false);
  }, [request]);

  useEffect(() => {
    alive.current = true;
    void reload();
    if (resumeCaseId) {
      const token = ++epoch.current;
      setBusy('open');
      void request<CaseSession>(casePath(resumeCaseId)).then(next => {
        if (alive.current && epoch.current === token) update(next);
      }).catch(failure => {
        if (alive.current && epoch.current === token && !isCancelled(failure)) setError(failure);
      }).finally(() => {
        if (alive.current && epoch.current === token) setBusy(null);
      });
    }
    return () => {
      alive.current = false;
      epoch.current++;
      for (const controller of requests.current) controller.abort();
      const run = active.current;
      run?.controller.abort();
      if (run?.runId) {
        // The backend run is cancelled even after response headers have arrived.
        void api(cancelPath(run.runId), { method: 'POST', timeoutMs: 5000 }).catch(() => {});
      }
    };
  }, [reload, request, resumeCaseId, update]);

  async function change(name: string, operation: () => Promise<CaseSession | null>) {
    const token = ++epoch.current;
    setBusy(name);
    setError(undefined);
    try {
      const result = await operation();
      if (!alive.current || token !== epoch.current) return;
      update(result);
      setPartial('');
      setPendingQuestion('');
      void reload();
      return result;
    } catch (failure) {
      if (alive.current && token === epoch.current && !isCancelled(failure)) setError(failure);
    } finally {
      if (alive.current && token === epoch.current) setBusy(null);
    }
  }

  function start(body: StartCase) {
    return change('start', () => request<CaseSession>('/cases/sessions', { method: 'POST', body }));
  }
  function open(id: string) { return change('open', () => request<CaseSession>(casePath(id))); }
  function refreshCurrency() {
    const item = current.current;
    if (!item?.teaching || active.current) return;
    return change('currency', () => request<CaseSession>(casePath(item.id)));
  }
  async function handoff(question: string) {
    const item = current.current;
    if (!item || active.current || !question.trim()) return;
    const token = ++epoch.current;
    setBusy('handoff');
    setError(undefined);
    try {
      const ticket = await request<CaseHandoff>(casePath(item.id) + '/handoff', { method: 'POST',
        body: { revision: item.revision, target: 'explain', question: question.trim() } });
      if (!alive.current || epoch.current !== token) {
        void api('/cases/handoffs/' + encodeURIComponent(ticket.id), { method: 'DELETE', timeoutMs: 5000 }).catch(() => {});
        return;
      }
      return ticket;
    } catch (failure) {
      if (alive.current && epoch.current === token && !isCancelled(failure)) setError(failure);
    } finally {
      if (alive.current && epoch.current === token) setBusy(null);
    }
  }
  function save() {
    const item = current.current;
    if (!item || active.current) return;
    return change('save', () => request<CaseSession>(casePath(item.id) + '/save',
      { method: 'POST', body: { revision: item.revision } }));
  }
  function reveal() {
    const item = current.current;
    if (!item || active.current) return;
    return change('reveal', () => request<CaseSession>(casePath(item.id) + '/reveal',
      { method: 'POST', body: { revision: item.revision } }));
  }
  function applyPreview(id: string, text: string) {
    const item = current.current;
    if (!item || active.current) return;
    return change('apply-preview', () => request<CaseSession>('/cases/attachments/' + encodeURIComponent(id) + '/apply',
      { method: 'POST', body: { revision: item.revision, text } }));
  }
  function close() {
    const item = current.current;
    if (!item || active.current) return;
    return change('close', async () => {
      await request(casePath(item.id) + '/close', { method: 'POST', body: { revision: item.revision } });
      return null;
    });
  }
  function remove() {
    const item = current.current;
    if (!item) return;
    active.current?.controller.abort();
    return change('delete', async () => {
      const result = await request<{ id: string; deleted: boolean; purge_pending: boolean }>(
        casePath(item.id), { method: 'DELETE' });
      if (alive.current) setPurgePending(result.purge_pending ? result.id : undefined);
      return null;
    });
  }
  async function retryPurge() {
    if (!purgePending) return;
    try {
      const result = await request<{ purge_pending: boolean }>(casePath(purgePending), { method: 'DELETE' });
      if (alive.current && !result.purge_pending) setPurgePending(undefined);
    } catch (failure) { if (alive.current && !isCancelled(failure)) setError(failure); }
  }

  async function stop() {
    const run = active.current;
    if (!run) return;
    try {
      if (run.runId) await api(cancelPath(run.runId), { method: 'POST' });
    } catch (failure) { if (alive.current && !isCancelled(failure)) setError(failure); }
    finally { run.controller.abort(); }
  }

  async function send(question: string, onAccepted?: () => void) {
    const item = current.current;
    if (!item || active.current || !question.trim()) return;
    const run: ActiveStream = { controller: new AbortController(), caseId: item.id, epoch: ++epoch.current };
    active.current = run;
    setRunning(true);
    setError(undefined);
    setPartial('');
    setPendingQuestion(question);
    let lastSequence = 0;
    let terminal = false;
    try {
      for await (const packet of stream<CaseEvent>(casePath(item.id) + '/discuss', { method: 'POST',
        signal: run.controller.signal, body: { message: question, revision: item.revision,
          request_id: crypto.randomUUID() } })) {
        if (!alive.current || epoch.current !== run.epoch || run.controller.signal.aborted) break;
        const event = packet.data;
        if (event.sequence <= lastSequence) continue;
        if (terminal || (run.runId && event.run_id !== run.runId)) {
          throw new ApiError('The case response changed unexpectedly. Reload the case.', 0, 'invalid_case_stream');
        }
        lastSequence = event.sequence;
        run.runId = event.run_id;
        if (event.type === 'started' && event.payload.revision && event.payload.scope) {
          update({ ...item, revision: event.payload.revision, active_run_id: run.runId,
            scope: event.payload.scope, dirty: true });
          onAccepted?.();
        } else if (event.type === 'answer.delta' && typeof event.payload.text === 'string') {
          setPartial(previous => previous + event.payload.text);
        } else if (event.type === 'completed' || event.type === 'cancelled') {
          terminal = true;
        } else if (event.type === 'failed') {
          terminal = true;
          const failure = event.payload.error;
          setError(new ApiError(failure?.message ?? 'The case response could not finish. Try again.',
            0, failure?.code ?? 'case_discussion_failed', failure?.retryable ?? true));
        }
      }
      if (!terminal && !run.controller.signal.aborted && alive.current && epoch.current === run.epoch) {
        throw new ApiError('The connection ended before the response finished. Your case is still temporary.',
          0, 'case_stream_interrupted', true);
      }
    } catch (failure) {
      if (alive.current && epoch.current === run.epoch && !isCancelled(failure)) setError(failure);
    } finally {
      if (!terminal && run.runId) {
        await api(cancelPath(run.runId), { method: 'POST', timeoutMs: 5000 }).catch(() => {});
      }
      if (alive.current && epoch.current === run.epoch && current.current?.id === item.id) {
        try {
          const latest = await request<CaseSession>(casePath(item.id));
          if (alive.current && epoch.current === run.epoch) update(latest);
        } catch (failure) { if (alive.current && epoch.current === run.epoch && !isCancelled(failure)) setError(failure); }
      }
      if (active.current === run) active.current = null;
      if (alive.current) {
        setRunning(false);
        setPartial('');
        setPendingQuestion('');
      }
    }
  }

  return { session, capabilities, saved, teaching, loading, busy, error, catalogueError,
    running, partial, pendingQuestion, purgePending, reload, start, open, save, reveal,
    close, remove, retryPurge, stop, send, handoff, applyPreview, refreshCurrency };
}
