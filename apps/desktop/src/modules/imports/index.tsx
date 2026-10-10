import { useNavigation } from '../../shell/navigation';
import { PageHeader } from '../../ui';
import ImportPanel from './ImportPanel';

export default function Imports() {
  const { handoff, navigate } = useNavigation();
  return <div className="import-page"><PageHeader title="Import a test" description="Retain the original, resolve uncertainty and save personal practice." />
    <ImportPanel importId={typeof handoff?.import_id === 'string' ? handoff.import_id : undefined}
      sourceRevisionId={typeof handoff?.source_revision_id === 'string' ? handoff.source_revision_id : undefined}
      onOpenVersion={version => navigate('tests', { payload: { test_id: version.test_id, version_id: version.version_id } })} />
  </div>;
}
export { default as ImportPanel } from './ImportPanel';
export * from './api';
export type * from './types';
