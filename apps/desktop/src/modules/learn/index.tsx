import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { ArrowLeft, ArrowUp, BookOpen, Plus, Square, Trash2 } from 'lucide-react';
import { api, ApiError, isCancelled } from '../../platform/api';
import { stream } from '../../platform/stream';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, ErrorState, IconButton, LoadingState, Notice, PageHeader, Select, Textarea } from '../../ui';
import './learn.css';

// Flow: the question leads, the reading area stays open, history supports continuation.
// Shared Source Sans, teal, paper, quiet borders and 4px rhythm govern every state.
interface Citation { id?: string; passage_id?: string; document_id?: string; revision_id?: string; document_revision?: string; title?: string; page?: number; page_number?: number; source_id?: string; section?: string; locators?: { page?: number | null }[] }
interface Message { id: string; role: 'user' | 'assistant'; content: string; citations?: Citation[] }
interface Thread { id: string; title: string; topic_id?: string; teaching_style: 'direct' | 'guided'; messages: Message[]; updated_at: string }
interface Topic { id: string; label?: string; title?: string }
interface LiteratureRecord { id: string; title: string; url: string; authors?: string | null; publication_date?: string | null; doi?: string | null; retracted?: boolean | null }
type LiteratureDisclosure = { kind: 'ready'; topic_id: string; topic_label: string; queried_at: string; records: LiteratureRecord[] } | { kind: 'unavailable'; topic_id: string; topic_label: string; message: string };
interface RunEvent { run_id: string; sequence: number; type: string; payload: { text?: string; thread_id?: string; citations?: Citation[]; message?: string; code?: string; replayed?: boolean; count?: number; topic_id?: string; topic_label?: string; queried_at?: string; records?: LiteratureRecord[] } }
type MemoryRecall = { kind: 'recalled'; count: number } | { kind: 'unavailable'; message: string };

function literatureLink(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && ['europepmc.org', 'pubmed.ncbi.nlm.nih.gov'].includes(url.hostname) && !url.username && !url.password && !url.port && !url.search && !url.hash) return url.href;
  } catch { /* Unsupported discovery URLs remain plain titles. */ }
}

export default function Learn() {
  const { scope, handoff, navigate } = useNavigation();
  const temporary = scope.kind === 'temporary-case' || scope.kind === 'unclassified' || scope.kind === 'saved-case';
  const caseId = typeof handoff?.case_id === 'string' ? handoff.case_id : temporary ? scope.entity_id : undefined;
  const [question, setQuestion] = useState(String(handoff?.question ?? handoff?.case_text ?? ''));
  const [topic, setTopic] = useState(String(handoff?.topic_id ?? ''));
  const [style, setStyle] = useState<'direct' | 'guided'>('direct');
  const [thread, setThread] = useState<Thread | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [partial, setPartial] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [status, setStatus] = useState('');
  const [evidenceStatus, setEvidenceStatus] = useState('');
  const [memoryRecall, setMemoryRecall] = useState<MemoryRecall | null>(null);
  const [memoryCaptureMessage, setMemoryCaptureMessage] = useState('');
  const [literature, setLiterature] = useState<LiteratureDisclosure | null>(null);
  const [sourceLinkError, setSourceLinkError] = useState('');
  const abort = useRef<AbortController | null>(null);
  const runId = useRef<string | null>(null);
  const runCompleted = useRef(false);
  const ticketId = useRef(typeof handoff?.case_handoff_id === 'string' ? handoff.case_handoff_id : undefined);
  const { resource: history, retry: reloadHistory } = useResource(signal => api<{ threads: Thread[] }>('/learn/threads', { signal }));
  const { resource: topics } = useResource(signal => api<Topic[]>('/content/topics', { signal }));

  useEffect(() => {
    if (typeof handoff?.thread_id === 'string' && !temporary) void resume(handoff.thread_id);
    return () => { abort.current?.abort(); if (runId.current) void api('/learn/runs/' + runId.current + '/cancel', { method: 'POST' }).catch(() => {}); if (ticketId.current) void api('/cases/handoffs/' + ticketId.current, { method: 'DELETE' }).catch(() => {}); };
  }, []);
  function clearStatuses() { setStatus(''); setEvidenceStatus(''); setMemoryRecall(null); setMemoryCaptureMessage(''); setLiterature(null); setSourceLinkError(''); }
  async function resume(id: string) {
    if (temporary || busy) return;
    setError(null); clearStatuses();
    try { const value = await api<Thread>('/learn/threads/' + encodeURIComponent(id)); setThread(value); setMessages(value.messages); setTopic(value.topic_id ?? ''); setStyle(value.teaching_style); setPartial(''); }
    catch (caught) { setError(caught); }
  }
  function fresh() { setThread(null); setMessages([]); setPartial(''); setError(null); clearStatuses(); }
  async function remove(id: string) {
    try { await api('/learn/threads/' + id, { method: 'DELETE' }); if (thread?.id === id) fresh(); reloadHistory(); }
    catch (caught) { setError(caught); }
  }
  async function ask(event?: FormEvent) {
    event?.preventDefault(); const text = question.trim(); if (!text || busy) return;
    const controller = new AbortController(); abort.current = controller; runId.current = null;
    runCompleted.current = false;
    setBusy(true); setError(null); setPartial(''); clearStatuses(); setQuestion('');
    setMessages(previous => [...previous, { id: crypto.randomUUID(), role: 'user', content: text }]);
    let output = '', sequence = 0, threadId = thread?.id; let references: Citation[] = []; let retrievalFailed = false;
    try {
      let caseHandoffId: string | undefined;
      if (temporary && caseId) {
        if (ticketId.current) await api('/cases/handoffs/' + ticketId.current, { method: 'DELETE', signal: controller.signal });
        ticketId.current = undefined;
        const currentCase = await api<{ revision: number }>('/cases/sessions/' + encodeURIComponent(caseId), { signal: controller.signal });
        const ticket = await api<{ id: string }>('/cases/sessions/' + encodeURIComponent(caseId) + '/handoff', { method: 'POST', signal: controller.signal, body: { revision: currentCase.revision, target: 'explain', question: text } });
        caseHandoffId = ticket.id; ticketId.current = ticket.id;
      }
      for await (const item of stream<RunEvent>('/learn/ask', { method: 'POST', signal: controller.signal, headers: { 'Idempotency-Key': crypto.randomUUID() }, body: { question: text, scope: temporary ? { kind: 'temporary-case', entity_id: caseId ?? scope.entity_id } : { kind: 'study' }, thread_id: temporary ? null : thread?.id, topic_id: topic || null, teaching_style: style, case_handoff_id: caseHandoffId } })) {
        if (controller.signal.aborted || item.data.sequence <= sequence) continue;
        const data = item.data; sequence = data.sequence; runId.current = data.run_id;
        if (data.type === 'started') threadId = data.payload.thread_id ?? threadId;
        if (data.type === 'delta') { output += data.payload.text ?? ''; setPartial(output); }
        if (data.type === 'sources') { references = data.payload.citations ?? []; setEvidenceStatus(references.length ? 'Retrieved evidence' : retrievalFailed ? 'Evidence retrieval unavailable · answer not source-verified' : 'No evidence retrieved · answer not source-verified'); }
        if (data.type === 'retrieval-failed') { retrievalFailed = true; setEvidenceStatus('Evidence retrieval unavailable · answer not source-verified'); }
        if (!temporary && data.payload.topic_id && data.payload.topic_label) {
          if (data.type === 'discovered-literature' && Array.isArray(data.payload.records)) setLiterature({ kind: 'ready', topic_id: data.payload.topic_id, topic_label: data.payload.topic_label, queried_at: data.payload.queried_at ?? '', records: data.payload.records.slice(0, 5) });
          if (data.type === 'literature-discovery-unavailable') setLiterature({ kind: 'unavailable', topic_id: data.payload.topic_id, topic_label: data.payload.topic_label, message: data.payload.message ?? 'Europe PMC topic discovery was unavailable. Try topic discovery in Library.' });
        }
        if (!temporary && data.type === 'memory' && typeof data.payload.count === 'number' && Number.isSafeInteger(data.payload.count) && data.payload.count >= 0) setMemoryRecall({ kind: 'recalled', count: data.payload.count });
        if (!temporary && data.type === 'memory-unavailable') setMemoryRecall({ kind: 'unavailable', message: data.payload.message ?? 'Learner memory could not be recalled for this explanation.' });
        if (!temporary && data.type === 'memory-capture-unavailable') setMemoryCaptureMessage(data.payload.message ?? 'The explanation was saved. Learner memory capture will retry later.');
        if (data.type === 'completed') { runCompleted.current = true; output = data.payload.replayed ? data.payload.text ?? output : output; setMessages(previous => [...previous, { id: data.run_id, role: 'assistant', content: output, citations: references }]); setPartial(''); }
        if (data.type === 'cancelled') setStatus('Stopped · partial explanation not saved');
        if (data.type === 'error') { setError(new ApiError(data.payload.message ?? 'The explanation could not finish.', 0, data.payload.code ?? 'explain_failed', true)); setQuestion(text); }
      }
      if (threadId && !temporary) { const value = await api<Thread>('/learn/threads/' + threadId); setThread(value); setMessages(value.messages); reloadHistory(); }
    } catch (caught) { if (!isCancelled(caught)) { setError(caught); setQuestion(text); } else setStatus(runCompleted.current ? 'Complete' : 'Stopped · partial explanation not saved'); }
    finally { if (abort.current === controller) { setBusy(false); runId.current = null; } }
  }
  async function stop() {
    if (runId.current) { try { const result = await api<{ state: string }>('/learn/runs/' + runId.current + '/cancel', { method: 'POST' }); runCompleted.current = result.state === 'completed'; setStatus(runCompleted.current ? 'Complete' : 'Stopped · partial explanation not saved'); if (runCompleted.current) return; } catch (caught) { setError(caught); } }
    abort.current?.abort();
  }
  function citation(value: Citation) { navigate('library', { payload: { document_id: value.document_id, passage_id: value.passage_id ?? value.id, revision_id: value.revision_id ?? value.document_revision, page: value.page ?? value.page_number ?? value.locators?.find(location => location.page)?.page } }); }
  async function openLiteratureSource(event: MouseEvent<HTMLAnchorElement>, url: string) {
    // Parent supplies the native bridge; this page also works in a browser.
    const bridge = window.renulus as (typeof window.renulus & { openSource?: (url: string) => Promise<void> });
    if (!bridge?.openSource || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); setSourceLinkError('');
    try { await bridge.openSource(url); }
    catch { setSourceLinkError('The source link could not open. Try again or discover this topic in Library.'); }
  }

  return <>
    <PageHeader title={temporary ? 'Explore your case question' : 'What would you like to understand?'} description={temporary ? 'This explanation shares your temporary case context.' : 'Ask freely across nephrology, then explore the explanation and its evidence.'} actions={temporary && caseId ? <Button variant="secondary" disabled={busy} onClick={() => navigate('cases', { scope: { kind: 'temporary-case', entity_id: caseId }, payload: { case_id: caseId } })}><ArrowLeft size={17} />Return to case</Button> : !temporary && <Button variant="secondary" disabled={busy} onClick={fresh}><Plus size={17} />New study</Button>} />
    <div className="learn-layout"><section className="learn-main">
      {!messages.length && <div className="learning-invitation"><p>Start with a question, a mechanism or a decision you would like to reason through.</p><div className="question-starters">{['How should I reason through AKI?', 'Explain kidney transplant rejection.', 'How do dialysis modalities differ?'].map(value => <button key={value} onClick={() => setQuestion(value)}>{value}</button>)}</div></div>}
      <div className="conversation" aria-label="Learning discussion">{messages.map(message => <article key={message.id} className={'learning-message message-' + message.role}><strong className="message-author">{message.role === 'user' ? 'Your question' : 'Renulus'}</strong><div className="prose learning-answer">{message.content}</div>{message.citations?.length ? <div className="citation-row">{message.citations.map((value, index) => <button key={value.id ?? index} onClick={() => citation(value)}><BookOpen size={14} />Source {index + 1}{value.page ?? value.page_number ? ' · p. ' + (value.page ?? value.page_number) : ''}</button>)}</div> : null}</article>)}{partial && <article className="learning-message"><strong className="message-author">Renulus <Badge tone="neutral">{busy ? 'Explaining' : 'Partial'}</Badge></strong><div className="prose learning-answer">{partial}</div></article>}</div>
      {error !== null && <ErrorState error={error} title="The explanation could not finish" onRetry={() => { void ask(); }} />}
      {evidenceStatus && <p className="muted" role="status" aria-label="Scientific evidence"><strong>Scientific evidence:</strong> {evidenceStatus}</p>}
      {!temporary && literature && <section aria-label="Discovered literature" className="learn-literature"><Notice tone={literature.kind === 'unavailable' ? 'warning' : 'default'}>
        <p><strong>Discovered literature · discovery only</strong></p>
        <p>{literature.topic_label}</p>
        {literature.kind === 'unavailable' ? <p>{literature.message}</p> : <>
          <p className="muted">Europe PMC{literature.queried_at && <> · Searched <time dateTime={literature.queried_at}>{literature.queried_at}</time></>}</p>
          {literature.records.length ? <ul className="learn-discovery-records">{literature.records.map(record => {
            const url = literatureLink(record.url);
            return <li key={record.id}>{url ? <a href={url} target="_blank" rel="noopener noreferrer" onClick={event => { void openLiteratureSource(event, url); }}>{record.title}</a> : <strong>{record.title}</strong>}
              <p className="muted">Published {record.publication_date ?? 'date unavailable'}{record.authors && ' · ' + record.authors}</p>
              {record.doi && <p className="muted">DOI: {record.doi}</p>}
              {record.retracted && <Badge tone="warning">Retraction reported</Badge>}
            </li>;
          })}</ul> : <p>No literature records were found for this topic.</p>}
        </>}
        <p>Topic search results do not verify this explanation. Article text, publication status and permissions have not been reviewed here.</p>
        {sourceLinkError && <p role="alert">{sourceLinkError}</p>}
        <Button variant="secondary" disabled={busy} onClick={() => navigate('library', { scope: { kind: 'personal-library' }, payload: { mode: 'discover', topic_id: literature.topic_id } })}>Discover this topic in Library<BookOpen size={16} /></Button>
      </Notice></section>}
      {!temporary && memoryRecall && <section aria-label="Retained learner context"><Notice tone={memoryRecall.kind === 'unavailable' ? 'warning' : 'default'}><p><strong>Retained learner context</strong></p><p>{memoryRecall.kind === 'unavailable' ? memoryRecall.message : memoryRecall.count === 0 ? 'No retained learning was used for this explanation.' : 'Using ' + memoryRecall.count + ' retained learning ' + (memoryRecall.count === 1 ? 'record' : 'records') + ' to personalize this explanation.'}</p><p>Retained learning personalizes study; it does not verify scientific support.</p></Notice></section>}
      {!temporary && memoryCaptureMessage && <section aria-label="Learner memory capture"><Notice tone="warning"><p><strong>Learner memory capture</strong></p><p>{memoryCaptureMessage}</p></Notice></section>}
      {status && <p className="muted" role="status" aria-label="Explanation status">{status}</p>}
      <form className="learning-composer" onSubmit={ask}><Textarea label={messages.length ? 'Your follow-up' : 'Your nephrology question'} value={question} onChange={event => setQuestion(event.target.value)} placeholder="What would you like to understand?" maxLength={16000} disabled={busy} hint={temporary ? 'This discussion remains temporary.' : 'Bring details from daily practice through Cases so they remain temporary.'} /><div className="composer-controls"><div className="composer-selects"><Select label="Teaching style" value={style} disabled={busy} onChange={event => setStyle(event.target.value as 'direct' | 'guided')}><option value="direct">Direct explanation</option><option value="guided">Guided teaching</option></Select><Select label="Topic" value={topic} disabled={busy} onChange={event => setTopic(event.target.value)}><option value="">Explore freely</option>{topics.status === 'ready' && topics.data.map(value => <option key={value.id} value={value.id}>{value.label ?? value.title ?? value.id}</option>)}</Select></div>{busy ? <Button variant="secondary" onClick={stop}><Square size={15} />Stop</Button> : <Button type="submit" disabled={!question.trim()}><ArrowUp size={18} />Ask Renulus</Button>}</div></form>
      <div className="learning-next"><Button variant="ghost" onClick={() => navigate('library')}>Bring a source<BookOpen size={16} /></Button><Button variant="ghost" onClick={() => navigate('cases')}>Discuss a question from your day</Button></div>
    </section><aside className="learn-continuation">{temporary ? <Notice><p>Case scope follows you through Learn and practice. End temporary context to return to ordinary study.</p></Notice> : <><h2>Continue learning</h2>{history.status === 'loading' ? <LoadingState label="Loading study history" /> : history.status === 'error' ? <ErrorState error={history.error} onRetry={reloadHistory} /> : history.data.threads.length ? <div className="thread-list">{history.data.threads.map(value => <div key={value.id} className={'thread-row' + (value.id === thread?.id ? ' selected' : '')}><button disabled={busy} onClick={() => resume(value.id)}><strong>{value.title}</strong><span>{new Date(value.updated_at).toLocaleDateString()}</span></button><IconButton label={'Delete ' + value.title} disabled={busy} onClick={() => remove(value.id)}><Trash2 size={16} /></IconButton></div>)}</div> : <p>Study discussions appear here and resume after restart.</p>}</>}<section className="section"><h2>Your learning connection</h2><p>Choose a subscription and an available model in Connections.</p><Button variant="secondary" onClick={() => navigate('connections')}>Open Connections</Button></section></aside></div>
  </>;
}
