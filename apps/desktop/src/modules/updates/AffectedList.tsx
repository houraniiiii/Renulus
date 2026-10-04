import { useState } from 'react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Button, ErrorState } from '../../ui';

interface Affected { kind: string; entity_id: string; version: number; pinned_source_id: string; locators: string[]; state: string }
export default function AffectedList({ entryId }: { entryId: string }) {
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const { resource, retry } = useResource(signal => api<{ affected: Affected[]; total: number; next_offset: number | null }>('/updates/entries/' + encodeURIComponent(entryId) + '/affected?limit=10&offset=' + offset, { signal }));
  if (resource.status === 'loading') return <p className="muted">Checking affected learning versions…</p>;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  if (!resource.data.total) return <p className="muted">No pinned question or case versions are linked to this change yet.</p>;
  return <details className="update-affected" open={expanded} onToggle={event => setExpanded(event.currentTarget.open)}><summary>{resource.data.total} pinned learning {resource.data.total === 1 ? 'version' : 'versions'} linked</summary><p className="muted">Historical keys and results are preserved. These annotations request content re-review.</p><ul>{resource.data.affected.map(row => <li key={row.kind + row.entity_id + row.version + row.pinned_source_id}><strong>{row.kind} {row.entity_id} · v{row.version}</strong><span>{row.state === 'dismissed' ? 'Dismissed after review' : 'Needs re-review'} · {row.pinned_source_id}</span><span>{row.locators.join('; ')}</span></li>)}</ul>{(offset > 0 || resource.data.next_offset !== null) && <div className="actions"><Button variant="ghost" disabled={offset === 0} onClick={() => { setOffset(Math.max(0, offset - 10)); retry(); }}>Previous versions</Button><Button variant="ghost" disabled={resource.data.next_offset === null} onClick={() => { setOffset(resource.data.next_offset ?? offset); retry(); }}>Next versions</Button></div>}</details>;
}
