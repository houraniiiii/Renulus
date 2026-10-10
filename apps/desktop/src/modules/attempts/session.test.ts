import { describe, expect, it } from 'vitest';
import { ApiError } from '../../platform/api';
import { AttemptSession } from './session';
import { draftOf } from './types';
import type { Attempt, Draft, HelpReceipt } from './types';
import type { Transport } from './session';

const initial = (): Attempt => ({ id: 'test_attempt:synthetic', version_id: 'version:synthetic', origin: 'reviewed_bank', review_quality: 'reviewed',
  mode: 'test', status: 'active', item_count: 2, provenance_unavailable: false, draft_revision: 0, position: 0,
  answers: [{ item_id: 'item:first', option_ids: [], marked: false }, { item_id: 'item:second', option_ids: [], marked: false }],
  current_item: { item_id: 'item:first', question_id: 'q:first', question_version: '1', key_version: '1', family_id: 'f:first', family_version: '1', topic_id: 'synthetic', stem: 'Synthetic question', options: [{ id: 'a', text: 'A' }, { id: 'b', text: 'B' }] },
  committed: [], result: null, timing: { kind: 'untimed', duration_seconds: null, deadline_at: null, remaining_seconds: null, paused_seconds: 0 },
  policy: { active_test_id: 'test_attempt:synthetic', revision: 2, assistance_allowed: false } });
const selected = (attempt: Attempt, option: string): Draft => ({ ...draftOf(attempt), answers: attempt.answers.map((answer, index) => ({ ...answer, option_ids: index === 0 ? [option] : [] })) });
function deferred() { let release!: () => void; const promise = new Promise<void>(resolve => { release = resolve; }); return { promise, release }; }

function harness() {
  let durable = initial(); const calls: { path: string; body: Record<string, unknown>; key: string }[] = [];
  const receipts = new Map<string, unknown>(); let failure: 'save' | 'submit' | null = null; let barrier: Promise<void> | null = null;
  const transport: Transport = {
    read: async () => structuredClone(durable),
    write: async <T,>(path: string, _method: string, raw: unknown, key: string): Promise<T> => {
      const body = raw as Record<string, unknown>; calls.push({ path, body: structuredClone(body), key });
      if (receipts.has(key)) return structuredClone(receipts.get(key)) as T;
      if (path.endsWith('/draft')) {
        if (barrier) { const wait = barrier; barrier = null; await wait; }
        expect(body.expected_revision).toBe(durable.draft_revision);
        durable = { ...durable, position: body.position as number, answers: body.answers as Attempt['answers'], draft_revision: durable.draft_revision + 1 };
      }
      if (path.endsWith('/submit')) { durable = { ...durable, status: 'submitted', current_item: null, policy: { active_test_id: null, revision: 3, assistance_allowed: true } }; }
      const result = structuredClone(durable); receipts.set(key, result);
      if ((path.endsWith('/draft') && failure === 'save') || (path.endsWith('/submit') && failure === 'submit')) {
        failure = null; throw new ApiError('Synthetic lost acknowledgement', 0, 'unavailable', true);
      }
      return result as T;
    },
  };
  let ordinal = 0; const session = new AttemptSession(transport, () => 'command:' + ++ordinal); session.seed(durable);
  return { session, calls, transport, lose: (action: 'save' | 'submit') => { failure = action; }, block: (promise: Promise<void>) => { barrier = promise; }, read: () => durable };
}

describe('attempt draft ordering and recovery', () => {
  it('retries a lost save acknowledgement with the same payload/key before saving a newer choice', async () => {
    const h = harness(); h.lose('save'); h.session.change(selected(h.read(), 'a'));
    await expect(h.session.flush()).rejects.toThrow('lost acknowledgement');
    expect(h.session.snapshot().draft!.answers[0].option_ids).toEqual(['a']);
    h.session.change(selected(h.read(), 'b')); await h.session.flush();
    expect(h.calls).toHaveLength(3); expect(h.calls[1]).toEqual(h.calls[0]);
    expect(h.calls[2].key === h.calls[0].key).toBe(false);
    expect(h.read().answers[0].option_ids).toEqual(['b']); expect(h.session.snapshot().dirty).toBe(false);
  });
  it('final submission waits for every displayed choice and uses the last acknowledged revision', async () => {
    const h = harness(); const wait = deferred(); h.block(wait.promise); h.session.change(selected(h.read(), 'a'));
    h.session.change(selected(h.read(), 'b'));
    const final = h.session.action('submit', (attempt, draft) => ({ expected_draft_revision: attempt.draft_revision, latest_draft: draft }));
    expect(h.calls).toHaveLength(1); wait.release(); await final;
    expect(h.calls.map(call => call.path.split('/').pop())).toEqual(['draft', 'draft', 'submit']);
    expect(h.calls[2].body.expected_draft_revision).toBe(2);
    expect((h.calls[2].body.latest_draft as Draft).answers[0].option_ids).toEqual(['b']);
    expect(h.session.snapshot().attempt!.status).toBe('submitted');
  });
  it('refuses final submission when saving is ambiguous, keeping the displayed draft', async () => {
    const h = harness(); h.lose('save'); h.session.change(selected(h.read(), 'b'));
    await expect(h.session.action('submit', attempt => ({ expected_draft_revision: attempt.draft_revision }))).rejects.toThrow('lost acknowledgement');
    expect(h.calls.some(call => call.path.endsWith('/submit'))).toBe(false);
    expect(h.session.snapshot().draft!.answers[0].option_ids).toEqual(['b']);
    expect(h.session.snapshot().error).toBeInstanceOf(ApiError);
  });
  it('replays an ambiguous final submission exactly and reconciles the durable terminal state', async () => {
    const h = harness(); h.lose('submit');
    await expect(h.session.action('submit', attempt => ({ expected_draft_revision: attempt.draft_revision }))).rejects.toThrow('lost acknowledgement');
    await h.session.retry(); expect(h.calls[1]).toEqual(h.calls[0]);
    expect(h.session.snapshot().attempt!.status).toBe('submitted');
  });
  it('drops late help after a policy change before the consumer can use its receipt', async () => {
    const h = harness(); const study = { ...h.read(), mode: 'study' as const, policy: { active_test_id: null, revision: 2, assistance_allowed: true } }; h.session.seed(study);
    const receipt: HelpReceipt = { hint: 'Synthetic hint', assisted: true, references: [], context: { attempt_id: study.id, version_id: study.version_id,
      item_id: study.current_item!.item_id, draft_revision: 0, policy_revision: 2, kind: 'hint' } };
    h.transport.write = async <T,>() => receipt as T;
    h.transport.read = async () => ({ ...study, policy: { active_test_id: 'other:test', revision: 3, assistance_allowed: false } });
    await expect(h.session.action('help', () => ({}))).rejects.toThrow('policy changed');
    expect(h.session.snapshot().help).toBeNull();
  });
  it('does not let a delayed poll rewind a completed final submission', async () => {
    const h = harness(); const wait = deferred(); const old = structuredClone(h.read()); const read = h.transport.read;
    h.transport.read = async id => { await wait.promise; return old; };
    const poll = h.session.refresh(); h.transport.read = read;
    await h.session.action('submit', attempt => ({ expected_draft_revision: attempt.draft_revision }));
    wait.release(); await poll;
    expect(h.session.snapshot().attempt!.status).toBe('submitted');
    expect(h.session.snapshot().attempt!.policy.assistance_allowed).toBe(true);
  });
  it('allows another help kind after an unavailable authored hint is refused', async () => {
    const h = harness(); const study = { ...h.read(), mode: 'study' as const, policy: { active_test_id: null, revision: 2, assistance_allowed: true } }; h.session.seed(study);
    const kinds: string[] = []; h.transport.read = async () => study;
    h.transport.write = async <T,>(_path: string, _method: string, raw: unknown) => {
      const body = raw as { kind: HelpReceipt['context']['kind'] }; kinds.push(body.kind);
      if (body.kind === 'hint') throw new ApiError('No authored hint', 409, 'hint_unavailable');
      return { hint: null, references: [], assisted: true, context: { kind: body.kind, attempt_id: study.id, item_id: study.current_item!.item_id,
        version_id: study.version_id, draft_revision: 0, policy_revision: 2 } } as T;
    };
    await expect(h.session.action('help', () => ({ kind: 'hint' }))).rejects.toThrow('No authored hint');
    await h.session.action('help', () => ({ kind: 'sources' }));
    expect(kinds).toEqual(['hint', 'sources']); expect(h.session.snapshot().help!.context.kind).toBe('sources');
  });
});
