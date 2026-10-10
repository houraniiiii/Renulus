import { PageHeader } from '../../ui';
import { useNavigation } from '../../shell/navigation';
import GenerationPanel from './GenerationPanel';

/** Parent may embed GenerationPanel in Tests, Home or a typed chat card. */
export default function Generation() {
  const { handoff, navigate } = useNavigation();
  return <div className="generation-page"><PageHeader title="Generate a test" description="Create reusable personal practice and return to validated progress." />
    <GenerationPanel jobId={typeof handoff?.job_id === 'string' ? handoff.job_id : undefined}
      onOpenVersion={version => navigate('tests', { payload: { test_id: version.test_id, version_id: version.version_id } })} />
  </div>;
}
export { default as GenerationPanel } from './GenerationPanel';
export * from './api';
export type * from './types';
