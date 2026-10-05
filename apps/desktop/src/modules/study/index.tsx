import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, CalendarDays, Check, ChevronRight, MessageCircle, Stethoscope } from 'lucide-react';
import { api, isCancelled } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import StudyTrack, { contentTrackId, type StudySelection, type TrackMetadata } from './StudyTrack';
import './study.css';

// The question is the focal action; real continuation/review sits below it, goals alongside.
// Flow tokens and quiet paper/teal surfaces make this a reading and study space.
interface Activity { id: string; topic_id: string; title: string; due_date: string; state: 'planned' | 'completed' | 'skipped'; duration_minutes: number; kind: string; manual_override: boolean; outside_selection?: boolean; reason: { description: string; question_id?: string; track?: 'general_nephrology' | 'esen_eph' } }
interface Goals { hours_per_week: number; exam_date: string | null; topic_ids: string[]; track: 'general' | 'eseneph' }
interface Home { resume: { id: string; title: string; updated_at: string }[]; review: Activity[]; upcoming: Activity[]; topics: { id: string; title: string; objectives?: { id: string; text: string }[] }[]; goals: Goals; tracks?: TrackMetadata[]; selection?: StudySelection; progress: { groups: Record<string, { answered: number; correct: number }> }; updates: { id: string; title: string; publication_date?: string; reviewed_at?: string }[] }
type ActivityChange = Partial<Pick<Activity, 'due_date' | 'state'>>;
interface ActivityWrite { queued: ActivityChange | null; controller: AbortController | null }
interface ActivityFailure { error: unknown; values: ActivityChange }
type Operation = 'plan' | 'goals';

export default function Study() {
  const { navigate } = useNavigation();
  const { resource, retry } = useResource(signal => api<Home>('/study/home', { signal }));
  const [snapshot, setSnapshot] = useState<Home | null>(null);
  useEffect(() => { if (resource.status === 'ready') setSnapshot(resource.data); }, [resource]);
  const [question, setQuestion] = useState('');
  const [plan, setPlan] = useState<Activity[] | null>(null);
  const [goals, setGoals] = useState<Goals | null>(null);
  const [savedGoals, setSavedGoals] = useState<Goals | null>(null);
  const [settings, setSettings] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const busy = operation !== null;
  const [error, setError] = useState<{ operation: Operation; error: unknown } | null>(null);
  const [notice, setNotice] = useState('');
  const mounted = useRef(false);
  const writes = useRef(new Map<string, ActivityWrite>());
  const [pendingRows, setPendingRows] = useState<Set<string>>(new Set());
  const [rowFailures, setRowFailures] = useState<Record<string, ActivityFailure>>({});
  const [dateDrafts, setDateDrafts] = useState<Record<string, string>>({});
  const dateDraftsRef = useRef<Record<string, string>>({});
  const globalWrite = useRef<{ operation: Operation; controller: AbortController } | null>(null);
  const goalEdits = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; globalWrite.current?.controller.abort(); globalWrite.current = null;
      for (const write of writes.current.values()) write.controller?.abort(); writes.current.clear();
    };
  }, []);
  const home = resource.status === 'ready' ? resource.data : snapshot;
  if (!home) return resource.status === 'error' ? <ErrorState error={resource.error} onRetry={retry} /> : <LoadingState label="Loading your learning home" />;
  const currentGoals = goals ?? home.goals;
  const confirmedGoals = savedGoals ?? home.goals;
  const unsavedGoals = JSON.stringify(currentGoals) !== JSON.stringify(confirmedGoals);
  const selectedTrack = home.tracks?.find(track => track.id === contentTrackId(home.goals.track)) ?? {
    id: contentTrackId(home.goals.track), title: home.goals.track === 'eseneph' ? 'ESENeph preparation' : 'General nephrology' };
  const draftTrack = home.tracks?.find(track => track.id === contentTrackId(currentGoals.track));
  const activities = plan ?? home.upcoming;
  function start(event: FormEvent) { event.preventDefault(); if (question.trim()) navigate('learn', { payload: { question: question.trim() } }); }
  async function propose() {
    if (!mounted.current || globalWrite.current || writes.current.size || unsavedGoals) return;
    const controller = new AbortController(); globalWrite.current = { operation: 'plan', controller };
    setOperation('plan'); setError(null); setNotice('');
    try {
      const result = await api<{ activities: Activity[]; message?: string; explanation?: string }>('/study/plan/propose', { method: 'POST', signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      setPlan(result.activities); setNotice(result.message ?? result.explanation ?? 'Your study plan is ready.'); retry();
    } catch (caught) {
      if (mounted.current && !controller.signal.aborted && !isCancelled(caught)) setError({ operation: 'plan', error: caught });
    } finally {
      if (globalWrite.current?.controller === controller) globalWrite.current = null;
      if (mounted.current && !controller.signal.aborted) setOperation(null);
    }
  }
  async function change(id: string, values: ActivityChange) {
    if (!mounted.current || globalWrite.current) return;
    const intent = { ...rowFailures[id]?.values, ...values };
    setRowFailures(previous => { const next = { ...previous }; delete next[id]; return next; });
    const active = writes.current.get(id);
    if (active) { active.queued = { ...active.queued, ...intent }; return; }
    const write: ActivityWrite = { queued: intent, controller: null };
    writes.current.set(id, write); setPendingRows(new Set(writes.current.keys()));
    let saved = false;
    try {
      // One confirmed write per activity; rapid date edits retain only the latest queued intent.
      while (mounted.current && write.queued) {
        const next = write.queued; write.queued = null;
        const controller = new AbortController(); write.controller = controller;
        try {
          const result = await api<Activity>('/study/plan/' + encodeURIComponent(id), { method: 'PATCH', body: next, signal: controller.signal });
          if (!mounted.current || controller.signal.aborted) return;
          saved = true;
          setPlan(previous => (previous ?? activities).map(row => row.id === id ? result : row));
          const queued = writes.current.get(id)?.queued;
          if (next.due_date && dateDraftsRef.current[id] === next.due_date && !queued?.due_date) {
            delete dateDraftsRef.current[id];
            setDateDrafts({ ...dateDraftsRef.current });
          }
        } catch (caught) {
          if (!mounted.current || controller.signal.aborted || isCancelled(caught)) return;
          // A lost response cannot establish whether the server committed. Retry the latest intent explicitly.
          const latest = { ...next, ...writes.current.get(id)?.queued }; write.queued = null;
          setRowFailures(previous => ({ ...previous, [id]: { error: caught, values: latest } }));
          break;
        }
      }
    } finally {
      if (writes.current.get(id) === write) writes.current.delete(id);
      if (mounted.current) { setPendingRows(new Set(writes.current.keys())); if (saved) retry(); }
    }
  }
  function move(id: string, value: string) {
    dateDraftsRef.current[id] = value; setDateDrafts({ ...dateDraftsRef.current });
    setRowFailures(previous => { const next = { ...previous }; delete next[id]; return next; });
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) void change(id, { due_date: value });
  }
  function editGoals(values: Goals) {
    ++goalEdits.current; setGoals(values);
    if (error?.operation === 'goals') setError(null);
  }
  async function persistGoals() {
    if (!mounted.current || globalWrite.current || writes.current.size) return;
    const controller = new AbortController(), edited = goalEdits.current;
    globalWrite.current = { operation: 'goals', controller };
    const submitted = { ...currentGoals, topic_ids: [...currentGoals.topic_ids] };
    setOperation('goals'); setError(null); setNotice('');
    try {
      const result = await api<Goals>('/study/goals', { method: 'PUT', body: submitted, signal: controller.signal });
      if (!mounted.current || controller.signal.aborted) return;
      setSavedGoals(result); setPlan(null);
      if (goalEdits.current === edited) { setGoals(result); setSettings(false); setNotice('Your study preferences are saved.'); }
      else setNotice('Your preferences are saved. Newer edits are still unsaved.');
      retry();
    } catch (caught) {
      if (mounted.current && !controller.signal.aborted && !isCancelled(caught)) setError({ operation: 'goals', error: caught });
    } finally {
      if (globalWrite.current?.controller === controller) globalWrite.current = null;
      if (mounted.current && !controller.signal.aborted) setOperation(null);
    }
  }
  function saveGoals(event: FormEvent) { event.preventDefault(); void persistGoals(); }

  return <><PageHeader title="A little learning, every day." description="Pick up where you left off, or follow a new question." actions={<Button variant="ghost" onClick={() => setSettings(value => !value)}><CalendarDays size={17} />Study preferences</Button>} />
    <div className="today-layout"><div className="today-main">
      <form className="home-question" onSubmit={start}><h2>What would you like to understand?</h2><Textarea label="Your nephrology question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="A mechanism, a topic or a question you want to explore…" maxLength={16000} /><div className="actions"><Button type="submit" disabled={!question.trim()}>Explore in Learn<ArrowRight size={17} /></Button><Button variant="ghost" onClick={() => navigate('library')}>Bring a source<BookOpen size={17} /></Button></div></form>
      {resource.status === 'loading' && <p className="study-refresh-status muted" role="status">Refreshing your study records…</p>}
      {resource.status === 'error' && <ErrorState title="Study records could not be refreshed" error={resource.error} onRetry={retry} />}
      {error !== null && <ErrorState title={error.operation === 'plan' ? 'The suggested plan could not be confirmed' : 'Your preferences could not be confirmed'} error={error.error} onRetry={busy || pendingRows.size > 0 ? undefined : () => { if (error.operation === 'plan') void propose(); else void persistGoals(); }} />}{notice && <Notice><p>{notice}</p></Notice>}
      <section className="section"><h2>Continue learning</h2>{home.resume.length ? <div className="home-record-list">{home.resume.map(row => <button key={row.id} onClick={() => navigate('learn', { payload: { thread_id: row.id } })}><MessageCircle size={18} /><span><strong>{row.title}</strong><small>Last opened {new Date(row.updated_at).toLocaleDateString()}</small></span><ChevronRight size={18} /></button>)}</div> : <p>Start a study discussion. Your ordinary learning threads will be ready to resume here.</p>}</section>
      <section className="section"><div className="section-heading"><h2>Your next study</h2><Button variant="ghost" busy={operation === 'plan'} disabled={busy || pendingRows.size > 0 || unsavedGoals} onClick={propose}>Suggest a plan</Button></div>
        <StudyTrack track={selectedTrack} selection={home.selection} />
        {unsavedGoals && <p className="field-hint">Save your changed preferences before suggesting a plan.</p>}
        {activities.length ? <div className="study-activities">{activities.map(row => <article key={row.id} className={'study-activity activity-' + row.state} aria-busy={pendingRows.has(row.id) || undefined}>
        <div className="activity-main"><div className="activity-title"><strong>{row.title}</strong><Badge tone={row.state === 'planned' ? 'default' : 'neutral'}>{row.state === 'planned' ? row.kind === 'mistake-review' ? 'Review' : 'Study' : row.state}</Badge></div><p>{row.reason.description}</p>
          <div className="activity-meta"><label>When <input aria-label={'Move ' + row.title} type="date" value={dateDrafts[row.id] ?? row.due_date} disabled={busy} onChange={event => move(row.id, event.target.value)} /></label><span>{row.duration_minutes} min</span>{row.manual_override && <span>Adjusted by you</span>}</div>
          {row.outside_selection && row.manual_override && <p className="field-hint">Kept from your manual plan, outside the current track or topics.</p>}
          {dateDrafts[row.id] === '' && <p className="field-hint">Choose a complete date to move this activity.</p>}
          {pendingRows.has(row.id) && <p className="study-save-status muted" role="status">Saving your change…</p>}
        </div>
        <div className="activity-actions">{row.state === 'planned' && <><Button variant="secondary" onClick={() => navigate(row.kind === 'mistake-review' ? 'assessment' : 'learn', { payload: { topic_id: row.topic_id, question_id: row.reason.question_id, track: row.reason.track ?? 'general_nephrology' } })}>Start<ArrowRight size={15} /></Button><Button variant="ghost" disabled={busy || pendingRows.has(row.id)} onClick={() => void change(row.id, { state: 'completed' })}><Check size={15} />Mark done</Button><Button variant="ghost" disabled={busy || pendingRows.has(row.id)} onClick={() => void change(row.id, { state: 'skipped' })}>Skip</Button></>}</div>
        {rowFailures[row.id] && <ErrorState title="This study change could not be confirmed" error={rowFailures[row.id].error} onRetry={busy ? undefined : () => void change(row.id, rowFailures[row.id].values)} />}
      </article>)}</div> : <p>A plan can balance selected topics and your recorded mistakes. Explore freely whenever you prefer.</p>}</section>
      <section className="section"><h2>Explore nephrology</h2>{home.topics.length ? <div className="topic-directory">{home.topics.map(topic => <button key={topic.id} onClick={() => navigate('learn', { payload: { topic_id: topic.id, question: 'Help me study ' + topic.title + '.' } })}>{topic.title}<ArrowRight size={15} /></button>)}</div> : <p>Topic coverage appears when the original learning pack is installed.</p>}</section>
    </div><aside className="today-support">
      <section className="daily-case-entry"><Stethoscope size={23} /><h2>A question from your day?</h2><p>Discuss a daily case in a temporary space, then choose whether to save it.</p><Button variant="ghost" onClick={() => navigate('cases')}>Discuss a case<ArrowRight size={16} /></Button></section>
      {settings && <form className="study-settings section" onSubmit={saveGoals}><h2>Your study preferences</h2><Input label="Hours per week" type="number" min={1} max={40} required value={currentGoals.hours_per_week} onChange={event => editGoals({ ...currentGoals, hours_per_week: Number(event.target.value) })} /><Input label="Exam date (optional)" type="date" value={currentGoals.exam_date ?? ''} onChange={event => editGoals({ ...currentGoals, exam_date: event.target.value || null })} /><Select label="Track" value={currentGoals.track} onChange={event => editGoals({ ...currentGoals, track: event.target.value as Goals['track'] })}><option value="general">General nephrology</option><option value="eseneph">ESENeph preparation</option></Select>
        <p className="muted">Saved preferences guide automatic suggestions. ESENeph uses only active exam-domain objective links from the published partial mapping.</p>
        {currentGoals.track === 'eseneph' && !draftTrack?.available && <p>{draftTrack?.reason ?? 'ESENeph programme metadata is unavailable. You can save the preference; mapped suggestions will wait for eligible content.'}</p>}
        <fieldset className="topic-preferences"><legend>Topics to emphasise</legend>{home.topics.map(topic => {
          const outsideMapping = currentGoals.track === 'eseneph' && !topic.objectives?.some(objective => draftTrack?.aligned_objective_ids?.includes(objective.id));
          return <div key={topic.id} className="study-topic-choice"><label><input type="checkbox" aria-describedby={outsideMapping ? 'study-topic-' + topic.id + '-mapping' : undefined} checked={currentGoals.topic_ids.includes(topic.id)} onChange={event => editGoals({ ...currentGoals, topic_ids: event.target.checked ? [...currentGoals.topic_ids, topic.id] : currentGoals.topic_ids.filter(id => id !== topic.id) })} />
            <span>{topic.title}</span></label>{outsideMapping && <small id={'study-topic-' + topic.id + '-mapping'} className="muted">Outside this ESENeph exam-domain mapping</small>}</div>;
        })}</fieldset><p className="field-hint">Leave topics unchecked to use all available topics in the selected track.</p><Button type="submit" busy={operation === 'goals'} disabled={operation === 'plan' || pendingRows.size > 0}>Save preferences</Button></form>}
      <section className="section"><h2>Reviewed updates</h2>{home.updates.length ? home.updates.map(item => <button className="home-update" key={item.id} onClick={() => navigate('updates', { payload: { entry_id: item.id } })}><strong>{item.title}</strong><small>Reviewed {item.reviewed_at ? new Date(item.reviewed_at).toLocaleDateString() : 'date unavailable'}</small></button>) : <p>Reviewed changes in guidance and research appear here. New discoveries stay in the review queue.</p>}<Button variant="ghost" onClick={() => navigate('updates')}>Open Updates<ArrowRight size={16} /></Button></section>
      <section className="section"><h2>Observed assessment</h2>{home.progress.groups.fresh.answered ? <p>{home.progress.groups.fresh.correct} correct from {home.progress.groups.fresh.answered} fresh unassisted reviewed answers across all tracks.</p> : <p>Take a reviewed test to see your results. Conversations do not count as mastery.</p>}<Button variant="secondary" onClick={() => navigate('assessment', { payload: { track: contentTrackId(home.goals.track) } })}>Open Test<ArrowRight size={16} /></Button></section>
    </aside></div></>;
}
