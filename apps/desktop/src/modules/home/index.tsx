import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowUp, BookOpen, ClipboardCheck, Paperclip, Stethoscope } from 'lucide-react';
import { ApiError, isCancelled } from '../../platform/api';
import type { ContextScope } from '../../platform/contracts';
import type { ConversationSummary } from '../../platform/designC';
import { routes, useNavigation } from '../../shell/navigation';
import { Button, Notice } from '../../ui';
import { cancelChatTestRun, createConversation, type ChatTestRun } from '../chat/api';
import { prepareQuickPractice, type QuickPracticeCommand } from './practice';
import { readHome, refreshHome } from './requests';
import type { HomeAdapters, HomeState, SuggestionCategory } from './types';
import './home.css';

const categories = [
  { id: 'explain', label: 'Explain a topic', Icon: BookOpen },
  { id: 'case', label: 'Discuss a case', Icon: Stethoscope },
  { id: 'practice', label: 'Quick practice', Icon: ClipboardCheck },
] as const;
const running = (value: HomeState) => value.job?.state === 'running' || value.job?.state === 'queued';

export default function Home({ adapters = {} }: { adapters?: HomeAdapters }) {
  const navigation = useNavigation();
  const [state, setState] = useState<HomeState>();
  const [text, setText] = useState('');
  const [intent, setIntent] = useState<SuggestionCategory>('explain');
  const [expanded, setExpanded] = useState<SuggestionCategory>();
  const [pending, setPending] = useState<{ prompt: string; category: SuggestionCategory }>();
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [greeting, setGreeting] = useState('Welcome back');
  const greetingChosen = useRef(false);
  const hasDraft = useRef(false);
  const composer = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const sending = useRef(false);
  const stopping = useRef(false);
  const [stopPending, setStopPending] = useState(false);
  const command = useRef<{ text: string; kind: 'learning' | 'case'; request_id: string; creation_key: string; conversation?: ConversationSummary }>(undefined);
  const practice = useRef<QuickPracticeCommand>(undefined);
  const active = useRef<AbortController>(undefined);
  const mounted = useRef(true);
  const [practiceRun, setPracticeRun] = useState<ChatTestRun>();
  const attachment = useRef<{ file: File; text: string; kind: 'learning' | 'case';
    request_id: string; creation_key: string; conversation?: ConversationSummary }>(undefined);
  const [attachmentRetry, setAttachmentRetry] = useState(false);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; active.current?.abort(); }; }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let polls = 0;
    const accept = (value: HomeState) => {
      if (controller.signal.aborted) return;
      setState(value);
      if (!greetingChosen.current) {
        greetingChosen.current = true;
        if (!hasDraft.current) setGreeting(value.preferences.doctor_name ? 'Welcome back, Dr. ' + value.preferences.doctor_name : 'Welcome back');
      }
      if (running(value) && polls++ < 80) timer = setTimeout(() => {
        void readHome(controller.signal).then(accept).catch(handleError);
      }, 1000);
    };
    const handleError = (error: unknown) => {
      if (isCancelled(error) || controller.signal.aborted) return;
      if (error instanceof ApiError && error.code === 'assistance_restricted') {
        setState({ preferences: { doctor_name: null, revision: 1 }, suggestions: null,
          suggestions_date: null, stale: false, job: null, error_code: error.code, assistance_allowed: false });
      } else setMessage('Daily suggestions are unavailable. You can still write a message.');
    };
    void readHome(controller.signal).then(value => {
      accept(value);
      if (value.assistance_allowed && !running(value)) {
        void refreshHome(controller.signal).then(accept).catch(handleError);
      }
    }).catch(handleError);
    return () => { controller.abort(); clearTimeout(timer); };
  }, []);

  function fill(prompt: string, category: SuggestionCategory) {
    setText(prompt); setIntent(category); hasDraft.current = true; setPending(undefined); setMessage('');
    composer.current?.focus();
  }
  function choose(prompt: string, category: SuggestionCategory) {
    if (text.trim()) { setPending({ prompt, category }); return; }
    fill(prompt, category);
  }
  function go(destination: 'chat' | 'attempts', payload: Record<string, unknown>, scope = navigation.scope) {
    const route = routes.find(value => String(value.id) === destination);
    if (!route) throw new ApiError('This destination is not available yet. Your draft is kept.', 0, 'prerequisite_unavailable');
    navigation.navigate(route.id, { scope, payload });
  }
  async function send(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || sending.current || state?.assistance_allowed === false) return;
    const draft = text;
    const kind = intent === 'case' ? 'case' : 'learning';
    sending.current = true; setBusy(true); setMessage('');
    const controller = new AbortController(); active.current = controller;
    try {
      if (intent === 'practice') {
        if (!practice.current || practice.current.text !== draft ||
            ['failed', 'cancelled'].includes(practice.current.run?.state ?? '')) {
          practice.current = { text: draft, request_id: crypto.randomUUID() };
        }
        const result = await (adapters.practice ?? prepareQuickPractice)(practice.current, controller.signal, setPracticeRun);
        if (controller.signal.aborted || !mounted.current) return;
        go('attempts', { attempt_id: result.id, version_id: result.version_id },
          { kind: 'generated-practice', entity_id: result.id });
      } else {
        if (!command.current || command.current.text !== draft || command.current.kind !== kind) {
          command.current = { text: draft, kind, request_id: crypto.randomUUID(), creation_key: crypto.randomUUID() };
        }
        const current = command.current;
        // Home creates only. Chat consumes the volatile intent and owns streaming.
        current.conversation ??= await (adapters.create ?? createConversation)({ kind }, controller.signal, current.creation_key);
        if (controller.signal.aborted || !mounted.current) return;
        const conversation = current.conversation;
        const scope: ContextScope = conversation.kind === 'case'
          ? { kind: conversation.retention === 'temporary' ? 'temporary-case' : 'saved-case', entity_id: conversation.identity.id }
          : { kind: 'study', entity_id: conversation.identity.id };
        go('chat', { conversation: conversation.identity, retention: conversation.retention,
          sendIntent: { text: draft, request_id: current.request_id } }, scope);
      }
      setText(''); hasDraft.current = false; setPending(undefined); command.current = undefined; practice.current = undefined;
    } catch (error) {
      if (mounted.current && !stopping.current) setMessage(isCancelled(error) ? 'Preparation was interrupted. Your draft is kept; retry to check this request.' :
        error instanceof ApiError ? error.message : 'Your message could not be sent. Your draft is kept.');
    } finally {
      if (!stopping.current) { sending.current = false; if (mounted.current) { setBusy(false); setPracticeRun(undefined); } }
    }
  }
  async function stopPractice() {
    const current = practice.current, run = current?.run;
    if (!current || !run || stopping.current) return;
    stopping.current = true; setStopPending(true); setMessage('');
    active.current?.abort();
    try {
      const winner = await cancelChatTestRun(run.run_id);
      current.run = winner;
      if (mounted.current) setMessage(winner.state === 'cancelled' ? 'Quick practice stopped. Your draft is kept.' :
        winner.state === 'published' ? 'The five-question set finished before Stop. Your draft is kept; Send opens its Study attempt.' :
          'The stop could not be confirmed. Your draft is kept; retry to check this request.');
    } catch { if (mounted.current) setMessage('The stop could not be confirmed. Your draft is kept; retry to check this request.'); }
    finally {
      stopping.current = false; sending.current = false;
      if (mounted.current) { setStopPending(false); setBusy(false); setPracticeRun(undefined); }
    }
  }
  async function attach(file?: File) {
    if (sending.current || state?.assistance_allowed === false) return;
    if (file) attachment.current = { file, text, kind: intent === 'case' ? 'case' : 'learning',
      request_id: crypto.randomUUID(), creation_key: crypto.randomUUID() };
    const current = attachment.current;
    if (!current) return;
    // Capture the current draft again on an explicit retry; creation/file receipts stay stable.
    current.text = text;
    sending.current = true; setBusy(true); setMessage(''); setAttachmentRetry(false);
    const controller = new AbortController(); active.current = controller;
    try {
      current.conversation ??= await (adapters.create ?? createConversation)({ kind: current.kind }, controller.signal, current.creation_key);
      if (controller.signal.aborted || !mounted.current) return;
      const conversation = current.conversation;
      const scope: ContextScope = conversation.kind === 'case'
        ? { kind: conversation.retention === 'temporary' ? 'temporary-case' : 'saved-case', entity_id: conversation.identity.id }
        : { kind: 'study', entity_id: conversation.identity.id };
      go('chat', { conversation: conversation.identity, retention: conversation.retention, prefill: current.text,
        attachmentIntent: { file: current.file, request_id: current.request_id } }, scope);
      setText(''); hasDraft.current = false; setPending(undefined); attachment.current = undefined;
    } catch (error) {
      if (mounted.current && !isCancelled(error)) {
        setMessage(error instanceof ApiError ? error.message : 'This attachment could not be opened. Your draft is kept.');
        setAttachmentRetry(true);
      }
    } finally { sending.current = false; if (mounted.current) setBusy(false); }
  }
  const prompts = expanded && state?.suggestions?.[expanded];
  const allowed = state?.assistance_allowed !== false;
  return <section className="home-view" aria-label="New chat">
    <div className="home-opening">
      <h1 className="home-greeting">{greeting}</h1>
      <form className="home-composer" onSubmit={send}>
        <label className="sr-only" htmlFor="home-message">How can I help you today</label>
        <textarea ref={composer} id="home-message" placeholder="How can I help you today"
          value={text} maxLength={16000} disabled={busy || !allowed} rows={2} className="home-message"
          onChange={event => { setText(event.target.value); hasDraft.current = !!event.target.value; }} />
        <div className="home-toolbar">
          <input ref={fileInput} type="file" aria-label="Attach file" hidden disabled={busy || !allowed}
            accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx,.xlsx,.csv,.md,.html,.htm,.xml"
            onChange={event => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; if (file) void attach(file); }} />
          <Button variant="ghost" disabled={busy || !allowed} onClick={() => fileInput.current?.click()}><Paperclip size={20} aria-hidden="true" />Attach</Button>
          <Button type="submit" busy={busy} disabled={!text.trim() || !allowed}><ArrowUp size={20} aria-hidden="true" />Send</Button>
        </div>
      </form>
      <div className="home-actions" aria-label="Daily learning suggestions">
        {categories.map(({ id, label, Icon }) => <Button key={id} variant="secondary"
          className={expanded === id ? 'home-action home-action-selected' : 'home-action'}
          aria-expanded={expanded === id} aria-controls="home-suggestions" disabled={!allowed}
          onClick={() => { setExpanded(current => current === id ? undefined : id); if (!text.trim()) setIntent(id); }}>
          <Icon size={20} aria-hidden="true" />{label}</Button>)}
      </div>
      {expanded && <div id="home-suggestions" className="home-suggestions" role="region"
        aria-label={categories.find(category => category.id === expanded)!.label + ' suggestions'}>
        {prompts?.length === 5 ? prompts.map(prompt => <button type="button" className="home-suggestion" key={prompt}
          onClick={() => choose(prompt, expanded)} disabled={busy || !allowed}>{prompt}</button>) :
          <p role="status">{state && running(state) ? 'Preparing today’s suggestions…' : 'Daily suggestions are unavailable. Write your own message above.'}</p>}
        {state?.suggestions_date && <p className="home-date">{state.stale ? 'Previous suggestions · ' : 'Suggestions · '}
          <time dateTime={state.suggestions_date}>{state.suggestions_date}</time></p>}
      </div>}
      {pending && <div className="home-draft-choice" role="group" aria-label="Keep your draft">
        <p>You already have a draft. Add this suggestion or replace your draft?</p>
        <p className="home-pending-prompt">{pending.prompt}</p>
        <div className="actions">
          <Button variant="secondary" onClick={() => fill(text + '\n\n' + pending.prompt, pending.category)}
            disabled={text.length + pending.prompt.length + 2 > 16000}>Add to draft</Button>
          <Button variant="ghost" onClick={() => fill(pending.prompt, pending.category)}>Replace draft</Button>
          <Button variant="ghost" onClick={() => setPending(undefined)}>Keep draft</Button>
        </div>
      </div>}
      {!allowed && <Notice>Chat and daily suggestions are paused during an active Test.</Notice>}
      {busy && practiceRun && <p className="home-status" role="status">{stopPending ? 'Stopping Quick practice…' : 'Preparing five fictional Study questions…'}
        {['queued', 'running'].includes(practiceRun.state) && <Button variant="ghost" disabled={stopPending} onClick={() => { void stopPractice(); }}>Stop practice</Button>}
      </p>}
      {message && <p className="home-status" role="status">{message}</p>}
      {attachmentRetry && <Button variant="secondary" disabled={busy || !allowed} onClick={() => { void attach(); }}>Retry attachment</Button>}
    </div>
  </section>;
}
