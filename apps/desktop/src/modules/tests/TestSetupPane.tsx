import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { routes, useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, Select, Textarea } from '../../ui';
import TestVersionEditor from './TestVersionEditor';
import { useTestMutation } from './useTestMutation';
import { originLabel, type PreviewItem, type TestSetup, type TestSelection, type VersionSummary } from './types';
import './tests.css';

interface Props { selected: TestSelection; onClose: () => void; onChanged: () => void; onVersionSelected: (id: string) => void }

export default function TestSetupPane({ selected, onClose, onChanged, onVersionSelected }: Props) {
  const { navigate } = useNavigation();
  const setupPath = selected.test_id !== undefined ? '/assessment/tests/' + encodeURIComponent(selected.test_id) + '/setup' +
    (selected.version_id ? '?version_id=' + encodeURIComponent(selected.version_id) : '') :
    '/assessment/tests/versions/' + encodeURIComponent(selected.version_id) + '/setup';
  const { resource, retry } = useResource(signal => api<TestSetup>(setupPath, { signal }));
  const mutation = useTestMutation();
  const [mode, setMode] = useState('study'), [timed, setTimed] = useState(false), [minutes, setMinutes] = useState('20');
  const [renaming, setRenaming] = useState(false), [title, setTitle] = useState(''), [deleting, setDeleting] = useState(false);
  const [editing, setEditing] = useState(false), [reporting, setReporting] = useState(false), [notice, setNotice] = useState('');
  const attemptRoute = routes.find(route => String(route.id) === 'attempts');
  if (resource.status === 'loading') return <aside className="test-setup"><LoadingState label="Loading the saved version" /></aside>;
  if (resource.status === 'error') return <aside className="test-setup"><ErrorState error={resource.error} onRetry={retry} /><Button variant="ghost" onClick={onClose}>Close</Button></aside>;
  const setup = resource.data;
  const path = '/assessment/tests/' + encodeURIComponent(setup.test.id);
  function changed() { retry(); onChanged(); }
  function rename(event: FormEvent) {
    event.preventDefault();
    mutation.mutate(path, 'PATCH', { title, expected_revision: setup.test.revision }, () => { setRenaming(false); changed(); });
  }
  function lifecycle(action: 'archive' | 'restore' | 'delete') {
    mutation.mutate(path + (action === 'delete' ? '' : '/' + action), action === 'delete' ? 'DELETE' : 'POST',
      { expected_revision: setup.test.revision }, () => { changed(); if (action === 'delete') onClose(); });
  }
  function start() {
    if (!attemptRoute) { setNotice('The attempt workspace is being connected. Your saved set is ready to reopen.'); return; }
    navigate(attemptRoute.id, { payload: { version_id: setup.version.id, mode,
      timing: timed ? { kind: 'timed', duration_seconds: Number(minutes) * 60 } : { kind: 'untimed' } } });
  }
  return <aside className="test-setup" aria-label="Selected test setup">
    <div className="test-setup-heading"><span className="test-eyebrow">Version {setup.version.ordinal}</span><Button variant="ghost" onClick={onClose}>Close</Button></div>
    <h2>{setup.test.title}</h2>
    <VersionHistory testId={setup.test.id} versionId={setup.version.id} onSelected={onVersionSelected} />
    <div className="test-row-meta"><Badge tone={setup.version.status === 'ready' ? 'default' : 'warning'}>{setup.version.status === 'ready' ? 'Ready' : 'Needs review'}</Badge>
      <span>{originLabel[setup.version.origin]}</span><span>{setup.version.review_quality === 'reviewed' ? 'Reviewed' : 'Personal practice'}</span></div>
    <p className="test-length">{setup.version.item_count}<span>questions in this version</span></p>
    <p>{setup.version.topic_ids.join(' · ')}</p>
    {!!setup.content_warnings.length && <Notice tone="warning">Some pinned content is withdrawn or unavailable. Retained results stay unchanged. Choose another set for a new attempt.</Notice>}
    {setup.version.status === 'needs_review' && <Notice tone="warning">Resolve missing or ambiguous keys in a personal version before starting.</Notice>}
    {notice && <Notice>{notice}</Notice>}
    {mutation.error !== null && <ErrorState error={mutation.error} title="Your change needs a retry" onRetry={mutation.retry} />}
    <div className="tests-controls"><Select label="Mode" value={mode} onChange={event => setMode(event.target.value)}><option value="study">Study</option><option value="test">Test</option></Select>
      <label className="test-check"><input type="checkbox" checked={timed} onChange={event => setTimed(event.target.checked)} />Use a timer</label>
      {timed && <Input label="Minutes" type="number" value={minutes} min={1} max={1440} onChange={event => setMinutes(event.target.value)} />}</div>
    <p className="muted">{mode === 'study' ? 'Submit each answer deliberately and learn from its feedback.' : 'Choices remain editable until you submit the whole Test. Help is unavailable before submission.'}</p>
    <Button onClick={start} disabled={!setup.can_start || mutation.locked || (timed && (!Number.isInteger(Number(minutes)) || Number(minutes) < 1 || Number(minutes) > 1440))}>Continue to {mode === 'study' ? 'Study' : 'Test'}</Button>
    {setup.legacy && <LegacyHistory testId={setup.test.id} onResume={() => navigate('assessment', {
      payload: { legacy_session_id: setup.legacy!.session_id, legacy_kind: setup.legacy!.kind, legacy_action: 'resume' } })} />}
    <div className="test-management actions"><Button variant="ghost" disabled={mutation.locked} onClick={() => { setTitle(setup.test.title); setRenaming(value => !value); }}>Rename</Button>
      <Button variant="ghost" disabled={mutation.locked} onClick={() => setEditing(value => !value)}>Edit personal version</Button>
      <Button variant="ghost" disabled={mutation.locked} onClick={() => setReporting(value => !value)}>Question seems wrong</Button>
      <Button variant="ghost" disabled={mutation.locked} onClick={() => lifecycle(setup.test.lifecycle === 'archived' ? 'restore' : 'archive')}>{setup.test.lifecycle === 'archived' ? 'Restore' : 'Archive'}</Button>
      <Button variant="danger" disabled={mutation.locked} onClick={() => setDeleting(true)}>Delete</Button></div>
    {renaming && <form onSubmit={rename} className="section"><Input label="New title" value={title} maxLength={120} required disabled={mutation.locked} onChange={event => setTitle(event.target.value)} />
      <Button type="submit" busy={mutation.busy} disabled={mutation.locked || !title.trim()}>Save title</Button></form>}
    {deleting && <section className="section"><h3>Delete this saved test?</h3><p>The collection entry and its versions will be removed. Historical attempts and local reports retain their pinned snapshots.</p>
      <div className="actions"><Button variant="danger" disabled={mutation.locked} onClick={() => lifecycle('delete')}>Delete saved test</Button><Button variant="secondary" disabled={mutation.locked} onClick={() => setDeleting(false)}>Keep test</Button></div></section>}
    {editing && <TestVersionEditor setup={setup} onSaved={() => { setEditing(false); changed(); }} />}
    {reporting && <QuestionReport setup={setup} onSaved={() => { setReporting(false); setNotice('Your local report is saved. The key, review quality and scores have not changed.'); }} />}
  </aside>;
}

function VersionHistory({ testId, versionId, onSelected }: { testId: string; versionId: string; onSelected: (id: string) => void }) {
  const [before, setBefore] = useState<number | null>(null);
  const { resource, retry } = useResource(signal => api<{ items: VersionSummary[]; next_before: number | null }>(
    '/assessment/tests/' + encodeURIComponent(testId) + '/versions' + (before ? '?before=' + before : ''), { signal }));
  useEffect(() => { retry(); }, [before, retry]);
  if (resource.status === 'loading') return <LoadingState label="Loading version history" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  return <section className="test-history" aria-label="Saved versions"><h3>Saved versions</h3>
    <ul className="tests-list">{resource.data.items.map(version => <li key={version.id}><Button variant="ghost"
      aria-pressed={version.id === versionId} onClick={() => onSelected(version.id)}>
      Version {version.ordinal} · {version.item_count} questions · {version.review_quality === 'reviewed' ? 'Reviewed' : 'Personal'} · {version.status === 'ready' ? 'Ready' : 'Needs review'}
    </Button></li>)}</ul>
    {(before !== null || resource.data.next_before !== null) && <div className="actions">
      <Button variant="ghost" disabled={before === null} onClick={() => setBefore(null)}>Newest versions</Button>
      <Button variant="ghost" disabled={resource.data.next_before === null} onClick={() => setBefore(resource.data.next_before)}>Older versions</Button>
    </div>}
  </section>;
}

interface LegacyFeedback {
  answer_id: string; ordinal: number; stem: string; options: { id: string; text: string }[];
  selected_option_ids: string[]; correct_option_ids: string[]; correct: boolean;
  assisted: boolean; score_bucket: string; explanation: string; committed_at: string;
}

function LegacyHistory({ testId, onResume }: { testId: string; onResume: () => void }) {
  const [showing, setShowing] = useState(false);
  const { resource, retry } = useResource(signal => api<{ available: boolean; denominator: number; unanswered_not_scored: number;
    status: string; feedback: LegacyFeedback[]; legacy: { kind: string };
    scores: Record<string, { answered: number; correct: number }> }>('/assessment/tests/' + encodeURIComponent(testId) + '/history', { signal }));
  if (resource.status === 'loading') return <LoadingState label="Loading original history" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  if (!resource.data.available) return <Notice tone="warning">The original session is unavailable. The saved version remains pinned.</Notice>;
  return <section className="test-history"><h3>Original Study history</h3>
    <p>{resource.data.denominator} committed answers · {resource.data.unanswered_not_scored} unscored blanks</p>
    {Object.entries(resource.data.scores).map(([bucket, score]) => <p key={bucket}>{bucket}: {score.correct} / {score.answered}</p>)}
    <Button variant="secondary" onClick={() => setShowing(value => !value)}>{showing ? 'Hide original answers' : 'View original committed answers'}</Button>
    {showing && <div className="test-history"><p>Original commitments and scores are retained. Blanks have no feedback.</p>
      {resource.data.feedback.length === 0 && <p>No answers were committed in this original Study.</p>}
      {resource.data.feedback.map(answer => <article key={answer.answer_id} className="section"><h4>Question {answer.ordinal}</h4>
        <p>{answer.stem}</p><ul>{answer.options.map(option => <li key={option.id}>{option.id}. {option.text}</li>)}</ul>
        <p>Committed choice: {answer.selected_option_ids.join(', ')} · {resource.data.legacy.kind === 'generated' ? 'Personal key comparison' : 'Original reviewed result'}: {answer.correct ? 'Correct' : 'Incorrect'}</p>
        <p>Original key: {answer.correct_option_ids.join(', ')} · {answer.score_bucket}{answer.assisted ? ' · Assisted' : ''}</p>
        <p>{answer.explanation}</p>
      </article>)}</div>}
    {resource.data.status !== 'ended' && <Button variant="ghost" onClick={onResume}>Resume original Study</Button>}
  </section>;
}

function QuestionReport({ setup, onSaved }: { setup: TestSetup; onSaved: () => void }) {
  const path = '/assessment/tests/' + encodeURIComponent(setup.test.id) + '/versions/' + encodeURIComponent(setup.version.id);
  const { resource, retry } = useResource(signal => api<{ items: PreviewItem[] }>(path + '/preview', { signal }));
  const mutation = useTestMutation(), [item, setItem] = useState(''), [text, setText] = useState('');
  if (resource.status === 'loading') return <LoadingState label="Loading question references" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  return <form className="section" onSubmit={event => { event.preventDefault(); mutation.mutate(path + '/reports', 'POST', {
    item_id: item || resource.data.items[0].item_id, report_text: text }, onSaved); }}>
    <h3>Question seems wrong</h3><p>Save a local note against this exact version.</p>
    <Select label="Question" value={item || resource.data.items[0].item_id} disabled={mutation.locked} onChange={event => setItem(event.target.value)}>
      {resource.data.items.map((question, index) => <option value={question.item_id} key={question.item_id}>{index + 1}. {question.stem.slice(0, 100)}</option>)}</Select>
    <Textarea label="What seems wrong?" value={text} maxLength={2000} required disabled={mutation.locked} onChange={event => setText(event.target.value)} />
    {mutation.error !== null && <ErrorState error={mutation.error} onRetry={mutation.retry} />}
    <Button type="submit" disabled={mutation.locked || !text.trim()} busy={mutation.busy}>Save local report</Button>
  </form>;
}
