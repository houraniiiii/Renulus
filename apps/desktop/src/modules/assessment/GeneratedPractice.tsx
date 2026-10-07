import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Check, Pause, Play, RotateCcw, Square } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { stream } from '../../platform/stream';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, Textarea } from '../../ui';
import type { GeneratePracticeRequest, PracticeAnswerResult, PracticeCapabilities, PracticeCitation,
  PracticeContext, PracticeFeedback, PracticeHelpResult, PracticeRetrieval, PracticeReview, PracticeRunEvent,
  PracticeScores, PracticeSession } from './generated-types';

const base = '/assessment/practice';
const sessionPath = (id: string, action = '') => base + '/sessions/' + encodeURIComponent(id) + action;
const runPath = (id: string) => base + '/runs/' + encodeURIComponent(id) + '/cancel';

interface GenerationAttempt {
  body: GeneratePracticeRequest;
  controller: AbortController | null;
  runId: string | null;
  terminal: boolean;
  cancelRequest?: Promise<{ run_id: string; cancelled: true }>;
}
interface GenerationState {
  status: 'idle' | 'running' | 'interrupted' | 'failed' | 'cancelling' | 'cancelled';
  received: number;
  retrieval?: PracticeRetrieval;
  error?: ApiError;
}
interface PendingCommand {
  controller: AbortController | null;
  execute: (signal: AbortSignal) => Promise<void>;
}

function errorMessage(error: unknown): ApiError {
  return error instanceof ApiError ? error
    : new ApiError('The connection stopped before the runtime confirmed this request. Retry the same request.',
      0, 'interrupted', true);
}

function cancelRun(attempt: GenerationAttempt) {
  if (!attempt.runId) return undefined;
  if (!attempt.cancelRequest) {
    attempt.cancelRequest = api<{ run_id: string; cancelled: true }>(runPath(attempt.runId), { method: 'POST' })
      .then(result => {
        if (result.cancelled !== true || result.run_id !== attempt.runId) {
          throw new ApiError('Cancellation was not confirmed.', 0, 'invalid_response', true);
        }
        return result;
      })
      .catch(error => { attempt.cancelRequest = undefined; throw error; });
  }
  return attempt.cancelRequest;
}

function handoffScope(value: unknown): string | undefined {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object' && 'kind' in value && typeof value.kind === 'string') return value.kind;
  return undefined;
}

function locatorLabel(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return null;
  const locator = value as Record<string, unknown>;
  if (typeof locator.locator === 'string') return locator.locator;
  const parts: string[] = [];
  const page = locator.page_label ?? locator.page_number ?? locator.page;
  if (typeof page === 'string' || typeof page === 'number') parts.push('Page ' + page);
  if (typeof locator.section === 'string') parts.push(locator.section);
  if (typeof locator.passage_id === 'string') parts.push('Passage ' + locator.passage_id);
  return parts.length ? parts.join(' · ') : null;
}

function SourceList({ sources }: { sources: PracticeCitation[] }) {
  if (!sources.length) return <p className="muted">No source locators were supplied. Source verification is unavailable for this feedback.</p>;
  return <ul className="assessment-sources">{sources.map((source, index) => <li key={source.source_id + ':' + index}>
    {source.url?.startsWith('https://')
      ? <a href={source.url} target="_blank" rel="noreferrer">{source.title ?? source.source_id}</a>
      : <strong>{source.title ?? source.source_id}</strong>}
    <span>{source.locator}</span>
    {source.locators?.map(locatorLabel).filter((label): label is string => !!label)
      .filter(label => label !== source.locator).map((label, position) => <span key={position}>{label}</span>)}
    {source.edition && <span className="muted">Edition: {source.edition}</span>}
    {source.checked_on && <span className="muted">Locator check recorded: {source.checked_on}</span>}
  </li>)}</ul>;
}

function ScoreTable({ scores }: { scores: PracticeScores }) {
  return <div className="section"><table className="assessment-scores"><caption>Generated key comparisons</caption>
    <thead><tr><th scope="col">Attempt type</th><th scope="col">Matches / answered</th></tr></thead>
    <tbody>{(['unassisted', 'assisted'] as const).map(bucket => <tr key={bucket}>
      <th scope="row">{bucket === 'unassisted' ? 'Unassisted' : 'Assisted'}</th>
      <td>{scores[bucket].correct} / {scores[bucket].answered}</td>
    </tr>)}</tbody></table>
    <p className="muted">These comparisons use an unreviewed generated key. They do not contribute to reviewed scores or establish mastery.</p>
  </div>;
}

function FeedbackView({ feedback, focus = false }: { feedback: PracticeFeedback; focus?: boolean }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (focus) heading.current?.focus(); }, [feedback.attempt_id, focus]);
  return <article className="assessment-feedback">
    <div className="assessment-meta"><Badge tone="warning">Generated · unreviewed</Badge>
      <span>{feedback.correct ? 'Matches generated key' : 'Differs from generated key'}</span>
      <span>{feedback.assisted ? 'Assisted' : 'Unassisted'}</span></div>
    <h3 ref={heading} tabIndex={focus ? -1 : undefined}>{feedback.item.stem}</h3>
    <dl className="assessment-result-options"><div><dt>Your answer</dt><dd>
      {feedback.options.filter(option => feedback.selected_option_ids.includes(option.id)).map(option => option.text).join(', ')}
    </dd></div><div><dt>Generated key</dt><dd>
      {feedback.options.filter(option => feedback.correct_option_ids.includes(option.id)).map(option => option.text).join(', ')}
    </dd></div></dl>
    <div className="prose section"><h3>Generated explanation</h3><p>{feedback.explanation}</p></div>
    <details className="assessment-rationales"><summary>Reasoning for each option</summary>
      <dl>{feedback.options.map(option => <div key={option.id}><dt>{option.text}</dt>
        <dd>{option.rationale ?? 'No additional rationale supplied.'}</dd></div>)}</dl>
    </details>
    <section className="section"><h3>Sources for this feedback</h3><SourceList sources={feedback.sources} />
      <p className="muted">Source retrieval does not independently verify the generated question, key or explanation.</p></section>
  </article>;
}

export function GeneratedPractice({ onBack }: { onBack?: () => void }) {
  const nav = useNavigation();
  const ticket = typeof nav.handoff?.case_handoff_id === 'string' ? nav.handoff.case_handoff_id : undefined;
  const topic = typeof nav.handoff?.topic_id === 'string' ? nav.handoff.topic_id : undefined;
  const scopeKind = nav.scope.kind === 'study' ? handoffScope(nav.handoff?.scope) ?? 'study' : nav.scope.kind;
  const context: PracticeContext = scopeKind === 'unclassified' ? 'unclassified'
    : scopeKind === 'study' && !ticket ? 'study' : 'temporary';
  const volatile = context !== 'study' || !!ticket;
  // A case question can contain case text. The ticket is its only transport;
  // the renderer supplies a separate, editable practice instruction.
  const initialPrompt = ticket ? 'Practise the reasoning from this temporary case.'
    : typeof nav.handoff?.question === 'string' ? nav.handoff.question : '';
  const [prompt, setPrompt] = useState(initialPrompt);
  const [count, setCount] = useState('3');
  const [generation, setGeneration] = useState<GenerationState>({ status: 'idle', received: 0 });
  const [cancelError, setCancelError] = useState<ApiError>();
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [choice, setChoice] = useState('');
  const [feedback, setFeedback] = useState<PracticeFeedback | null>(null);
  const [help, setHelp] = useState<PracticeHelpResult | null>(null);
  const [review, setReview] = useState<PracticeReview | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<ApiError>();
  const mounted = useRef(true);
  const revision = useRef(nav.revision);
  const attempt = useRef<GenerationAttempt | null>(null);
  const pending = useRef<PendingCommand | null>(null);
  const questionHeading = useRef<HTMLLegendElement>(null);
  const practiceHeading = useRef<HTMLHeadingElement>(null);
  const sessionState = useRef<string | undefined>(undefined);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const capabilities = useResource(signal => api<PracticeCapabilities>(base + '/capabilities', { signal }));
  const history = useResource(async signal => volatile ? [] :
    (await api<{ sessions: PracticeSession[] }>(base + '/sessions', { signal })).sessions
      .filter(value => value.mode === 'generated' && value.retention === 'persistent'));

  useEffect(() => {
    mounted.current = true;
    if (revision.current !== nav.revision) {
      revision.current = nav.revision;
      setPrompt(initialPrompt); setCount('3'); setSession(null); setChoice('');
      setFeedback(null); setHelp(null); setReview(null); setBusy(false);
      setActionError(undefined); setCancelError(undefined);
      setGeneration({ status: 'idle', received: 0 });
      capabilities.retry(); history.retry();
    }
    return () => {
      mounted.current = false;
      const current = attempt.current;
      attempt.current = null;
      current?.controller?.abort();
      if (current && !current.terminal && current.runId) void cancelRun(current)?.catch(() => {});
      pending.current?.controller?.abort();
      pending.current = null;
    };
  }, [nav.revision]);
  useEffect(() => {
    if (!feedback && session?.status === 'active') questionHeading.current?.focus();
  }, [session?.current_item?.id, session?.status, feedback]);
  useEffect(() => {
    const state = session?.status;
    if (!feedback && sessionState.current !== state && (state === 'paused' || state === 'ended' || !state)) practiceHeading.current?.focus();
    sessionState.current = state;
  }, [session?.status, feedback]);
  useEffect(() => { if (review) reviewHeading.current?.focus(); }, [review]);

  function checkedSession(value: PracticeSession): PracticeSession {
    if (value.mode !== 'generated' || (volatile && value.retention !== 'volatile')) {
      throw new ApiError('The runtime returned a session outside this practice context.', 0, 'invalid_session');
    }
    return value;
  }
  function adopt(value: PracticeSession) {
    setSession(checkedSession(value)); setChoice(''); setFeedback(null); setHelp(null); setReview(null);
  }

  async function generate(current: GenerationAttempt) {
    if (current.controller || current.terminal || !mounted.current) return;
    attempt.current = current;
    const controller = new AbortController();
    current.controller = controller;
    setGeneration({ status: 'running', received: 0 }); setCancelError(undefined);
    let sequence = -1;
    let started = false;
    try {
      for await (const message of stream<PracticeRunEvent>(base + '/generate', {
        method: 'POST', body: current.body, signal: controller.signal,
      })) {
        if (!mounted.current || attempt.current !== current || current.terminal) return;
        const event = message.data;
        if (!event || !Number.isInteger(event.sequence) || event.sequence <= sequence
          || typeof event.run_id !== 'string' || !event.run_id || !event.payload
          || (started && current.runId && event.run_id !== current.runId)) {
          throw new ApiError('The runtime sent an unexpected practice event. Reconnect to the same request.', 0, 'invalid_event', true);
        }
        sequence = event.sequence;
        if (!started && event.type !== 'started') {
          throw new ApiError('The runtime did not acknowledge the practice run. Reconnect to the same request.', 0, 'invalid_event', true);
        }
        switch (event.type) {
          case 'started':
            current.runId = event.run_id;
            if (started || event.payload.mode !== 'generated' || (volatile && event.payload.persistent)) {
              throw new ApiError('The runtime could not confirm the requested practice context.', 0, 'invalid_event');
            }
            started = true;
            break;
          case 'retrieval':
            setGeneration(previous => ({ ...previous, retrieval: event.payload }));
            break;
          case 'progress':
            if (!Number.isInteger(event.payload.received_characters) || event.payload.received_characters < 0) {
              throw new ApiError('The runtime sent invalid generation progress.', 0, 'invalid_event');
            }
            setGeneration(previous => ({ ...previous, received: event.payload.received_characters }));
            break;
          case 'completed':
            adopt(event.payload.session);
            current.terminal = true;
            setGeneration({ status: 'idle', received: 0 });
            history.retry();
            return;
          case 'error':
            current.terminal = true;
            setGeneration({ status: 'failed', received: 0, error: new ApiError(
              event.payload.message, 0, event.payload.code, event.payload.retryable) });
            return;
          case 'cancelled':
            current.terminal = true;
            setGeneration({ status: 'cancelled', received: 0 });
            return;
          default:
            throw new ApiError('The runtime sent an unsupported practice event.', 0, 'invalid_event');
        }
      }
      if (!current.terminal) throw new ApiError('The generation stream ended before a result was confirmed.', 0, 'interrupted', true);
    } catch (error) {
      if (!mounted.current || attempt.current !== current || current.terminal || isCancelled(error)) return;
      const failure = errorMessage(error);
      // A terminal SSE failure permits an explicit new generation. A lost
      // acknowledgement keeps the exact body/key for idempotent replay.
      const rejected = failure.status >= 400 && failure.status < 500 && !failure.retryable
        && failure.code !== 'invalid_stream' && failure.code !== 'invalid_response';
      current.terminal = rejected;
      setGeneration({ status: rejected ? 'failed' : 'interrupted', received: 0, error: failure });
    } finally {
      if (current.controller === controller) current.controller = null;
    }
  }

  function launch(body?: GeneratePracticeRequest) {
    if (pending.current || (attempt.current && !attempt.current.terminal)) return;
    const available = capabilities.resource.status === 'ready' && capabilities.resource.data.available;
    const amount = Number(count);
    if (!available || !prompt.trim() || prompt.length > 12000 || !Number.isInteger(amount) || amount < 1 || amount > 5) return;
    const request: GeneratePracticeRequest = body ? { ...body, idempotency_key: crypto.randomUUID() }
      : { idempotency_key: crypto.randomUUID(), prompt: prompt.trim(), count: amount, context,
        ...(topic ? { topic_id: topic } : {}), ...(ticket ? { case_handoff_id: ticket } : {}) };
    void generate({ body: request, controller: null, runId: null, terminal: false });
  }

  async function cancelGeneration() {
    const current = attempt.current;
    if (!current?.runId || current.terminal || generation.status === 'cancelling') return;
    const previousStatus = current.controller ? 'running' : 'interrupted';
    setGeneration(previous => ({ ...previous, status: 'cancelling' })); setCancelError(undefined);
    try {
      const result = await cancelRun(current);
      if (!mounted.current || attempt.current !== current || current.terminal) return;
      if (!result?.cancelled || result.run_id !== current.runId) throw new ApiError('Cancellation was not confirmed.', 0, 'invalid_response', true);
      current.terminal = true; current.controller?.abort();
      setGeneration({ status: 'cancelled', received: 0 });
    } catch (error) {
      if (mounted.current && attempt.current === current && !current.terminal) {
        setCancelError(errorMessage(error));
        setGeneration(previous => ({ ...previous, status: previousStatus }));
      }
    }
  }

  async function execute(command: PendingCommand) {
    if (command.controller || !mounted.current) return;
    const controller = new AbortController();
    command.controller = controller;
    setBusy(true); setActionError(undefined);
    try {
      await command.execute(controller.signal);
      if (mounted.current && pending.current === command) { pending.current = null; history.retry(); }
    } catch (error) {
      if (mounted.current && pending.current === command && !isCancelled(error)) setActionError(errorMessage(error));
    } finally {
      command.controller = null;
      if (mounted.current && (pending.current === command || !pending.current)) setBusy(false);
    }
  }
  function perform<T>(work: (signal: AbortSignal) => Promise<T>, apply: (value: T) => void) {
    if (pending.current || busy) return;
    const command: PendingCommand = { controller: null, execute: async signal => {
      const value = await work(signal);
      if (mounted.current && pending.current === command && !signal.aborted) apply(value);
    } };
    pending.current = command;
    void execute(command);
  }
  function transition(action: 'pause' | 'resume' | 'end') {
    if (!session) return;
    const url = sessionPath(session.id, '/' + action);
    const body = { idempotency_key: crypto.randomUUID() };
    perform(signal => api<PracticeSession>(url, { method: 'POST', body, signal }), adopt);
  }
  function answer() {
    if (!session?.current_item || !choice || session.status !== 'active') return;
    const url = sessionPath(session.id, '/answer');
    const body = { idempotency_key: crypto.randomUUID(), item_id: session.current_item.id, option_ids: [choice] };
    perform(signal => api<PracticeAnswerResult>(url, { method: 'POST', body, signal }), result => {
      setSession(checkedSession(result.session)); setFeedback(result.feedback); setChoice(''); setHelp(null); setReview(null);
    });
  }
  function requestHelp(kind: 'hint' | 'sources') {
    if (!session?.current_item || session.status !== 'active') return;
    const url = sessionPath(session.id, '/help');
    const body = { idempotency_key: crypto.randomUUID(), item_id: session.current_item.id, kind };
    perform(signal => api<PracticeHelpResult>(url, { method: 'POST', body, signal }), result => {
      setHelp(result);
      setSession(current => current?.current_item?.id === result.item_id ? { ...current,
        current_item: { ...current.current_item, assisted: true } } : current);
    });
  }
  async function reconcile() {
    if (busy) return;
    const command = pending.current;
    const controller = new AbortController();
    if (command) command.controller = controller;
    setBusy(true);
    try {
      if (session) {
        const restored = await api<PracticeSession>(sessionPath(session.id), { signal: controller.signal });
        if (mounted.current && pending.current === command && !controller.signal.aborted) adopt(restored);
      }
      if (mounted.current && pending.current === command && !controller.signal.aborted) {
        pending.current = null; setActionError(undefined); history.retry();
      }
    } catch (error) {
      if (mounted.current && pending.current === command && !isCancelled(error)) setActionError(errorMessage(error));
    } finally {
      if (command) command.controller = null;
      if (mounted.current && !controller.signal.aborted) setBusy(false);
    }
  }

  const generating = generation.status === 'running' || generation.status === 'cancelling';
  const generationLocked = generating || generation.status === 'interrupted' || generation.status === 'failed';
  const locked = busy || !!actionError || generationLocked;
  const availability = capabilities.resource.status === 'ready' ? capabilities.resource.data : null;
  const amount = Number(count);
  const valid = !!prompt.trim() && prompt.length <= 12000 && Number.isInteger(amount) && amount >= 1 && amount <= 5;

  return <section className="generated-practice section" aria-label="Generated practice">
    <div className="section">{onBack && <div className="actions"><Button variant="ghost" onClick={onBack}><ArrowLeft size={17} />Back to Test</Button></div>}
      <h2 ref={practiceHeading} tabIndex={-1}>Generated practice</h2>
      <p>Practise with unreviewed generated questions. Answers are compared with a generated key, separately from reviewed assessment.</p>
      {volatile && <Notice tone="warning"><p>{ticket ? 'Practice from this case is temporary.'
        : context === 'unclassified' ? 'This context is unclassified and stays temporary.' : 'This practice stays temporary.'}
        {' '}Questions and answers are not saved to study history.</p></Notice>}
    </div>
    {actionError && <div className="section"><ErrorState error={actionError} title="Your practice action needs attention" />
      <div className="actions">{(actionError.retryable || actionError.status === 0) && pending.current &&
        <Button variant="secondary" busy={busy} onClick={() => { if (pending.current) void execute(pending.current); }}>Retry same request</Button>}
        <Button variant="ghost" disabled={busy} onClick={() => void reconcile()}>{session ? 'Reload session' : 'Return to request'}</Button>
      </div></div>}
    {!session ? <div className="section">
      {capabilities.resource.status === 'loading' && <LoadingState label="Checking practice generation availability" />}
      {capabilities.resource.status === 'error' && <ErrorState error={capabilities.resource.error}
        title="Practice availability could not be checked" onRetry={capabilities.retry} />}
      {availability && !availability.available && <div className="section"><Notice tone="warning"><p>
        {availability.reason ?? 'Practice generation is unavailable in the local runtime.'}</p></Notice>
        <div className="actions"><Button variant="secondary" onClick={capabilities.retry}>Check availability again</Button>
          <Button variant="ghost" onClick={() => nav.navigate('connections')}>Open Connections</Button></div></div>}
      <form className="assessment-chooser generated-practice-request" onSubmit={event => { event.preventDefault(); launch(); }}>
        <Textarea label={ticket ? 'Practice instruction' : 'What would you like to practise?'} value={prompt} required maxLength={12000}
          disabled={locked} onChange={event => setPrompt(event.target.value)} rows={4}
          hint={ticket ? 'Focus this practice on a reasoning step from the current case. It remains temporary.' : 'Describe the topic or reasoning you want to work on.'} />
        <Input label="Questions" type="number" min={1} max={5} step={1} required value={count} disabled={locked}
          onChange={event => setCount(event.target.value)} hint="Choose 1 to 5 questions." />
        <Button type="submit" busy={generating} disabled={locked || !availability?.available || !valid}>
          Generate practice<ArrowRight size={17} /></Button>
      </form>
      {generating && <div className="section"><Notice><p>{generation.status === 'cancelling' ? 'Requesting cancellation…' : 'Generating your practice…'}
        </p>
        {generation.retrieval && <p>{generation.retrieval.verification === 'retrieved'
          ? generation.retrieval.passage_count + ' source passages retrieved. Sources open after an answer or assisted help.'
          : generation.retrieval.verification === 'retrieval-failed' ? 'Source retrieval failed; sources are not verified.'
          : generation.retrieval.verification === 'not-requested' ? 'Source retrieval was not requested for this context.'
          : 'No verified source passages were retrieved.'}</p>}</Notice>
        <div className="actions"><Button variant="secondary" disabled={!attempt.current?.runId || generation.status === 'cancelling'}
          onClick={() => void cancelGeneration()}><Square size={16} />Cancel generation</Button></div></div>}
      {generation.error && <div className="section"><ErrorState error={generation.error}
        title={generation.status === 'failed' ? 'Practice generation failed' : 'Generation could not be confirmed'} />
        {ticket && <div className="actions"><Button variant="secondary" onClick={() => nav.navigate('cases', {
          payload: { case_id: nav.handoff?.case_id ?? nav.scope.entity_id },
        })}>Return to Cases</Button></div>}
        {generation.status === 'interrupted' && <><p>The runtime may already have completed this request. Reconnect using the same request and key to recover its result.</p>
          <div className="actions"><Button disabled={generating} onClick={() => { if (attempt.current) void generate(attempt.current); }}>Reconnect same request</Button>
            {attempt.current?.runId && <Button variant="secondary" disabled={generating} onClick={() => void cancelGeneration()}>Cancel generation</Button>}</div></>}
        {generation.status === 'failed' && <div className="actions">{generation.error.retryable && <Button
          disabled={!availability?.available} onClick={() => { if (attempt.current) launch(attempt.current.body); }}>Retry generation</Button>}
          <Button variant="secondary" onClick={() => { attempt.current = null; setGeneration({ status: 'idle', received: 0 }); }}>Edit request</Button></div>}
      </div>}
      {cancelError && <ErrorState error={cancelError} title="Cancellation could not be confirmed"
        onRetry={attempt.current?.runId && !attempt.current.terminal ? () => void cancelGeneration() : undefined} />}
      {generation.status === 'cancelled' && <Notice><p>Generation cancelled. You can edit the request and explicitly generate again.</p></Notice>}
      {!volatile && <section className="section assessment-separated"><h3>Pick up generated practice</h3>
        {history.resource.status === 'loading' && <LoadingState label="Loading saved generated practice" />}
        {history.resource.status === 'error' && <ErrorState error={history.resource.error} title="Practice history could not be loaded" onRetry={history.retry} />}
        {history.resource.status === 'ready' && (history.resource.data.length === 0 ? <p>No saved generated practice yet.</p>
          : <ul className="assessment-history">{history.resource.data.map(previous => <li key={previous.id}>
            <div><strong>Generated · unreviewed</strong><span>{previous.answered_count} / {previous.item_count} answered · {previous.status}</span>
              <span className="muted">{new Date(previous.created_at).toLocaleString()}</span></div>
            <Button variant="secondary" disabled={locked} onClick={() => perform(signal =>
              api<PracticeSession>(sessionPath(previous.id), { signal }), adopt)}>{previous.status === 'ended' ? 'Open review' : 'Open session'}<Play size={16} /></Button>
          </li>)}</ul>)}
      </section>}
    </div> : <div className="assessment-session-layout">
      <section className="section"><div className="assessment-meta"><Badge tone="warning">Generated · unreviewed</Badge>
        <span>{session.answered_count} / {session.item_count} answered</span>
        <Badge tone="neutral">{session.retention === 'volatile' ? 'Temporary' : 'Saved study practice'}</Badge>
        {session.current_item?.assisted && <Badge tone="warning">Assisted</Badge>}</div>
        <p className="muted">{session.source_verification === 'retrieved' ? 'Source passages retrieved; the generated key remains unreviewed.'
          : 'Source verification is unavailable for this session.'}</p>
        {session.status === 'paused' && <EmptyState title="Practice paused" action={<Button disabled={locked} busy={busy}
          onClick={() => transition('resume')}>Resume practice<Play size={16} /></Button>}>
          <p>{session.retention === 'volatile' ? 'This practice remains temporary.' : 'Your committed answers are retained.'}</p></EmptyState>}
        {session.status === 'ended' && <Notice><p>This practice ended with {session.answered_count} committed answers.</p></Notice>}
        {session.status === 'active' && session.current_item && !feedback && <form className="assessment-question"
          onSubmit={event => { event.preventDefault(); answer(); }}><fieldset disabled={locked}>
            <legend ref={questionHeading} tabIndex={-1}><span className="assessment-question-number">Question {session.current_item.ordinal} of {session.item_count}</span>
              <span className="assessment-stem">{session.current_item.stem}</span></legend>
            <div className="assessment-options">{session.current_item.options.map(option => <label key={option.id}>
              <input type="radio" name={'practice-' + session.current_item!.id} value={option.id} checked={choice === option.id}
                onChange={() => setChoice(option.id)} /><span>{option.text}</span></label>)}</div>
          </fieldset><div className="actions"><Button type="submit" busy={busy} disabled={locked || !choice}>Commit answer<Check size={17} /></Button>
            <Button variant="ghost" disabled={locked} onClick={() => requestHelp('hint')}>Show hint</Button>
            <Button variant="ghost" disabled={locked} onClick={() => requestHelp('sources')}>View sources</Button></div>
          <p className="muted">Opening a hint or sources marks this attempt assisted before help is shown. Committed answers cannot be changed.</p>
          {help && <div className="assessment-help"><h3>{help.kind === 'hint' ? 'Hint' : 'Source help'} · assisted</h3>
            {help.kind === 'hint' && <p>{help.hint ?? 'No hint was supplied for this question.'}</p>}
            <SourceList sources={help.sources} /></div>}
        </form>}
        {feedback && <><FeedbackView feedback={feedback} focus /><div className="actions">
          {session.status === 'active' && session.answered_count < session.item_count && <Button disabled={locked}
            onClick={() => perform(signal => api<PracticeSession>(sessionPath(session.id), { signal }), adopt)}>Next question<ArrowRight size={17} /></Button>}
          {session.status === 'active' && session.answered_count === session.item_count && <Button disabled={locked} onClick={() => transition('end')}>Finish practice</Button>}
        </div></>}
        {session.status === 'active' && !session.current_item && !feedback && <EmptyState title="All practice answers are committed"
          action={<Button disabled={locked} onClick={() => transition('end')}>Finish practice</Button>}>
          <p>Review the generated reasoning and its source locators below.</p></EmptyState>}
        <div className="actions assessment-separated"><Button variant="secondary" disabled={locked} onClick={() => perform(signal =>
          api<PracticeReview>(sessionPath(session.id, '/review'), { signal }), setReview)}>Review committed answers<RotateCcw size={16} /></Button>
          {session.status === 'active' && <Button variant="ghost" disabled={locked} onClick={() => transition('pause')}>Pause<Pause size={16} /></Button>}
          {session.status !== 'ended' && <Button variant="ghost" disabled={locked} onClick={() => transition('end')}>End practice</Button>}
          <Button variant="ghost" disabled={locked} onClick={() => { setSession(null); setFeedback(null); setHelp(null); setReview(null); }}>Back to practice request</Button>
        </div>
        {review && <section className="assessment-review section"><h3 ref={reviewHeading} tabIndex={-1}>Committed answer review</h3>
          {review.feedback.length ? review.feedback.map(entry => <FeedbackView key={entry.attempt_id} feedback={entry} />)
            : <p>No committed answers to review yet.</p>}</section>}
      </section><aside className="assessment-aside"><ScoreTable scores={review?.scores ?? session.scores} /></aside>
    </div>}
  </section>;
}

export default GeneratedPractice;
