import { Component, Suspense, lazy, type ComponentType, type ReactNode } from 'react';
import { ArrowRight, Stethoscope } from 'lucide-react';
import { Button, EmptyState, ErrorState, LoadingState, PageHeader } from '../ui';
import { ConnectionsPage } from '../platform/ConnectionsPage';
import { routes, useNavigation, type RouteId } from './navigation';

const imports = import.meta.glob<{ default: ComponentType }>('../modules/*/index.tsx');
const pages = Object.fromEntries(Object.entries(imports).map(([path, load]) => [path, lazy(load)]));

class ModuleBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <ErrorState error={null} title="This view could not open" onRetry={() => this.setState({ failed: false })} /> : this.props.children; }
}

const descriptions: Record<RouteId, string> = {
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

export function ModuleOutlet() {
  const { route, revision } = useNavigation();
  const Page = pages['../modules/' + route + '/index.tsx'];
  return <ModuleBoundary key={route + '-' + revision}><Suspense fallback={<LoadingState />}>
    {Page ? <Page /> : route === 'connections' ? <ConnectionsPage /> : <PendingPage />}
  </Suspense></ModuleBoundary>;
}
