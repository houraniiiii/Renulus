import { useState, type FormEvent } from 'react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { routes, useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, Select, Textarea } from '../../ui';
import TestVersionEditor from './TestVersionEditor';
import { useTestMutation } from './useTestMutation';
import { originLabel, type PreviewItem, type TestSetup, type TestSelection } from './types';

interface Props { selected: TestSelection; onClose: () => void; onChanged: () => void }

export default function TestSetupPane({ selected, onClose, onChanged }: Props) {
  const { navigate } = useNavigation();
  const setupPath = selected.test_id ? '/assessment/tests/' + encodeURIComponent(selected.test_id) + '/setup' +
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
    {setup.legacy && <LegacyHistory testId={setup.test.id} onOpen={() => navigate('assessment', {
      payload: { legacy_session_id: setup.legacy!.session_id, legacy_kind: setup.legacy!.kind } })} />}
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

function LegacyHistory({ testId, onOpen }: { testId: string; onOpen: () => void }) {
  const { resource, retry } = useResource(signal => api<{ available: boolean; denominator: number; unanswered_not_scored: number;
    scores: Record<string, { answered: number; correct: number }> }>('/assessment/tests/' + encodeURIComponent(testId) + '/history', { signal }));
  if (resource.status === 'loading') return <LoadingState label="Loading original history" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  if (!resource.data.available) return <Notice tone="warning">The original session is unavailable. The saved version remains pinned.</Notice>;
  return <section className="test-history"><h3>Original Study history</h3>
    <p>{resource.data.denominator} committed answers · {resource.data.unanswered_not_scored} unscored blanks</p>
    {Object.entries(resource.data.scores).map(([bucket, score]) => <p key={bucket}>{bucket}: {score.correct} / {score.answered}</p>)}
    <Button variant="secondary" onClick={onOpen}>Open original history</Button></section>;
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
