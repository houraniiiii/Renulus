import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowUp, BookOpen, Plus, Square, Trash2 } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { stream } from '../../platform/stream';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, IconButton, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import './learn.css';

// Flow: the question leads, the reading area stays open, history supports continuation.
// Shared Source Sans, teal, paper, quiet borders and 4px rhythm govern every state.
interface Citation { id?: string; passage_id?: string; document_id?: string; revision_id?: string; title?: string; page?: number; page_number?: number; source_id?: string; section?: string }
interface Message { id: string; role: 'user' | 'assistant'; content: string; citations?: Citation[] }
interface Thread { id: string; title: string; topic_id?: string; teaching_style: 'direct' | 'guided'; messages: Message[]; updated_at: string }
interface Topic { id: string; title: string }
interface RunEvent { run_id: string; sequence: number; type: string; payload: { text?: string; thread_id?: string; citations?: Citation[]; message?: string; code?: string; replayed?: boolean } }

export default function Learn() {
  const { scope, handoff, navigate } = useNavigation();
  const temporary = scope.kind === 'temporary-case' || scope.kind === 'unclassified' || scope.kind === 'saved-case';
  const [question, setQuestion] = useState(String(handoff?.question ?? handoff?.case_text ?? ''));
  const [topic, setTopic] = useState(String(handoff?.topic_id ?? ''));
  const [style, setStyle] = useState<'direct' | 'guided'>('direct');
  const [thread, setThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [partial, setPartial] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState('');
  const abort = useRef<AbortController | null>(null);
  const runId = useRef<string | null>(null);
  const { resource: history, retry: reloadHistory } = useResource(signal => api<{ threads: Thread[] }>('/learn/threads', { signal }));
  const { resource: topics } = useResource(signal => api<Topic[]>('/content/topics', { signal }));

  useEffect(() => {
    if (typeof handoff?.thread_id === 'string' && !temporary) void resume(handoff.thread_id);
    return () => { abort.current?.abort(); if (runId.current) void api('/learn/runs/' + runId.current + '/cancel', { method: 'POST' }).catch(() => {}); };
  }, []);
  async function resume(id: string) {
    if (temporary || busy) return;
    setError(null);
    try { const value = await api<Thread>('/learn/threads/' + encodeURIComponent(id)); setThread(value); setMessages(value.messages); setTopic(value.topic_id ?? ''); setStyle(value.teaching_style); setPartial(''); setStatus(''); }
    catch (caught) { setError(caught); }
  }
  function fresh() { setThread(null); setMessages([]); setPartial(''); setError(null); setStatus(''); }
  async function remove(id: string) {
    try { await api('/learn/threads/' + id, { method: 'DELETE' }); if (thread?.id === id) fresh(); reloadHistory(); }
    catch (caught) { setError(caught); }
  }
  async function ask(event?: FormEvent) {
    event?.preventDefault(); const text = question.trim(); if (!text || busy) return;
    const controller = new AbortController(); abort.current = controller; runId.current = null;
    setBusy(true); setError(null); setPartial(''); setStatus(''); setQuestion('');
    setMessages(previous => [...previous, { id: crypto.randomUUID(), role: 'user', content: text }]);
    let output = '', sequence = 0, threadId = thread?.id; let references: Citation[] = [];
    try {
      for await (const item of stream<RunEvent>('/learn/ask', { method: 'POST', signal: controller.signal, headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { question: text, scope: temporary ? { kind: 'temporary-case', entity_id: scope.entity_id } : { kind: 'study' }, thread_id: temporary ? null : thread?.id, topic_id: topic || null, teaching_style: style } })) {
        if (controller.signal.aborted || item.data.sequence <= sequence) continue;
        const data = item.data; sequence = data.sequence; runId.current = data.run_id;
        if (data.type === 'started') threadId = data.payload.thread_id ?? threadId;
        if (data.type === 'delta') { output += data.payload.text ?? ''; setPartial(output); }
        if (data.type === 'sources') { references = data.payload.citations ?? []; setStatus(references.length ? 'Retrieved evidence' : 'No evidence retrieved · answer not source-verified'); }
        if (data.type === 'retrieval-failed') setStatus('Evidence retrieval unavailable · answer not source-verified');
        if (data.type === 'completed') { output = data.payload.replayed ? data.payload.text ?? output : output; setMessages(previous => [...previous, { id: data.run_id, role: 'assistant', content: output, citations: references }]); setPartial(''); }
        if (data.type === 'cancelled') setStatus('Stopped · partial explanation not saved');
        if (data.type === 'error') { setError(new ApiError(data.payload.message ?? 'The explanation could not finish.', 0, data.payload.code ?? 'explain_failed', true)); setQuestion(text); }
      }
      if (threadId && !temporary) { const value = await api<Thread>('/learn/threads/' + threadId); setThread(value); setMessages(value.messages); reloadHistory(); }
    } catch (caught) { if (!isCancelled(caught)) { setError(caught); setQuestion(text); } else setStatus('Stopped · partial explanation not saved'); }
    finally { if (abort.current === controller) { setBusy(false); runId.current = null; } }
  }
  async function stop() {
    if (runId.current) { try { const result = await api<{ state: string }>('/learn/runs/' + runId.current + '/cancel', { method: 'POST' }); setStatus(result.state === 'completed' ? 'Complete' : 'Stopped · partial explanation not saved'); } catch (caught) { setError(caught); } }
    abort.current?.abort();
  }
  function citation(value: Citation) { navigate('library', { payload: { document_id: value.document_id, passage_id: value.passage_id ?? value.id, revision_id: value.revision_id, page: value.page ?? value.page_number } }); }

  return <>
    <PageHeader title={temporary ? 'Explore your case question' : 'What would you like to understand?'} description={temporary ? 'This explanation shares your temporary case context.' : 'Ask freely across nephrology, then explore the explanation and its evidence.'} actions={!temporary && <Button variant="secondary" disabled={busy} onClick={fresh}><Plus size={17} />New study</Button>} />
    <div className="learn-layout"><section className="learn-main">
      {!messages.length && <div className="learning-invitation"><p>Start with a question, a mechanism or a decision you would like to reason through.</p><div className="question-starters">{['How should I reason through AKI?', 'Explain kidney transplant rejection.', 'How do dialysis modalities differ?'].map(value => <button key={value} onClick={() => setQuestion(value)}>{value}</button>)}</div></div>}
      <div className="conversation" aria-label="Learning discussion">{messages.map(message => <article key={message.id} className={'learning-message message-' + message.role}><strong className="message-author">{message.role === 'user' ? 'Your question' : 'Renulus'}</strong><div className="prose learning-answer">{message.content}</div>{message.citations?.length ? <div className="citation-row">{message.citations.map((value, index) => <button key={value.id ?? index} onClick={() => citation(value)}><BookOpen size={14} />Source {index + 1}{value.page ?? value.page_number ? ' · p. ' + (value.page ?? value.page_number) : ''}</button>)}</div> : null}</article>)}{partial && <article className="learning-message"><strong className="message-author">Renulus <Badge tone="neutral">{busy ? 'Explaining' : 'Partial'}</Badge></strong><div className="prose learning-answer">{partial}</div></article>}</div>
      {error !== null && <ErrorState error={error} title="The explanation could not finish" onRetry={() => { void ask(); }} />}
      {status && <p className="muted" role="status">{status}</p>}
      <form className="learning-composer" onSubmit={ask}><Textarea label={messages.length ? 'Your follow-up' : 'Your nephrology question'} value={question} onChange={event => setQuestion(event.target.value)} placeholder="What would you like to understand?" maxLength={16000} disabled={busy} hint={temporary ? 'This discussion remains temporary.' : 'Bring details from daily practice through Cases so they remain temporary.'} /><div className="composer-controls"><div className="composer-selects"><Select label="Teaching style" value={style} disabled={busy} onChange={event => setStyle(event.target.value as 'direct' | 'guided')}><option value="direct">Direct explanation</option><option value="guided">Guided teaching</option></Select><Select label="Topic" value={topic} disabled={busy} onChange={event => setTopic(event.target.value)}><option value="">Explore freely</option>{topics.status === 'ready' && topics.data.map(value => <option key={value.id} value={value.id}>{value.title}</option>)}</Select></div>{busy ? <Button variant="secondary" onClick={stop}><Square size={15} />Stop</Button> : <Button type="submit" disabled={!question.trim()}><ArrowUp size={18} />Ask Renulus</Button>}</div></form>
      <div className="learning-next"><Button variant="ghost" onClick={() => navigate('library')}>Bring a source<BookOpen size={16} /></Button><Button variant="ghost" onClick={() => navigate('cases')}>Discuss a question from your day</Button></div>
    </section><aside className="learn-continuation">{temporary ? <Notice><p>Case scope follows you through Learn and practice. End temporary context to return to ordinary study.</p></Notice> : <><h2>Continue learning</h2>{history.status === 'loading' ? <LoadingState label="Loading study history" /> : history.status === 'error' ? <ErrorState error={history.error} onRetry={reloadHistory} /> : history.data.threads.length ? <div className="thread-list">{history.data.threads.map(value => <div key={value.id} className={'thread-row' + (value.id === thread?.id ? ' selected' : '')}><button disabled={busy} onClick={() => resume(value.id)}><strong>{value.title}</strong><span>{new Date(value.updated_at).toLocaleDateString()}</span></button><IconButton label={'Delete ' + value.title} disabled={busy} onClick={() => remove(value.id)}><Trash2 size={16} /></IconButton></div>)}</div> : <p>Study discussions appear here and resume after restart.</p>}</>}<section className="section"><h2>Your learning connection</h2><p>Choose a subscription and an available model in Connections.</p><Button variant="secondary" onClick={() => navigate('connections')}>Open Connections</Button></section></aside></div>
  </>;
}
