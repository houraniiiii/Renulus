import { useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, CalendarDays, Check, ChevronRight, MessageCircle, Stethoscope } from 'lucide-react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import './study.css';

// The question is the focal action; real continuation/review sits below it, goals alongside.
// Flow tokens and quiet paper/teal surfaces make this a reading and study space.
interface Activity { id: string; topic_id: string; title: string; due_date: string; state: 'planned' | 'completed' | 'skipped'; duration_minutes: number; kind: string; manual_override: boolean; reason: { description: string; question_id?: string } }
interface Goals { hours_per_week: number; exam_date: string | null; topic_ids: string[]; track: 'general' | 'eseneph' }
interface Home { resume: { id: string; title: string; updated_at: string }[]; review: Activity[]; upcoming: Activity[]; topics: { id: string; title: string }[]; goals: Goals; progress: { groups: Record<string, { answered: number; correct: number }> }; updates: { id: string; title: string; publication_date?: string; reviewed_at?: string }[] }

export default function Study() {
  const { navigate } = useNavigation();
  const { resource, retry } = useResource(signal => api<Home>('/study/home', { signal }));
  const [question, setQuestion] = useState('');
  const [plan, setPlan] = useState<Activity[] | null>(null);
  const [goals, setGoals] = useState<Goals | null>(null);
  const [settings, setSettings] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [notice, setNotice] = useState('');
  if (resource.status === 'loading') return <LoadingState label="Loading your learning home" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  const home = resource.data;
  const currentGoals = goals ?? home.goals;
  const activities = plan ?? home.upcoming;
  function start(event: FormEvent) { event.preventDefault(); if (question.trim()) navigate('learn', { payload: { question: question.trim() } }); }
  async function propose() {
    setBusy(true); setError(null);
    try { const result = await api<{ activities: Activity[]; message?: string; explanation?: string }>('/study/plan/propose', { method: 'POST' }); setPlan(result.activities); setNotice(result.message ?? result.explanation ?? 'Your study plan is ready.'); }
    catch (caught) { setError(caught); } finally { setBusy(false); }
  }
  async function change(id: string, values: Partial<Activity>) {
    setError(null);
    try { const result = await api<Activity>('/study/plan/' + id, { method: 'PATCH', body: values }); setPlan(previous => (previous ?? activities).map(row => row.id === id ? result : row)); retry(); }
    catch (caught) { setError(caught); }
  }
  async function saveGoals(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { const result = await api<Goals>('/study/goals', { method: 'PUT', body: currentGoals }); setGoals(result); setSettings(false); retry(); setNotice('Your study preferences are saved.'); }
    catch (caught) { setError(caught); } finally { setBusy(false); }
  }

  return <><PageHeader title="A little learning, every day." description="Pick up where you left off, or follow a new question." actions={<Button variant="ghost" onClick={() => setSettings(value => !value)}><CalendarDays size={17} />Study preferences</Button>} />
    <div className="today-layout"><div className="today-main">
      <form className="home-question" onSubmit={start}><h2>What would you like to understand?</h2><Textarea label="Your nephrology question" value={question} onChange={event => setQuestion(event.target.value)} placeholder="A mechanism, a topic or a question you want to explore…" maxLength={16000} /><div className="actions"><Button type="submit" disabled={!question.trim()}>Explore in Learn<ArrowRight size={17} /></Button><Button variant="ghost" onClick={() => navigate('library')}>Bring a source<BookOpen size={17} /></Button></div></form>
      {error !== null && <ErrorState error={error} onRetry={() => setError(null)} />}{notice && <Notice><p>{notice}</p></Notice>}
      <section className="section"><h2>Continue learning</h2>{home.resume.length ? <div className="home-record-list">{home.resume.map(row => <button key={row.id} onClick={() => navigate('learn', { payload: { thread_id: row.id } })}><MessageCircle size={18} /><span><strong>{row.title}</strong><small>Last opened {new Date(row.updated_at).toLocaleDateString()}</small></span><ChevronRight size={18} /></button>)}</div> : <p>Start a study discussion. Your ordinary learning threads will be ready to resume here.</p>}</section>
      <section className="section"><div className="section-heading"><h2>Your next study</h2><Button variant="ghost" busy={busy} onClick={propose}>Suggest a plan</Button></div>{activities.length ? <div className="study-activities">{activities.map(row => <article key={row.id} className={'study-activity activity-' + row.state}><div className="activity-main"><div className="activity-title"><strong>{row.title}</strong><Badge tone={row.state === 'planned' ? 'default' : 'neutral'}>{row.state === 'planned' ? row.kind === 'mistake-review' ? 'Review' : 'Study' : row.state}</Badge></div><p>{row.reason.description}</p><div className="activity-meta"><label>When <input aria-label={'Move ' + row.title} type="date" value={row.due_date} onChange={event => change(row.id, { due_date: event.target.value })} /></label><span>{row.duration_minutes} min</span>{row.manual_override && <span>Adjusted by you</span>}</div></div><div className="activity-actions">{row.state === 'planned' && <><Button variant="secondary" onClick={() => navigate(row.kind === 'mistake-review' ? 'assessment' : 'learn', { payload: { topic_id: row.topic_id, question_id: row.reason.question_id } })}>Start<ArrowRight size={15} /></Button><Button variant="ghost" onClick={() => change(row.id, { state: 'completed' })}><Check size={15} />Mark done</Button><Button variant="ghost" onClick={() => change(row.id, { state: 'skipped' })}>Skip</Button></>}</div></article>)}</div> : <p>A plan can balance selected topics and your recorded mistakes. Explore freely whenever you prefer.</p>}</section>
      <section className="section"><h2>Explore nephrology</h2>{home.topics.length ? <div className="topic-directory">{home.topics.map(topic => <button key={topic.id} onClick={() => navigate('learn', { payload: { topic_id: topic.id, question: 'Help me study ' + topic.title + '.' } })}>{topic.title}<ArrowRight size={15} /></button>)}</div> : <p>Topic coverage appears when the original learning pack is installed.</p>}</section>
    </div><aside className="today-support">
      <section className="daily-case-entry"><Stethoscope size={23} /><h2>A question from your day?</h2><p>Discuss a daily case in a temporary space, then choose whether to save it.</p><Button variant="ghost" onClick={() => navigate('cases')}>Discuss a case<ArrowRight size={16} /></Button></section>
      {settings && <form className="study-settings section" onSubmit={saveGoals}><h2>Your study preferences</h2><Input label="Hours per week" type="number" min={1} max={40} value={currentGoals.hours_per_week} onChange={event => setGoals({ ...currentGoals, hours_per_week: Number(event.target.value) })} /><Input label="Exam date (optional)" type="date" value={currentGoals.exam_date ?? ''} onChange={event => setGoals({ ...currentGoals, exam_date: event.target.value || null })} /><Select label="Track" value={currentGoals.track} onChange={event => setGoals({ ...currentGoals, track: event.target.value as Goals['track'] })}><option value="general">General nephrology</option><option value="eseneph">ESENeph preparation</option></Select><p className="muted">Track selection sets your study preference. Published pack coverage determines available assessment.</p><fieldset className="topic-preferences"><legend>Topics to emphasise</legend>{home.topics.map(topic => <label key={topic.id}><input type="checkbox" checked={currentGoals.topic_ids.includes(topic.id)} onChange={event => setGoals({ ...currentGoals, topic_ids: event.target.checked ? [...currentGoals.topic_ids, topic.id] : currentGoals.topic_ids.filter(id => id !== topic.id) })} />{topic.title}</label>)}</fieldset><Button type="submit" busy={busy}>Save preferences</Button></form>}
      <section className="section"><h2>Reviewed updates</h2>{home.updates.length ? home.updates.map(item => <button className="home-update" key={item.id} onClick={() => navigate('updates', { payload: { entry_id: item.id } })}><strong>{item.title}</strong><small>Reviewed {item.reviewed_at ? new Date(item.reviewed_at).toLocaleDateString() : 'date unavailable'}</small></button>) : <p>Reviewed changes in guidance and research appear here. New discoveries stay in the review queue.</p>}<Button variant="ghost" onClick={() => navigate('updates')}>Open Updates<ArrowRight size={16} /></Button></section>
      <section className="section"><h2>Observed assessment</h2>{home.progress.groups.fresh.answered ? <p>{home.progress.groups.fresh.correct} correct from {home.progress.groups.fresh.answered} fresh unassisted reviewed answers.</p> : <p>Take a reviewed test to see your results. Conversations do not count as mastery.</p>}<Button variant="secondary" onClick={() => navigate('assessment')}>Open Test<ArrowRight size={16} /></Button></section>
    </aside></div></>;
}
