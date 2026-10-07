import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Check, Pause, Play, RotateCcw } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Select } from '../../ui';
import type { AnswerResult, AssessmentTrack, Catalog, Citation, Feedback, HelpResult, ReviewResult, Scores, Session } from './types';
import GeneratedPractice from './GeneratedPractice';
import SourceCurrencyNotice, { currencySummary, SessionCurrencyNotice } from './SourceCurrencyNotice';
import './assessment.css';

const base = '/assessment';
const path = (id: string, action = '') => base + '/sessions/' + encodeURIComponent(id) + action;
const labels = { fresh: 'Fresh, unassisted', assisted: 'Assisted', repeat: 'Repeat, unassisted' };

function SourceList({ sources }: { sources: Citation[] }) {
  return <ul className="assessment-sources">{sources.map((source, index) => <li key={source.source_id + ':' + index}>
    {source.url?.startsWith('https://')
      ? <a href={source.url} target="_blank" rel="noreferrer">{source.title ?? source.source_id}</a>
      : <strong>{source.title ?? source.source_id}</strong>}
    <span>{source.locator}</span>
    {source.edition && <span className="muted">{source.edition}</span>}
    {source.checked_on && <span className="muted">
      {source.check_status === 'check_failed' ? 'Locator check failed on ' : 'Locator checked '}{source.checked_on}</span>}
  </li>)}</ul>;
}

function ScoreTable({ scores }: { scores: Scores }) {
  return <table className="assessment-scores"><caption>Reviewed results</caption>
    <thead><tr><th scope="col">Attempt type</th><th scope="col">Correct / answered</th></tr></thead>
    <tbody>{(['fresh', 'assisted', 'repeat'] as const).map(bucket => <tr key={bucket}>
      <th scope="row">{labels[bucket]}</th><td>{scores.reviewed[bucket].correct} / {scores.reviewed[bucket].answered}</td>
    </tr>)}</tbody>
  </table>;
}

function TrackCoverage({ catalog, track }: { catalog: Catalog; track: AssessmentTrack | undefined }) {
  return <section className="assessment-track-coverage" aria-label="Selected track coverage">
    <Notice tone="warning">
      {track?.available
        ? <p>{catalog.available_questions} reviewed questions in {catalog.available_families} item families available.</p>
        : <p><strong>{track?.title ?? 'This track'} is unavailable.</strong>{' '}
          {track?.reason ?? 'No reviewed content is available for this track.'}</p>}
      <p>{catalog.coverage_note}</p>
      {track?.checked_on && <p>Mapping checked {track.checked_on}.</p>}
      {track?.format_compatible_questions !== undefined && <p>
        {track.format_compatible_questions} questions match the exam option format. Exam simulation is unavailable.</p>}
    </Notice>
    {!!track?.domains.length && <details className="assessment-domain-details">
      <summary>View indicative domain coverage</summary>
      <p className="muted">Family shortfalls compare distinct item families with indicative domain counts.
        These counts do not establish curriculum depth or mastery.</p>
      <div className="assessment-coverage-scroll" tabIndex={0} role="region" aria-label="Indicative domain coverage">
        <table className="assessment-scores assessment-domain-coverage">
          <caption>Mapped reviewed bank</caption>
          <thead><tr><th scope="col">Domain</th><th scope="col">Questions</th>
            <th scope="col">Item families</th><th scope="col">Family shortfall</th><th scope="col">Coverage</th></tr></thead>
          <tbody>{track.domains.map(domain => <tr key={domain.id}><th scope="row">{domain.label}</th>
            <td>{domain.available_questions}</td><td>{domain.available_families}</td><td>{domain.family_shortfall}</td>
            <td>{domain.status === 'gap' ? 'Gap' : 'Partial'}</td></tr>)}</tbody>
        </table>
      </div>
    </details>}
  </section>;
}

function FeedbackView({ feedback, focus = false }: { feedback: Feedback; focus?: boolean }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { if (focus) heading.current?.focus(); }, [feedback.attempt_id, focus]);
  return <article className="assessment-feedback">
    <div className="assessment-meta"><Badge tone={feedback.correct ? 'default' : 'warning'}>
      {feedback.correct ? 'Correct' : 'Review this answer'}</Badge><span>{labels[feedback.score_bucket]}</span>
      {feedback.repeat && feedback.assisted && <span>Previously exposed</span>}</div>
    <h2 ref={heading} tabIndex={focus ? -1 : undefined}>{feedback.item.stem}</h2>
    <dl className="assessment-result-options"><div><dt>Your answer</dt><dd>
      {feedback.options.filter(option => feedback.selected_option_ids.includes(option.id)).map(option => option.text).join(', ')}
    </dd></div><div><dt>Reviewed answer</dt><dd>
      {feedback.options.filter(option => feedback.correct_option_ids.includes(option.id)).map(option => option.text).join(', ')}
    </dd></div></dl>
    {feedback.content_status.status !== 'current' && <Notice tone="warning">
      <strong>Question version {feedback.item.question_version} is {feedback.content_status.status}.</strong>
      <p>{feedback.content_status.message}</p>
      {feedback.content_status.withdrawal && <p>{feedback.content_status.withdrawal.reason}</p>}
    </Notice>}
    <SourceCurrencyNotice currency={feedback.source_currency} item={feedback.item} committed />
    <div className="prose"><h3>Why this answer</h3><p>{feedback.explanation}</p></div>
    <details className="assessment-rationales"><summary>Reasoning for each option</summary>
      <dl>{feedback.options.map(option => <div key={option.id}><dt>{option.text}</dt>
        <dd>{option.rationale ?? 'No additional rationale supplied.'}</dd></div>)}</dl>
    </details>
    <section className="section"><h3>Sources for this feedback</h3><SourceList sources={feedback.sources} />
      <p className="muted">Question {feedback.item.question_version} · key {feedback.item.key_version} ·
        {feedback.review.status === 'human_reviewed' ? ' human reviewed' : ' assistant reviewed'}
        {!feedback.review.independent_human_review && ' · independent human review not recorded'}</p>
    </section>
  </article>;
}

export default function AssessmentPage() {
  const nav = useNavigation();
  const temporary = nav.scope.kind === 'temporary-case' || nav.scope.kind === 'unclassified';
  if (temporary) return <div className="assessment-page"><PageHeader title="Test" description="Practise in this temporary context." />
    <Notice tone="warning"><p>This case context is temporary. Start a separate study session to use the reviewed bank.</p></Notice>
    <div className="actions assessment-separated"><Button variant="secondary" onClick={() => nav.navigate('assessment', { freshStudy: true })}>
      Start separate study<ArrowRight size={17} /></Button></div>
    <GeneratedPractice key={nav.revision} /></div>;
  return <AssessmentStudyPage key={nav.revision} />;
}

function AssessmentStudyPage() {
  const nav = useNavigation();
  const [mode, setMode] = useState<'reviewed' | 'generated'>('reviewed');
  const handoffTrack = nav.handoff?.track;
  const [track, setTrack] = useState<string>(
    handoffTrack === 'general_nephrology' || handoffTrack === 'esen_eph' ? handoffTrack : 'general_nephrology');
  const [topic, setTopic] = useState(typeof nav.handoff?.topic_id === 'string' ? nav.handoff.topic_id : '');
  const [count, setCount] = useState('10');
  const [session, setSession] = useState<Session | null>(null);
  const [choice, setChoice] = useState('');
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [review, setReview] = useState<ReviewResult | null>(null);
  const [help, setHelp] = useState<HelpResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>();
  const mounted = useRef(true);
  const pending = useRef<(() => Promise<void>) | null>(null);
  const handoffConsumed = useRef(false);
  const questionHeading = useRef<HTMLLegendElement>(null);
  const questionForm = useRef<HTMLFormElement>(null);
  const visibleQuestionId = feedback ? null : session?.current_item?.id;
  const overview = useResource(async signal => {
    const [catalog, history, scores] = await Promise.all([
      api<Catalog>(base + '/catalog?track=' + encodeURIComponent(track), { signal }),
      api<{ sessions: Session[] }>(base + '/sessions', { signal }),
      api<Scores>(base + '/aggregates', { signal }),
    ]);
    return { catalog, track, history: history.sessions, scores };
  });
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (!visibleQuestionId) return;
    const notice = questionForm.current?.querySelector<HTMLElement>('.assessment-source-currency');
    if (notice) {
      notice.focus({ preventScroll: true });
      notice.scrollIntoView?.({ block: 'start' });
    } else questionHeading.current?.focus();
  }, [visibleQuestionId]);

  async function execute() {
    if (!pending.current || busy) return;
    setBusy(true); setActionError(undefined);
    try {
      await pending.current();
      if (mounted.current) { pending.current = null; overview.retry(); }
    } catch (error) {
      if (mounted.current && !isCancelled(error)) setActionError(error);
    } finally { if (mounted.current) setBusy(false); }
  }
  function perform<T>(work: () => Promise<T>, apply: (value: T) => void) {
    if (pending.current || busy) return;
    pending.current = async () => { const value = await work(); if (mounted.current) apply(value); };
    void execute();
  }
  function adopt(value: Session) {
    setSession(value); setChoice(''); setFeedback(null); setHelp(null); setReview(null);
  }
  function launch() {
    const amount = Number(count);
    if (!Number.isInteger(amount) || amount < 1 || amount > 50 || !selectedTrack?.available || !availableFamilies) return;
    const body = { idempotency_key: crypto.randomUUID(), mode: 'reviewed', count: amount,
      selector: { topic_ids: topic ? [topic] : [], track } };
    perform(() => api<Session>(base + '/start', { method: 'POST', body }), adopt);
  }
  function transition(action: 'pause' | 'resume' | 'end') {
    if (!session) return;
    const id = session.id;
    const body = { idempotency_key: crypto.randomUUID() };
    perform(() => api<Session>(path(id, '/' + action), { method: 'POST', body }), adopt);
  }
  function commit() {
    if (!session?.current_item || !choice) return;
    const id = session.id;
    const body = { idempotency_key: crypto.randomUUID(), item_id: session.current_item.id, option_ids: [choice] };
    perform(() => api<AnswerResult>(path(id, '/answer'), { method: 'POST', body }), result => {
      setSession(result.session); setFeedback(result.feedback); setHelp(null); setChoice('');
    });
  }
  function sourceHelp() {
    if (!session?.current_item) return;
    const id = session.id;
    const body = { idempotency_key: crypto.randomUUID(), item_id: session.current_item.id, kind: 'sources' };
    perform(() => api<HelpResult>(path(id, '/help'), { method: 'POST', body }), result => {
      setHelp(result);
      setSession(current => current?.current_item ? { ...current,
        current_item: { ...current.current_item, assisted: true } } : current);
    });
  }
  async function reloadAfterError() {
    if (busy) return;
    setBusy(true);
    try {
      // Inspect persisted state before abandoning an uncertain command. An
      // answer whose acknowledgement was lost remains committed on the server.
      if (session) {
        const restored = await api<Session>(path(session.id));
        if (mounted.current) adopt(restored);
      } else {
        await api<{ sessions: Session[] }>(base + '/sessions');
      }
      if (mounted.current) { pending.current = null; setActionError(undefined); overview.retry(); }
    } catch (error) { if (mounted.current) setActionError(error); }
    finally { if (mounted.current) setBusy(false); }
  }
  const locked = busy || !!actionError;
  const data = overview.resource.status === 'ready' && overview.resource.data.track === track ? overview.resource.data : null;
  const selectedTrack = data?.catalog.tracks.find(candidate => candidate.id === track);
  const availableFamilies = topic
    ? data?.catalog.domains.find(domain => domain.id === topic)?.available_families ?? 0
    : data?.catalog.available_families ?? 0;
  useEffect(() => {
    const questionId = nav.handoff?.question_id;
    if (!data || typeof questionId !== 'string' || handoffConsumed.current) return;
    handoffConsumed.current = true;
    perform(async () => {
      const rows = await api<{ mistakes: { question_id: string; session_id: string; item_id: string }[] }>(base + '/mistakes');
      const mistake = rows.mistakes.find(row => row.question_id === questionId);
      const retained = data.history.find(previous => previous.id === mistake?.session_id);
      if (!mistake || !retained) throw new ApiError('This retained mistake could not be opened. Choose its session from quiz history.',
        404, 'mistake_not_found');
      const detail = await api<ReviewResult>(path(retained.id, '/review?item_id=' + encodeURIComponent(mistake.item_id)));
      return { retained, detail };
    }, ({ retained, detail }) => {
      setSession({ ...retained, scores: detail.scores });
      setFeedback(detail.feedback[0] ?? null); setHelp(null); setChoice(''); setReview(null);
    });
  }, [data, nav.handoff]);

  return <div className="assessment-page">
    <PageHeader title="Test" description="Commit an answer, then work through its reasoning and sources."
      actions={session && <Button variant="ghost" disabled={locked} onClick={() => {
        setSession(null); setFeedback(null); setReview(null); setHelp(null);
        overview.retry();
      }}>Back to quizzes</Button>} />
    {actionError !== undefined && <div className="section"><ErrorState error={actionError} title="Your action needs attention"
      onRetry={actionError instanceof ApiError && actionError.retryable ? () => void execute() : undefined} />
      <div className="actions"><Button variant="secondary" busy={busy} onClick={() => void reloadAfterError()}>
        {session ? 'Reload retained session' : 'Return to quiz chooser'}</Button></div></div>}
    {!session ? <>
      <fieldset className="assessment-modes" disabled={locked}><legend className="sr-only">Question mode</legend>
        <label><input type="radio" name="assessment-mode" checked={mode === 'reviewed'} onChange={() => setMode('reviewed')} />
          <span><strong>Reviewed quiz</strong><span>Published questions, deterministic scoring</span></span></label>
        <label><input type="radio" name="assessment-mode" checked={mode === 'generated'} onChange={() => setMode('generated')} />
          <span><strong>Generated practice</strong><span>Separate from reviewed results</span></span></label>
      </fieldset>
      {(overview.resource.status === 'loading' || (overview.resource.status === 'ready' && !data))
        && <LoadingState label="Loading quiz coverage and your sessions" />}
      {overview.resource.status === 'error' && <ErrorState error={overview.resource.error} onRetry={overview.retry} />}
      {mode === 'generated' && <GeneratedPractice onBack={() => setMode('reviewed')} />}
      {data && mode === 'reviewed' && <div className="assessment-overview">
        <section className="section"><h2>Choose a focused quiz</h2>
          <form className="assessment-chooser" onSubmit={event => { event.preventDefault(); launch(); }}>
            <Select label="Track" value={track} disabled={locked} onChange={event => {
              setTrack(event.target.value); setTopic(''); overview.retry();
            }}>{data.catalog.tracks.length === 0 && <option value="">No tracks available</option>}
              {data.catalog.tracks.map(candidate => <option key={candidate.id} value={candidate.id}>
                {candidate.title}{!candidate.available && ' (unavailable)'}</option>)}
            </Select>
            <Select label="Topic" value={topic} disabled={locked} onChange={event => setTopic(event.target.value)}>
              <option value="">Across available topics</option>{data.catalog.domains.map(domain =>
                <option key={domain.id} value={domain.id} disabled={domain.available_families === 0}>
                  {domain.label} ({domain.available_families} item families)</option>)}
            </Select>
            <Input label="Questions" type="number" min={1} max={50} step={1} value={count} disabled={locked}
              onChange={event => setCount(event.target.value)} hint="If coverage is limited, the quiz uses the available item families." />
            <Button type="submit" busy={busy} disabled={locked || !selectedTrack?.available || availableFamilies === 0
              || !Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 50}>
              Start reviewed quiz<ArrowRight size={17} /></Button>
          </form>
          <TrackCoverage catalog={data.catalog} track={selectedTrack} />
          <section className="section assessment-separated"><h2>Pick up a session</h2>
            {data.history.length === 0 ? <p>No sessions yet. Your committed answers will appear here.</p>
              : <ul className="assessment-history">{data.history.map(previous => <li key={previous.id}>
                <div><strong>{previous.status === 'ended' ? 'Ended session' : 'Reviewed quiz'}</strong>
                  {previous.coverage.track_title && <span>{previous.coverage.track_title}</span>}
                  <span>{previous.answered_count} / {previous.item_count} answered · {previous.status}</span>
                  <span className="muted">{new Date(previous.created_at).toLocaleString()}</span>
                  {currencySummary(previous.source_currency) && <span className="assessment-currency-summary">
                    {currencySummary(previous.source_currency)}</span>}</div>
                <Button variant="secondary" disabled={locked} onClick={() => {
                  perform(() => api<Session>(path(previous.id)), adopt);
                }}>{previous.status === 'ended' ? 'Open review' : 'Open session'}<Play size={16} /></Button>
              </li>)}</ul>}
          </section>
        </section>
        <aside className="assessment-aside"><ScoreTable scores={data.scores} />
          <p className="muted">Results record observed answers. They do not establish curriculum mastery.</p>
        </aside>
      </div>}
    </> : <div className="assessment-session-layout">
      <section className="section">
        <div className="assessment-meta"><Badge>Reviewed quiz</Badge>
          {session.coverage.track_title && <span>{session.coverage.track_title}</span>}
          <span>{session.answered_count} / {session.item_count} committed</span>
          {session.current_item?.assisted && <Badge tone="warning">Assisted</Badge>}
          {session.current_item?.repeat && <Badge tone="neutral">Repeat exposure</Badge>}</div>
        {session.selector.track === 'esen_eph' && <Notice tone="warning"><p>{session.coverage.note}</p></Notice>}
        {session.coverage.insufficient_count && <Notice tone="warning"><p>
          Only {session.item_count} item families matched the requested {session.coverage.requested_count} questions.</p></Notice>}
        {session.status === 'paused' && <EmptyState title="Quiz paused" action={
          <Button busy={busy} disabled={locked} onClick={() => transition('resume')}>Resume quiz<Play size={16} /></Button>}>
          <p>{session.answered_count} committed answers are retained. Resume when you are ready.</p></EmptyState>}
        {session.status === 'ended' && <Notice><p>This session ended with {session.answered_count} committed answers.
          Review below includes those answers only.</p></Notice>}
        {!session.current_item && !feedback && <SessionCurrencyNotice currency={session.source_currency} />}
        {session.current_item && !feedback && <form ref={questionForm} className="assessment-question" onSubmit={event => { event.preventDefault(); commit(); }}>
          <SourceCurrencyNotice currency={session.current_item.source_currency} item={session.current_item} />
          <fieldset disabled={locked || session.current_item.content_status?.status !== 'current'}>
            <legend ref={questionHeading} tabIndex={-1}><span className="assessment-question-number">Question {session.current_item.ordinal}</span>
              <span className="assessment-stem">{session.current_item.stem}</span></legend>
            <div className="assessment-options">{session.current_item.options.map(option => <label key={option.id}>
              <input type="radio" name={session.current_item!.id} value={option.id} checked={choice === option.id}
                onChange={() => setChoice(option.id)} /><span>{option.text}</span>
            </label>)}</div>
          </fieldset>
          {session.current_item.content_status?.status !== 'current' && <Notice tone="warning"><p>
            This question is no longer current. End this session and start a new quiz.</p></Notice>}
          <div className="actions"><Button type="submit" busy={busy} disabled={locked || !choice
            || session.current_item.content_status?.status !== 'current'}>Commit answer<Check size={17} /></Button>
            <Button variant="ghost" disabled={locked} onClick={sourceHelp}>View source help</Button></div>
          <p className="muted">Source help marks this attempt assisted before it opens. Committed answers cannot be changed.</p>
          {help && <div className="assessment-help"><h3>Source help · assisted</h3><SourceList sources={help.sources} /></div>}
        </form>}
        {feedback && <><FeedbackView feedback={feedback} focus /><div className="actions">
          {session.status === 'active' && session.answered_count < session.item_count && <Button disabled={locked} onClick={() =>
            perform(() => api<Session>(path(session.id)), adopt)}>Next question<ArrowRight size={17} /></Button>}
          {session.status === 'active' && session.answered_count === session.item_count && <Button disabled={locked} onClick={() => transition('end')}>Finish quiz</Button>}
        </div></>}
        {session.status === 'active' && !session.current_item && !feedback && <EmptyState title="All selected answers are committed"
          action={<Button disabled={locked} onClick={() => transition('end')}>Finish quiz</Button>}>
          <p>You can review their reasoning and sources below.</p></EmptyState>}
        <div className="actions assessment-separated"><Button variant="secondary" disabled={locked} onClick={() =>
          perform(() => api<ReviewResult>(path(session.id, '/review')), result => {
            setReview(result);
            setFeedback(current => current ? result.feedback.find(entry => entry.attempt_id === current.attempt_id) ?? current : null);
          })}>
          Review committed answers<RotateCcw size={16} /></Button>
          {session.status === 'active' && <Button variant="ghost" disabled={locked} onClick={() => transition('pause')}>Pause<Pause size={16} /></Button>}
          {session.status !== 'ended' && <Button variant="ghost" disabled={locked} onClick={() => transition('end')}>End session</Button>}
        </div>
        {review && <section className="assessment-review section"><h2>Committed answer review</h2>
          {review.feedback.length === 0 ? <p>No committed answers to review yet.</p>
            : review.feedback.map(entry => <FeedbackView key={entry.attempt_id} feedback={entry} />)}
        </section>}
      </section>
      <aside className="assessment-aside"><ScoreTable scores={session.scores} />
        <p className="muted">{session.coverage.note}. Assisted attempts and repeat exposure have separate results.</p></aside>
    </div>}
  </div>;
}
