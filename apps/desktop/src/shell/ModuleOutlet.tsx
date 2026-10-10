import { Component, Suspense, lazy, type ComponentType, type ReactNode } from 'react';
import { ArrowRight, Stethoscope } from 'lucide-react';
import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from '../ui';
import { ConnectionsPage } from '../platform/ConnectionsPage';
import type { ConversationIdentity } from '../platform/designC';
import { validReference } from '../modules/workspace/state';
import { routes, useNavigation, type RouteId } from './navigation';

const imports = import.meta.glob<{ default: ComponentType<Record<string, unknown>> }>('../modules/*/index.tsx');
const pages = Object.fromEntries(Object.entries(imports).map(([path, load]) => [path, lazy(load)]));

class ModuleBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <ErrorState error={null} title="This view could not open" onRetry={() => this.setState({ failed: false })} /> : this.props.children; }
}

const descriptions: Record<RouteId, string> = {
  newchat: 'Start an explanation, discuss a case or choose practice.',
  chat: 'Your conversation and its saved context.',
  projects: 'Organise conversations, shared documents and study goals.',
  tests: 'Saved tests and immutable versions for Study and Test.',
  attempts: 'Continue your exact saved choices and attempt.',
  more: 'Study planning, learning memory and teaching tools.',
  study: 'Pick up where you left off, or follow a new question.',
  learn: 'Chat and explanations across nephrology, with direct and guided teaching.',
  library: 'Your deliberately imported sources, with editions and cited passages.',
  cases: 'Discuss a question from your day. Save only when you choose.',
  assessment: 'Reviewed assessment and generated practice have separate roles.',
  memory: 'Inspect, revise and remove the learning you retain.',
  updates: 'Changes in your sources, with review and checked dates.',
  connections: 'Choose the subscription Renulus uses for your learning.',
};

function PendingPage() {
  const { route, navigate } = useNavigation();
  if (route === 'study') return <div className="home-flow">
    <PageHeader title="A little learning, every day." description={descriptions.study} />
    <div className="home-flow-grid">
      <section className="section"><h2>What would you like to understand?</h2>
        <div className="home-start"><p>Open Learn to ask a nephrology question, or bring a source to your library.</p><div className="actions"><Button onClick={() => navigate('learn')}>Open Learn<ArrowRight size={17} /></Button><Button variant="ghost" onClick={() => navigate('library')}>Bring a source</Button></div></div>
        <EmptyState title="Your learning starts here"><p>Resume, review and source updates appear here when you have learning records. The home module is awaiting integration.</p></EmptyState>
      </section>
      <aside className="today-aside"><section className="case-entry"><Stethoscope size={22} aria-hidden="true" /><div><h2>A question from your day?</h2><p>Case input stays temporary until explicit Save.</p><Button variant="ghost" onClick={() => navigate('cases')}>Discuss a case<ArrowRight size={16} /></Button></div></section><section className="section"><h2>Set up your learning connection</h2><p>Connection status comes from your local runtime.</p><Button variant="secondary" onClick={() => navigate('connections')}>Open Connections<ArrowRight size={16} /></Button></section></aside>
    </div>
  </div>;
  const label = routes.find(item => item.id === route)!.label;
  return <><PageHeader title={label} description={descriptions[route]} /><EmptyState title={label + ' is awaiting integration'} action={<Button variant="secondary" onClick={() => navigate('connections')}>Check Connections<ArrowRight size={16} /></Button>}><p>This module has not been connected to the desktop yet. No sample records or model responses are shown.</p></EmptyState></>;
}

function MorePage() {
  const { navigate } = useNavigation();
  const destinations = ['study', 'memory', 'cases', 'learn', 'assessment', 'connections'] as const;
  return <><PageHeader title="More" /><div className="secondary-destinations">{destinations.map(id => <button key={id} onClick={() => navigate(id)}><strong>{routes.find(item => item.id === id)?.label}</strong><span>{descriptions[id]}</span><ArrowRight size={18} aria-hidden="true" /></button>)}</div></>;
}

export function ModuleOutlet({ assistanceAllowed }: { assistanceAllowed?: boolean } = {}) {
  const { route, handoff, navigate, consumeIntent, selectConversation } = useNavigation();
  const module = routes.find(item => item.id === route)!.module;
  const Page = pages['../modules/' + module + '/index.tsx'];
  const props: Record<string, unknown> = {};
  if (route === 'chat') {
    props.onConversation = selectConversation;
    const identity = handoff?.conversation as ConversationIdentity | undefined;
    if (identity && ['learn_thread', 'case'].includes(identity.type) && typeof identity.id === 'string') props.identity = identity;
    const send = handoff?.sendIntent as { text?: unknown; request_id?: unknown } | undefined;
    if (send && typeof send.text === 'string' && send.text.length <= 16000 && typeof send.request_id === 'string' && send.request_id.length >= 8) {
      props.sendIntent = send; props.onSendIntentConsumed = (id: string) => consumeIntent('sendIntent', id);
    }
    const passage = handoff?.passageIntent as { id?: unknown; text?: unknown; reference?: unknown; title?: unknown } | undefined;
    if (passage && typeof passage.id === 'string' && typeof passage.text === 'string' && passage.text.length <= 16000 && typeof passage.title === 'string' && validReference(passage.reference)) {
      props.passageIntent = passage; props.onPassageIntentConsumed = (id: string) => consumeIntent('passageIntent', id);
    }
    if (typeof handoff?.prefill === 'string') props.prefill = handoff.prefill;
  }
  if (route === 'projects') {
    props.projectId = typeof handoff?.project_id === 'string' ? handoff.project_id : undefined;
    props.onOpenConversation = (identity: ConversationIdentity) => navigate('chat', { payload: { conversation: identity, retention: 'saved' } });
  }
  if (route === 'attempts') {
    props.attemptId = handoff?.attempt_id; props.versionId = handoff?.version_id;
    props.mode = handoff?.mode; props.timing = handoff?.timing;
  }
  return <ModuleBoundary key={route}><Suspense fallback={<LoadingState />}>
    {Page ? <Page {...props} /> : route === 'connections' ? <ConnectionsPage assistanceAllowed={assistanceAllowed}
      initialSection={handoff?.settings_section === 'preferences' ? 'preferences' : undefined} /> : route === 'more' ? <MorePage /> : <PendingPage />}
  </Suspense></ModuleBoundary>;
}
