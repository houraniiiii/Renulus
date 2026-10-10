/** Serial writes preserve the displayed draft and retry an ambiguous ACK exactly. */
import { api, ApiError } from '../../platform/api';
import { draftOf } from './types';
import type { Attempt, Draft, HelpReceipt } from './types';

export const attemptPath = (id: string, action = '') => '/assessment/test-attempts/' + encodeURIComponent(id) + action;
export interface Transport {
  read: (id: string) => Promise<Attempt>;
  write: <T>(path: string, method: string, body: unknown, key: string) => Promise<T>;
}
const localTransport: Transport = {
  read: id => api<Attempt>(attemptPath(id)),
  write: (path, method, body, key) => api(path, { method, body, headers: { 'Idempotency-Key': key } }),
};
interface Command { path: string; method: string; body: unknown; key: string; draft?: Draft }
export interface SessionState {
  attempt: Attempt | null; draft: Draft | null; saving: boolean; busy: boolean; dirty: boolean;
  error: unknown; help: HelpReceipt | null; warning: string | null; receivedAt: number;
}
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export class AttemptSession {
  private state: SessionState = { attempt: null, draft: null, saving: false, busy: false, dirty: false, error: null, help: null, warning: null, receivedAt: 0 };
  private listeners = new Set<() => void>();
  private pending: Command | null = null;
  private saves: Promise<void> | null = null;
  private epoch = 0;
  constructor(private transport: Transport = localTransport, private key: () => string = () => crypto.randomUUID()) {}
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  snapshot = () => this.state;
  private update(patch: Partial<SessionState>) { this.state = { ...this.state, ...patch }; this.listeners.forEach(listener => listener()); }
  private accept(attempt: Attempt, adopt: boolean) {
    const previous = this.state.attempt;
    if (previous?.id === attempt.id && (attempt.draft_revision < previous.draft_revision || attempt.policy.revision < previous.policy.revision
      || (previous.result !== null && attempt.result === null))) return;
    const terminal = attempt.status !== 'active';
    const changed = this.state.attempt?.position !== attempt.position || this.state.attempt?.draft_revision !== attempt.draft_revision || terminal;
    this.update({ attempt, receivedAt: performance.now(), ...(adopt || terminal ? { draft: draftOf(attempt), dirty: false } : {}),
      ...(changed ? { help: null } : {}), error: null });
    if (typeof window !== 'undefined' && (!previous || previous.policy.revision !== attempt.policy.revision))
      window.dispatchEvent(new CustomEvent('renulus:assessment-policy', { detail: attempt.policy }));
  }
  async open(id: string) {
    const epoch = ++this.epoch;
    try { const attempt = await this.transport.read(id); if (epoch === this.epoch) { this.pending = null; this.accept(attempt, true); } }
    catch (error) { if (epoch === this.epoch) this.update({ error }); }
  }
  seed(attempt: Attempt) { this.epoch++; this.pending = null; this.accept(attempt, true); }
  async refresh() {
    const id = this.state.attempt?.id;
    if (!id || this.state.busy || this.state.dirty || this.pending) return;
    const epoch = this.epoch;
    try { const attempt = await this.transport.read(id);
      if (epoch === this.epoch && !this.state.busy && !this.state.dirty && !this.pending) this.accept(attempt, true);
    } catch (error) { if (epoch === this.epoch) this.update({ error }); }
  }
  change(draft: Draft) {
    if (!this.state.attempt || this.state.attempt.status !== 'active' || this.state.busy || (this.pending && !this.pending.draft)) return;
    this.update({ draft, dirty: true, help: null });
    void this.flush().catch(() => { /* The page keeps the draft and recovery controls. */ });
  }
  flush(): Promise<void> {
    if (this.saves) return this.saves;
    this.saves = this.saveLoop().finally(() => { this.saves = null; });
    return this.saves;
  }
  private async saveLoop() {
    while (this.state.dirty && this.state.attempt?.status === 'active') {
      const attempt = this.state.attempt;
      if (this.pending && !this.pending.draft) throw new ApiError('Retry the pending action before changing answers.', 409, 'pending_action');
      const command = this.pending ?? { path: attemptPath(attempt.id, '/draft'), method: 'PUT', key: this.key(),
        draft: this.state.draft!, body: { ...this.state.draft, expected_revision: attempt.draft_revision } };
      this.epoch++; this.pending = command; this.update({ saving: true, error: null });
      try {
        await this.transport.write<Attempt>(command.path, command.method, command.body, command.key);
        const durable = await this.transport.read(attempt.id);
        const caughtUp = same(this.state.draft, command.draft);
        this.pending = null;
        if (durable.status !== 'active' && !same(this.state.draft, draftOf(durable)))
          this.update({ warning: 'The timer finished. Results use the answers accepted by Renulus before the deadline.' });
        this.accept(durable, caughtUp);
      } catch (error) {
        if (error instanceof ApiError && !error.retryable && error.status >= 400 && error.status < 500) this.pending = null;
        this.update({ error }); throw error;
      }
      finally { this.update({ saving: false }); }
    }
  }
  async action<T = Attempt>(action: string, body: (attempt: Attempt, draft: Draft) => unknown): Promise<T> {
    if (this.state.busy) throw new ApiError('Another attempt action is still saving.', 409, 'pending_action');
    this.epoch++;
    this.update({ busy: true, error: null, help: null });
    try {
      await this.flush();
      const attempt = this.state.attempt!;
      const command = this.pending ?? { path: attemptPath(attempt.id, '/' + action), method: 'POST', key: this.key(), body: body(attempt, this.state.draft!) };
      if (command.path !== attemptPath(attempt.id, '/' + action)) throw new ApiError('Retry the pending action first.', 409, 'pending_action');
      this.pending = command;
      const result = await this.transport.write<T>(command.path, command.method, command.body, command.key);
      const durable = await this.transport.read(attempt.id);
      this.pending = null; this.accept(durable, true);
      if (action === 'help') {
        const receipt = result as HelpReceipt;
        if (receipt.context.attempt_id === durable.id && receipt.context.item_id === durable.current_item?.item_id
          && receipt.context.draft_revision === durable.draft_revision && receipt.context.policy_revision === durable.policy.revision
          && durable.policy.assistance_allowed && durable.status === 'active') this.update({ help: receipt });
        else throw new ApiError('The question or learning policy changed. Reopen help for the current question.', 409, 'stale_help');
      }
      return result;
    } catch (error) {
      if (error instanceof ApiError && !error.retryable && error.status >= 400 && error.status < 500) this.pending = null;
      this.update({ error }); throw error;
    }
    finally { this.update({ busy: false }); }
  }
  async retry() {
    const pending = this.pending;
    if (!pending) { await this.refresh(); return; }
    if (pending.draft) { await this.flush(); return; }
    const action = pending.path.split('/').pop()!;
    await this.action(action, () => pending.body);
  }
  async move(position: number) {
    if (!this.state.draft || this.state.busy) return;
    this.change({ ...this.state.draft, position });
    await this.flush();
    if (this.state.attempt?.status === 'active') await this.action('present', attempt => ({ expected_revision: attempt.draft_revision, item_id: attempt.answers[attempt.position].item_id }));
  }
  dispose() { this.epoch++; this.listeners.clear(); }
}
