// SPDX-License-Identifier: MIT
import { useRef, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, Save, Square, Trash2, X } from 'lucide-react';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Textarea } from '../../ui';
import { useNavigation } from '../../shell/navigation';
import { useCases } from './useCases';
import './cases.css';

export default function CasesPage() {
  const navigation = useNavigation();
  const resumeId = typeof navigation.handoff?.case_id === 'string' ? navigation.handoff.case_id :
    navigation.scope.kind === 'temporary-case' ? navigation.scope.entity_id ?? undefined : undefined;
  const cases = useCases(resumeId);
  const [title, setTitle] = useState('Daily case');
  const [text, setText] = useState('');
  const [question, setQuestion] = useState('');
  const [confirmation, setConfirmation] = useState<'delete' | 'close'>('delete');
  const dialog = useRef<HTMLDialogElement>(null);
  const item = cases.session;
  const disabled = !!cases.busy || cases.running;

  function start(event: FormEvent) {
    event.preventDefault();
    void cases.start({ kind: 'daily', title: title.trim() || 'Daily case', text: text.trim() })
      .then(result => { if (result) { setText(''); setTitle('Daily case'); } });
  }
  function send(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) void cases.send(question.trim(), () => setQuestion(''));
  }
  async function explain() {
    const ticket = await cases.handoff(question);
    if (ticket) navigation.navigate('learn', { scope: ticket.scope, payload: { ...ticket } });
  }
  function confirm(action: 'delete' | 'close') {
    if (action === 'close' && !item?.dirty) { void cases.close(); return; }
    setConfirmation(action);
    dialog.current?.showModal();
  }

  return <div className="cases-page">
    <PageHeader title={item?.title ?? 'Discuss a case'}
      description={item ? 'Reason through the case, then choose what to keep.' :
        'Bring a question from your day, or work through an original teaching case.'}
      actions={item && <>
        <Button variant="secondary" disabled={disabled || !item.dirty} busy={cases.busy === 'save'} onClick={() => void cases.save()}>
          <Save size={17} aria-hidden="true" />{item.dirty ? (item.saved ? 'Save changes' : 'Save case') : 'Saved'}
        </Button>
        <Button variant="ghost" disabled={disabled} onClick={() => confirm('close')}><X size={17} aria-hidden="true" />Close case</Button>
        <Button variant="ghost" disabled={!!cases.busy} onClick={() => confirm('delete')}><Trash2 size={17} aria-hidden="true" />Delete</Button>
      </>} />

    {!!cases.error && <ErrorState title="The case action could not finish" error={cases.error} />}
    {cases.purgePending && <Notice tone="warning"><p>The case is deleted. Renulus is finishing removal of an older saved copy once the current operation ends.</p>
      <Button variant="ghost" onClick={() => void cases.retryPurge()}>Retry cleanup</Button></Notice>}

    <div className="cases-workspace">
      <main className="cases-main">
        <Notice><p>{item?.saved ? (item.dirty ? 'Saved snapshot · You have temporary changes. Save again to keep them.' :
          'Saved snapshot · Further discussion stays temporary until you save again.') :
          'Temporary case · Text and discussion stay in this app session until you choose Save.'}</p></Notice>

        {cases.busy === 'open' && !item ? <LoadingState label="Reopening the current case" /> : !item ? <form className="case-start section" onSubmit={start}>
          <Input label="Case title" value={title} onChange={event => setTitle(event.target.value)} maxLength={120} disabled={!!cases.busy} />
          <Textarea label="What would you like to discuss?" value={text} rows={8} maxLength={50000}
            onChange={event => setText(event.target.value)} disabled={!!cases.busy} required
            placeholder="Describe the situation, relevant findings and your learning question." />
          <div className="actions"><Button type="submit" busy={cases.busy === 'start'}
            disabled={!text.trim() || !cases.capabilities?.inputs.text.supported}>Start temporary case<ArrowRight size={17} aria-hidden="true" /></Button></div>
          <p className="muted">Text input is available. Images and PDFs cannot be added to this temporary session yet.</p>
        </form> : <>
          <div className="case-context">
            <div className="case-context-meta"><Badge tone={item.dirty ? 'warning' : 'default'}>
              {item.dirty ? 'Temporary' : 'Saved snapshot'}</Badge>
              {item.teaching && <span className="muted">Original synthetic teaching case · Version {item.teaching.version}</span>}
            </div>
            {item.teaching ? <section className="case-teaching" aria-label="Teaching case stages">
              {item.teaching.stages.map((stage, index) => <article className="case-stage" key={stage.id}>
                <h2>Stage {index + 1} of {item.teaching!.stage_count}</h2>
                <p className="case-text prose">{stage.narrative}</p>
                <ul className="case-prompts">{stage.prompts.map(prompt => <li key={prompt}>{prompt}</li>)}</ul>
                {stage.teaching_points && <details className="case-debrief"><summary>Teaching points and sources</summary>
                  <ul>{stage.teaching_points.map(point => <li key={point}>{point}</li>)}</ul>
                  {stage.sources?.map(source => <p className="muted" key={source.source_id + source.locator}>{source.source_id} · {source.locator}</p>)}
                </details>}
              </article>)}
              {item.teaching.take_home && <section className="section"><h2>Take-home learning</h2><ul>{item.teaching.take_home.map(point => <li key={point}>{point}</li>)}</ul></section>}
              {!item.teaching.debriefed && <Button variant="secondary" disabled={disabled} busy={cases.busy === 'reveal'} onClick={() => void cases.reveal()}>
                {item.teaching.revealed_count < item.teaching.stage_count ? 'Reveal next stage' : 'Reveal debrief'}<ArrowRight size={17} aria-hidden="true" /></Button>}
            </section> : <details className="case-details" open><summary>Case details</summary><p className="case-text prose">{item.text}</p></details>}
          </div>
          <section className="case-discussion" aria-label="Case discussion">
            {item.messages.map(message => <article className={'case-message case-message-' + message.role} key={message.id}>
              <h3>{message.role === 'user' ? 'Your question' : 'Discussion'}</h3><p className="case-text prose">{message.content}</p>
            </article>)}
            {cases.pendingQuestion && <article className="case-message"><h3>Your question</h3><p className="case-text prose">{cases.pendingQuestion}</p></article>}
            {cases.running && <article className="case-message"><h3>Discussion</h3><p className="case-text prose">{cases.partial || 'Waiting for the selected model…'}</p></article>}
            <span className="sr-only" role="status" aria-live="polite">{cases.running ? 'Case response is in progress' : 'Case response is idle'}</span>
          </section>
          {!cases.capabilities?.discussion.adapter_installed && <Notice><p>Connect your selected subscription to discuss this case.</p>
            <Button variant="ghost" onClick={() => navigation.navigate('connections')}>Open Connections<ArrowRight size={16} aria-hidden="true" /></Button></Notice>}
          <form className="case-composer section" onSubmit={send}>
            <Textarea label="Your learning question" value={question} rows={3} maxLength={12000}
              onChange={event => setQuestion(event.target.value)} disabled={disabled} required placeholder="What would you like to understand?" />
            <div className="actions">{cases.running ? <Button variant="secondary" onClick={() => void cases.stop()}><Square size={15} aria-hidden="true" />Stop response</Button> :
              <><Button type="submit" disabled={disabled || !question.trim() || !cases.capabilities?.discussion.adapter_installed}>Discuss<ArrowRight size={17} aria-hidden="true" /></Button>
                <Button variant="ghost" disabled={disabled || !question.trim() || !cases.capabilities?.handoffs.explain}
                  busy={cases.busy === 'handoff'} onClick={() => void explain()}>Explore in Learn<ArrowRight size={17} aria-hidden="true" /></Button></>}</div>
            <p className="muted">Learn keeps this case temporary. Return here to choose Save.</p>
          </form>
        </>}
      </main>

      <aside className="case-catalogue" aria-label="Teaching and saved cases">
        {cases.loading && !cases.capabilities ? <LoadingState label="Loading case options" /> : <>
          {!!cases.catalogueError && <ErrorState error={cases.catalogueError} title="Case options could not load" onRetry={() => void cases.reload()} />}
          <section className="section"><h2><BookOpen size={20} aria-hidden="true" />Teaching cases</h2>
            <p className="muted">Reveal the case one stage at a time.</p>
            {cases.teaching.length ? <ul className="case-list">{cases.teaching.map(teaching => <li key={teaching.id}>
              <button disabled={!!item || !!cases.busy} onClick={() => void cases.start({ kind: 'teaching', teaching_case_id: teaching.id })}>
                <strong>{teaching.title}</strong><span>{teaching.topic_id.replaceAll('-', ' ')} · v{teaching.version}</span>
              </button></li>)}</ul> : <p className="muted">Teaching cases appear when an original content pack is installed.</p>}
          </section>
          <section className="section"><h2>Saved cases</h2>
            {cases.saved.length ? <ul className="case-list">{cases.saved.map(saved => <li key={saved.id}>
              <button disabled={!!item || !!cases.busy} onClick={() => void cases.open(saved.id)}><strong>{saved.title}</strong><span>
                Saved {new Date(saved.saved_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
              </span></button></li>)}</ul> : <EmptyState title="No saved cases"><p>Cases you explicitly save appear here.</p></EmptyState>}
            {item && <p className="muted">Close the current case to open another.</p>}
          </section>
        </>}
      </aside>
    </div>

    <dialog ref={dialog} className="case-confirm" aria-labelledby="case-confirm-title">
      <h2 id="case-confirm-title">{confirmation === 'delete' ? 'Delete this case?' : 'Discard temporary changes?'}</h2>
      <p>{confirmation === 'delete' ? 'This removes the case and its saved discussion from Renulus. You cannot reopen it.' :
        item?.saved ? 'The last saved snapshot remains available. Changes since that Save will be discarded.' :
          'This case has not been saved. Closing it discards its text and discussion.'}</p>
      <div className="actions"><Button variant="secondary" onClick={() => dialog.current?.close()}>Keep case open</Button>
        <Button variant="danger" onClick={() => { dialog.current?.close(); void (confirmation === 'delete' ? cases.remove() : cases.close()); }}>
          {confirmation === 'delete' ? 'Delete case' : 'Discard and close'}</Button></div>
    </dialog>
  </div>;
}
