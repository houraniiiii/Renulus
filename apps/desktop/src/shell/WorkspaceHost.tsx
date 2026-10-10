import { Suspense, lazy, useCallback, useEffect, useRef, useState, type ComponentType, type ReactNode } from 'react';
import { api, ApiError, isCancelled } from '../platform/api';
import { studyHelpHeaders, type ConversationSummary, type PassageDraft } from '../platform/designC';
import { NotesDraftProvider, NotesPanel } from '../modules/notes';
import { createConversation } from '../modules/chat/api';
import { WorkspacePanel, WorkspaceProvider, useWorkspace, workspaceLayout } from '../modules/workspace';
import { validContext } from '../modules/workspace/state';
import type { WorkspaceAccessDecision, WorkspaceAuthorizer, WorkspaceEntryProps, WorkspacePreferences, WorkspaceReaderProps } from '../modules/workspace';
import TestSetupPane from '../modules/tests/TestSetupPane';
import { Button, ErrorState, LoadingState, Notice } from '../ui';
import { useAssessmentPolicy } from './AssessmentPolicy';
import { useNavigation } from './navigation';
import { useStudyHelp } from './StudyHelp';
import { useWorkspaceTitles } from './workspaceTitles';

const readerImports = import.meta.glob<{ default: ComponentType<WorkspaceReaderProps> }>('../modules/reader/index.tsx');
const readerLoader = readerImports['../modules/reader/index.tsx'];
const Reader = readerLoader ? lazy(readerLoader) : undefined;
function StudyReader(props: WorkspaceReaderProps) {
  const studyHelp = useStudyHelp();
  return Reader ? <Reader {...props} studyHelpContext={studyHelp.context} /> : null;
}

function HydrateWorkspace() {
  const workspace = useWorkspace();
  const restored = useRef(false);
  useEffect(() => {
    if (!workspace.permitted || restored.current) return;
    const controller = new AbortController();
    void api<WorkspacePreferences>('/workspace/preferences', { signal: controller.signal }).then(value => {
      if (!controller.signal.aborted) { workspace.restorePreferences(value); restored.current = true; }
    }).catch(() => { /* The panel remains usable; subsequent policy changes retry. */ });
    return () => controller.abort();
  }, [workspace.permitted]);
  return null;
}

/** The selected saved chat/project owns tabs; reading routes retain that context. */
export function ShellWorkspaceProvider({ children }: { children: ReactNode }) {
  const navigation = useNavigation();
  const { policy } = useAssessmentPolicy();
  const studyHelp = useStudyHelp();
  const authorize: WorkspaceAuthorizer = useCallback((body, signal) => api<WorkspaceAccessDecision>('/workspace/authorize', {
    method: 'POST', body, signal, headers: studyHelpHeaders(studyHelp.context),
  }), [studyHelp.context]);
  const [context, setContext] = useState<import('../modules/workspace').WorkspaceContext | null>(null);
  const [saveError, setSaveError] = useState(false);
  const pending = useRef<WorkspacePreferences | undefined>(undefined);
  const saving = useRef(false);
  const timeout = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {
    const payload = navigation.handoff;
    const next = navigation.route === 'projects' && typeof payload?.project_id === 'string'
      ? { identity: { type: 'project', id: payload.project_id }, retention: 'saved' }
      : navigation.route === 'chat' && payload?.conversation
        ? { identity: payload.conversation, retention: payload.retention } : undefined;
    if (validContext(next)) setContext(next);
    else if (navigation.route === 'newchat' || navigation.route === 'chat') setContext(null);
  }, [navigation.route, navigation.handoff]);
  const persist = useCallback(async () => {
    if (saving.current) return;
    saving.current = true;
    try {
      while (pending.current) {
        const value = pending.current; pending.current = undefined;
        try { await api('/workspace/preferences', { method: 'PUT', body: value }); setSaveError(false); }
        catch { setSaveError(true); }
      }
    } finally { saving.current = false; }
  }, []);
  const preferencesChanged = useCallback((value: WorkspacePreferences) => {
    pending.current = value; clearTimeout(timeout.current);
    timeout.current = setTimeout(() => { void persist(); }, 300);
  }, [persist]);
  useEffect(() => () => clearTimeout(timeout.current), []);
  return <WorkspaceProvider context={context} onContextChange={setContext} authorize={authorize}
    policy={policy ?? { active_test_id: null, revision: 0, assistance_allowed: false }}
    onPreferencesChange={preferencesChanged}>
    <NotesDraftProvider><HydrateWorkspace />{children}</NotesDraftProvider>
    {saveError && <div className="workspace-save-notice" role="status">Workspace references could not be saved. Your open tabs are kept in this window.</div>}
  </WorkspaceProvider>;
}

function WorkspaceEntries({ section, ...props }: WorkspaceEntryProps & { section: 'Files' | 'Sources' | 'Notes' | 'Goals' }) {
  const [result, setResult] = useState<{ items: { id?: string; title: string; status: string; reference?: import('../platform/designC').ContentReference }[]; message?: string }>();
  const [error, setError] = useState<unknown>(null);
  const [retry, setRetry] = useState(0);
  const navigation = useNavigation();
  const studyHelp = useStudyHelp();
  useEffect(() => {
    const controller = new AbortController();
    const abort = () => controller.abort(); props.signal.addEventListener('abort', abort, { once: true });
    setResult(undefined); setError(null);
    const query = new URLSearchParams({ section });
    if (props.context?.retention === 'saved') {
      query.set('context_type', props.context.identity.type); query.set('context_id', props.context.identity.id);
    }
    void api<NonNullable<typeof result>>('/workspace/entries?' + query, { signal: controller.signal, headers: studyHelpHeaders(studyHelp.context) }).then(setResult)
      .catch(failure => { if (!isCancelled(failure)) setError(failure); });
    return () => { controller.abort(); props.signal.removeEventListener('abort', abort); };
  }, [section, props.context?.identity.type, props.context?.identity.id, props.context?.retention, props.signal, retry, studyHelp.context]);
  if (error) return <ErrorState error={error} onRetry={() => setRetry(value => value + 1)} />;
  if (!result) return <LoadingState label={'Loading ' + section.toLowerCase()} />;
  return <div className="workspace-entries"><h3>{section}</h3>
    {result.items.length === 0 && <p>{result.message ?? ('No ' + section.toLowerCase() + ' in this context yet.')}</p>}
    {result.items.map((item, index) => <div className="workspace-entry" key={item.reference?.target.id ?? item.id ?? index}>
      {item.reference ? <Button variant="ghost" onClick={() => props.open(item.reference!)}>{item.title}</Button> : <strong>{item.title}</strong>}
      <span className="muted">{item.status}</span>
    </div>)}
    <Button variant="secondary" onClick={() => navigation.navigate(section === 'Goals' ? 'projects' : 'library', {
      payload: props.context?.identity.type === 'project' ? { project_id: props.context.identity.id } : undefined,
    })}>{section === 'Goals' ? 'Open project' : 'Open Library'}</Button>
  </div>;
}
const Files = (props: WorkspaceEntryProps) => <WorkspaceEntries {...props} section="Files" />;
const Sources = (props: WorkspaceEntryProps) => <WorkspaceEntries {...props} section="Sources" />;
function Notes(props: WorkspaceEntryProps) {
  const help = useStudyHelp();
  const navigation = useNavigation();
  const workspace = useWorkspace();
  const [scope, setScope] = useState<{ projectId?: string }>();
  const [error, setError] = useState<unknown>();
  const createKey = useRef(crypto.randomUUID());
  const identity = props.context?.identity;
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined); setScope(undefined);
    if (!identity || identity.type === 'project') setScope({ projectId: identity?.id });
    else void api<ConversationSummary>('/conversations/' + (identity.type === 'case' ? 'case' : 'learning') + '/' + encodeURIComponent(identity.id),
      { signal: controller.signal, headers: studyHelpHeaders(help.context) }).then(value => { if (!controller.signal.aborted) setScope({ projectId: value.project_id ?? undefined }); })
      .catch(caught => { if (!isCancelled(caught)) setError(caught); });
    return () => controller.abort();
  }, [identity?.type, identity?.id, help.context]);
  if (props.context?.retention === 'temporary') return <Notice>Study notes are saved separately. Open a saved chat or project to create a note.</Notice>;
  if (error) return <ErrorState error={error} title="Note context is unavailable" />;
  if (!scope) return <LoadingState label="Opening note context" />;
  return <NotesPanel key={scope.projectId ?? 'personal'} projectId={scope.projectId} signal={props.signal} studyHelpContext={help.context}
    onOpen={note => props.open(note.reference)} onUse={async passage => {
      const conversation = !identity || identity.type === 'project'
        ? await createConversation({ kind: 'learning', project_id: scope.projectId }, props.signal, createKey.current, help.context) : undefined;
      if (props.signal.aborted) return;
      navigation.navigate('chat', { payload: { ...(navigation.route === 'chat' ? navigation.handoff : {}),
        conversation: conversation?.identity ?? identity, retention: 'saved', studyHelpContext: help.context,
        passageIntent: { ...passage, id: crypto.randomUUID() } } });
      if (workspaceLayout(window.innerWidth - 272, workspace.preferredWidth).mode === 'focused') workspace.close();
    }} />;
}
const Goals = (props: WorkspaceEntryProps) => <WorkspaceEntries {...props} section="Goals" />;

function TestPreview({ reference }: import('../modules/workspace').SavedTestPreviewProps) {
  const workspace = useWorkspace();
  return <TestSetupPane selected={{ version_id: reference.target.id }} onClose={() => workspace.closeTab('saved_test_version:' + reference.target.id)}
    onChanged={() => window.dispatchEvent(new Event('renulus:records-changed'))}
    onVersionSelected={id => workspace.open({ target: { type: 'saved_test_version', id } })} />;
}

export function WorkspaceHost({ contentRef }: { contentRef: React.RefObject<HTMLDivElement | null> }) {
  const workspace = useWorkspace();
  const getTitle = useWorkspaceTitles();
  const navigation = useNavigation();
  const studyHelp = useStudyHelp();
  const passageCreateKey = useRef(crypto.randomUUID());
  const [width, setWidth] = useState(0);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    const toggle = () => workspace.toggle();
    window.addEventListener('renulus:workspace-toggle', toggle);
    return () => window.removeEventListener('renulus:workspace-toggle', toggle);
  }, [workspace.toggle]);
  useEffect(() => {
    const element = contentRef.current;
    if (!element) return;
    const measure = () => setWidth(element.clientWidth);
    measure();
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure);
    observer?.observe(element); window.addEventListener('resize', measure);
    return () => { observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, [contentRef]);
  const focused = workspace.isOpen && workspaceLayout(width, workspace.preferredWidth).mode === 'focused';
  useEffect(() => { contentRef.current?.classList.toggle('workspace-focused', focused); }, [focused, contentRef]);
  async function passageToDraft(passage: PassageDraft) {
    if (!workspace.permitted) return;
    setError(null);
    try {
      const identity = workspace.context?.identity;
      const summary = !identity || identity.type === 'project' ? await createConversation({ kind: 'learning',
        project_id: identity?.type === 'project' ? identity.id : undefined }, undefined, passageCreateKey.current, studyHelp.context) : undefined;
      navigation.navigate('chat', { payload: {
        ...(navigation.route === 'chat' ? navigation.handoff : {}),
        conversation: summary?.identity ?? identity, retention: summary?.retention ?? workspace.context?.retention,
        studyHelpContext: studyHelp.context,
        passageIntent: { ...passage, id: crypto.randomUUID() },
      } });
    } catch (failure) { setError(failure instanceof ApiError ? failure : new Error('The selected passage could not be added. Your reader is kept.')); }
  }
  return <>{error && <Notice><p>{error instanceof Error ? error.message : 'The selected passage could not be added.'}</p></Notice>}
    <Suspense fallback={<LoadingState label="Opening the reader" />}><WorkspacePanel availableWidth={width} Reader={Reader ? StudyReader : undefined}
      SavedTestPreview={TestPreview} getTitle={getTitle} adapters={{ Files, Sources, Notes, Goals }} onPassage={passage => { void passageToDraft(passage); }}
      onReturnToChat={() => document.getElementById('learning-content')?.focus({ preventScroll: true })}
      onResumeTest={attemptId => navigation.navigate('attempts', { payload: { attempt_id: attemptId } })} /></Suspense>
  </>;
}
