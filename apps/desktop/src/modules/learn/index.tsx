import { Button, EmptyState, PageHeader } from '../../ui';
import { useNavigation } from '../../shell/navigation';

/** Entry reserved for the integration-owned Learn implementation. */
export default function Learn() {
  const { navigate } = useNavigation();
  return <><PageHeader title="Learn" description="Chat and explanations across nephrology." /><EmptyState title="Learn is awaiting integration" action={<Button variant="secondary" onClick={() => navigate('connections')}>Open Connections</Button>}><p>The learning API is being connected. No sample answer is shown.</p></EmptyState></>;
}
