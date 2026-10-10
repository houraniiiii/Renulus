import { useEffect, useState, useSyncExternalStore } from 'react';
import { Badge, Button, ErrorState, Notice, PageHeader, Panel, Textarea } from '../../ui';
import { practiceLabel } from './types';
import type { HelpReceipt } from './types';
import type { AttemptsPageProps } from './index';
import type { AttemptSession } from './session';
import Feedback from './Feedback';

export default function AttemptRun({ session, onHelp, onOpenReference, onRetake }: { session: AttemptSession } & Omit<AttemptsPageProps, 'attemptId' | 'versionId'>) {
  const state = useSyncExternalStore(session.subscribe, session.snapshot); const attempt = state.attempt!; const draft = state.draft!;
  const [confirm, setConfirm] = useState(false); const [reporting, setReporting] = useState<string | null>(null); const [reportText, setReportText] = useState('');
  const [reportSaved, setReportSaved] = useState(false); const [mistakesOnly, setMistakesOnly] = useState(false); const [now, setNow] = useState(performance.now());
  useEffect(() => { const timer = setInterval(() => setNow(performance.now()), 1000); return () => clearInterval(timer); }, []);
  const item = attempt.position === draft.position ? attempt.current_item : null;
  const currentAnswer = draft.answers[draft.position]; const committed = attempt.committed.find(entry => entry.item_id === currentAnswer.item_id);
  const selected = currentAnswer.option_ids; const disabled = state.busy || attempt.status !== 'active' || !!committed;
  const reviewed = attempt.origin === 'reviewed_bank' && attempt.review_quality === 'reviewed';
  const remaining = attempt.timing.remaining_seconds;
  const seconds = remaining === null ? null : Math.max(0, remaining - (attempt.status === 'active' ? Math.floor(Math.max(0, now - state.receivedAt) / 1000) : 0));
  const timeLabel = seconds === null ? 'Untimed' : Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  const swallow = (promise: Promise<unknown>) => { void promise.catch(() => { /* Recovery state remains visible. */ }); };
  function changeOption(id: string, checked: boolean) { session.change({ ...draft, answers: draft.answers.map(answer => answer.item_id === currentAnswer.item_id
    ? { ...answer, option_ids: checked ? reviewed ? [id] : [...answer.option_ids, id] : answer.option_ids.filter(value => value !== id) } : answer) }); }
  function submit() { swallow(session.action('submit', (latest, displayed) => ({ expected_draft_revision: latest.draft_revision, latest_draft: latest.status === 'active' ? displayed : null })).then(() => setConfirm(false))); }
  async function help(kind: HelpReceipt['context']['kind']) {
    try { await session.action<HelpReceipt>('help', latest => ({ expected_revision: latest.draft_revision, expected_policy_revision: latest.policy.revision, item_id: latest.current_item!.item_id, kind }));
      const receipt = session.snapshot().help; if (receipt && (kind === 'notes' || kind === 'chat')) await onHelp?.(receipt);
    } catch { /* Failed/stale receipts never reach the consumer. */ }
  }
  function report(itemId: string) { setReporting(itemId); setReportText(''); setReportSaved(false); }
  return <div className="attempt-page"><PageHeader title={attempt.result ? (attempt.mode === 'test' ? 'Test results' : 'Study summary') : (attempt.mode === 'test' ? 'Test' : 'Study')}
    description={practiceLabel(attempt)} actions={<div className="attempt-meta"><span>{timeLabel}</span><Badge tone={state.error ? 'warning' : 'neutral'}>{state.saving || state.dirty ? 'Saving draft…' : state.busy ? 'Saving action…' : 'Saved'}</Badge></div>} />
    {attempt.provenance_unavailable && <Notice tone="warning">The original collection is unavailable. This attempt keeps its pinned version and historical result.</Notice>}
    {state.warning && <Notice tone="warning">{state.warning}</Notice>}
    {!!state.error && <><ErrorState error={state.error} title="This action needs recovery" onRetry={() => swallow(session.retry())} />
      <Notice tone="warning"><p>Your displayed changes are retained here. Reopening uses the last backend-saved state.</p>
        <Button variant="secondary" disabled={state.busy || state.saving} onClick={() => { void session.open(attempt.id); }}>Reopen saved attempt</Button></Notice></>}
    {attempt.result ? <><Panel><div className="attempt-result-score"><strong>{attempt.result.correct}<span> / {attempt.result.denominator}</span></strong><p>Correct / included questions</p></div>
      <p>{attempt.result.unanswered} unanswered · {attempt.result.excluded} excluded · {attempt.result.not_submitted} not submitted</p>
      {attempt.result.reason === 'deadline' && <p>The timer ended this Test using backend-saved answers.</p>}
      <table className="attempt-cohorts"><caption>{reviewed ? 'Reviewed cohorts for this attempt' : 'Personal practice for this attempt'}</caption><thead><tr><th scope="col">Cohort</th><th scope="col">Correct / included</th></tr></thead>
        <tbody>{(['fresh', 'assisted', 'repeat', 'personal'] as const).filter(bucket => reviewed ? bucket !== 'personal' : bucket === 'personal').map(bucket => <tr key={bucket}><th scope="row">{bucket}</th><td>{attempt.result!.cohorts[bucket].correct} / {attempt.result!.cohorts[bucket].denominator}</td></tr>)}</tbody></table>
      <div className="actions"><Button variant="secondary" disabled={attempt.provenance_unavailable} onClick={() => onRetake?.(attempt.version_id)}>Retake this version</Button>
        <label><input type="checkbox" checked={mistakesOnly} onChange={event => setMistakesOnly(event.target.checked)} /> Mistakes and unanswered only</label></div></Panel>
      {attempt.result.items.filter(entry => !mistakesOnly || ['incorrect', 'unanswered'].includes(entry.outcome)).map(entry => <Panel key={entry.item_id}><p className="muted">Question {attempt.answers.findIndex(answer => answer.item_id === entry.item_id) + 1}</p>
        <h2 className="attempt-stem">{entry.question.stem}</h2><Feedback entry={entry} /><Button variant="ghost" onClick={() => report(entry.item_id)}>Question seems wrong</Button></Panel>)}
      {!attempt.result.items.length && <Notice>No Study answers were committed. Pending drafts were not graded.</Notice>}</>
    : <><div className="attempt-progress"><span>Question {draft.position + 1} of {attempt.item_count}</span><span>{attempt.mode === 'study' ? attempt.committed.length + ' committed' : draft.answers.filter(answer => answer.option_ids.length).length + ' answered in draft'}</span></div>
      {attempt.mode === 'test' && <Notice>Learning help stays restricted until you submit this Test. You can leave and resume; timed Tests continue while closed.</Notice>}
      {attempt.status === 'paused' && <Panel><h2>Study is paused</h2><p>Your question, draft and committed answers are saved.</p><Button busy={state.busy} onClick={() => swallow(session.action('resume', latest => ({ expected_revision: latest.draft_revision })))}>Resume study</Button></Panel>}
      {attempt.status === 'timer_expired' && <Panel><h2>Your Study timer ended</h2><p>The pending answer remains a draft. Choose how to continue.</p><div className="actions"><Button onClick={() => swallow(session.action('continue-untimed', latest => ({ expected_revision: latest.draft_revision })))}>Continue untimed</Button><Button variant="secondary" onClick={submit}>Finish study</Button></div></Panel>}
      {attempt.status === 'active' && <Panel className="attempt-question">{item ? <><h2 className="attempt-stem">{item.stem}</h2>
        {item.availability !== 'current' && <Notice tone="warning">This pinned item is {item.availability}. It will be flagged separately in the result.</Notice>}
        <fieldset className="attempt-options" disabled={disabled}><legend>Select your answer</legend>{item.options.map((option, index) => <label className={selected.includes(option.id) ? 'is-selected' : ''} key={option.id}>
          <input type={reviewed ? 'radio' : 'checkbox'} name={'choices-' + item.item_id} checked={selected.includes(option.id)} onChange={event => changeOption(option.id, event.target.checked)} /><span className="attempt-option-letter" aria-hidden="true">{String.fromCharCode(65 + index)}</span><span>{option.text}</span>
        </label>)}</fieldset>
        {!committed && <Button variant="ghost" disabled={disabled || !selected.length} onClick={() => session.change({ ...draft, answers: draft.answers.map(answer => answer.item_id === currentAnswer.item_id ? { ...answer, option_ids: [] } : answer) })}>Clear choice</Button>}
        {committed ? <Feedback entry={committed} /> : attempt.mode === 'study' && <div className="actions"><Button busy={state.busy} disabled={!selected.length} onClick={() => swallow(session.action('submit-answer', latest => ({ expected_revision: latest.draft_revision, item_id: latest.current_item!.item_id, option_ids: session.snapshot().draft!.answers[latest.position].option_ids })))}>Submit answer</Button>
          <Button variant="ghost" disabled={state.busy} onClick={() => { void help('hint'); }}>Hint</Button><Button variant="ghost" disabled={state.busy} onClick={() => { void help('sources'); }}>Sources</Button>
          <Button variant="ghost" disabled={state.busy || !onHelp} title={!onHelp ? 'Notes help is currently unavailable.' : undefined} onClick={() => { void help('notes'); }}>Notes</Button>
          <Button variant="ghost" disabled={state.busy || !onHelp} title={!onHelp ? 'Chat help is currently unavailable.' : undefined} onClick={() => { void help('chat'); }}>Ask in chat</Button></div>}
        {state.help && state.help.context.item_id === item.item_id && <aside className="attempt-help" aria-label="Recorded assistance">{state.help.hint && <p>{state.help.hint}</p>}
          {state.help.context.kind === 'sources' && (!state.help.references.length ? <p>No reader references were saved with this version.</p> : state.help.references.map((reference, index) => <Button key={index} variant="secondary" disabled={!onOpenReference} onClick={() => onOpenReference?.(reference, state.help!.context)}>Open source {index + 1}</Button>))}
          <p className="muted">Assistance is recorded for this question.</p></aside>}
        <Button variant="ghost" onClick={() => report(item.item_id)}>Question seems wrong</Button></> : <><p>The next question is waiting for its presentation record.</p><Button busy={state.busy || state.saving} onClick={() => swallow(session.action('present', latest => ({ expected_revision: latest.draft_revision, item_id: latest.answers[latest.position].item_id })))}>Open question</Button></>}</Panel>}
      {attempt.mode === 'test' && <Panel><h2>Question navigator</h2><p className="muted">Choices and review marks; no correctness is shown.</p><div className="attempt-navigator">{draft.answers.map((answer, index) => <Button key={answer.item_id} variant={index === draft.position ? 'primary' : 'secondary'} disabled={state.busy || attempt.status !== 'active'} aria-current={index === draft.position ? 'step' : undefined} onClick={() => swallow(session.move(index))} aria-label={'Question ' + (index + 1) + (answer.option_ids.length ? ', answered' : ', unanswered') + (answer.marked ? ', marked for review' : '')}>{index + 1}{answer.marked ? ' ⚑' : answer.option_ids.length ? ' •' : ''}</Button>)}</div>
        <label><input type="checkbox" checked={currentAnswer.marked} disabled={state.busy || attempt.status !== 'active'} onChange={event => session.change({ ...draft, answers: draft.answers.map(answer => answer.item_id === currentAnswer.item_id ? { ...answer, marked: event.target.checked } : answer) })} /> Mark this question for review</label></Panel>}
      <div className="actions attempt-actions"><Button variant="secondary" disabled={state.busy || draft.position === 0 || attempt.status !== 'active'} onClick={() => swallow(session.move(draft.position - 1))}>Previous</Button>
        <Button disabled={state.busy || draft.position + 1 >= attempt.item_count || attempt.status !== 'active' || (attempt.mode === 'study' && !committed)} onClick={() => swallow(session.move(draft.position + 1))}>{attempt.mode === 'test' && !selected.length ? 'Skip to next' : 'Next'}</Button>
        {attempt.mode === 'study' && attempt.status === 'active' && <Button variant="secondary" disabled={state.busy} onClick={() => swallow(session.action('pause', latest => ({ expected_revision: latest.draft_revision })))}>Pause study</Button>}
        <Button variant="secondary" disabled={state.busy} onClick={() => setConfirm(true)}>{attempt.mode === 'test' ? 'Review and submit test' : 'Finish study'}</Button></div>
      {confirm && <Panel className="attempt-confirm"><h2>{attempt.mode === 'test' ? 'Submit this Test?' : 'Finish this Study attempt?'}</h2><p>{draft.answers.filter(answer => answer.option_ids.length).length} answered in draft · {draft.answers.filter(answer => !answer.option_ids.length).length} unanswered · {draft.answers.filter(answer => answer.marked).length} marked for review</p>
        <p>{attempt.mode === 'test' ? 'Unanswered questions count as blanks. Submission saves the latest displayed choices and commits the whole result.' : 'The summary includes committed answers. Your pending selections will not be graded.'}</p>
        <div className="actions"><Button busy={state.busy} onClick={submit}>{attempt.mode === 'test' ? 'Submit test' : 'Finish study'}</Button><Button variant="secondary" disabled={state.busy} onClick={() => setConfirm(false)}>Keep working</Button></div></Panel>}
    </>}
    {reporting && <Panel className="attempt-report"><h2>Question seems wrong</h2>{reportSaved ? <p role="status">Your local report was saved. It does not change this answer or result.</p> : <>
      <Textarea label="What seems wrong?" hint="This report stays local and pins the question and attempt versions." maxLength={2000} value={reportText} onChange={event => setReportText(event.target.value)} />
      <Button busy={state.busy} disabled={!reportText.trim()} onClick={() => swallow(session.action('reports', () => ({ item_id: reporting, report_text: reportText.trim() })).then(() => setReportSaved(true)))}>Save report</Button></>}
      <Button variant="ghost" onClick={() => setReporting(null)}>Close report</Button></Panel>}
  </div>;
}
