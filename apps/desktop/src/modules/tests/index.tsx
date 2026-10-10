import { useEffect, useState, type FormEvent } from 'react';
import { ArrowRight, BookOpen, Plus } from 'lucide-react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { useNavigation } from '../../shell/navigation';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, PageHeader, Select } from '../../ui';
import TestSetupPane from './TestSetupPane';
import { useTestMutation } from './useTestMutation';
import { originLabel, type PublishedTest, type TestOrigin, type TestPage, type TestSelection } from './types';
import './tests.css';

const base = '/assessment/tests';

// Intent: a nephrologist chooses a reusable set after learning; calm, precise, readable.
// Saved title + real question count lead. Origin and quality stay visibly separate.
// Paper/teal tokens, Source Sans and 4px spacing reuse the established medical system.
export default function Tests() {
  const { handoff } = useNavigation();
  const [origin, setOrigin] = useState<TestOrigin | ''>(''), [lifecycle, setLifecycle] = useState('active');
  const [query, setQuery] = useState(''), [search, setSearch] = useState('');
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<TestSelection | null>(null);
  const [creating, setCreating] = useState(false), [title, setTitle] = useState('Reviewed practice'), [count, setCount] = useState('5');
  const [notice, setNotice] = useState('');
  const mutation = useTestMutation();
  const { resource, retry } = useResource(signal => {
    const params = new URLSearchParams({ lifecycle, q: search });
    if (origin) params.set('origin', origin);
    if (cursor) params.set('cursor', cursor);
    return api<TestPage>(base + '?' + params, { signal });
  });
  useEffect(() => { retry(); }, [origin, lifecycle, search, cursor, retry]);
  useEffect(() => {
    // Chat cards pin a version, never the mutable newest version.
    if (typeof handoff?.test_id === 'string') setSelected({ test_id: handoff.test_id,
      version_id: typeof handoff.version_id === 'string' ? handoff.version_id : undefined });
    else if (typeof handoff?.version_id === 'string') setSelected({ version_id: handoff.version_id });
  }, [handoff]);
  function filter(value: string) { setOrigin(value as TestOrigin | ''); setCursor(null); }
  function create(event: FormEvent) {
    event.preventDefault();
    mutation.mutate<PublishedTest>(base + '/reviewed', 'POST', { title, count: Number(count) }, result => {
      setCreating(false); setSelected(result); setNotice('Your reviewed set is saved. Choose how to practise it.'); retry();
    });
  }
  return <div className="saved-tests">
    <PageHeader title="Tests" description="Return to a saved set or choose reviewed questions for your next session."
      actions={<Button onClick={() => setCreating(value => !value)} disabled={mutation.locked}><Plus size={18} aria-hidden="true" />New reviewed test</Button>} />
    {notice && <Notice>{notice}</Notice>}
    {mutation.error !== null && <ErrorState error={mutation.error} title="Your request needs a retry" onRetry={mutation.retry} />}
    {creating && <form className="tests-create panel" onSubmit={create}>
      <h2>Save a reviewed set</h2>
      <p>Select 1–50 eligible questions. The set is saved before an attempt starts.</p>
      <div className="tests-controls"><Input label="Test title" value={title} maxLength={120} required disabled={mutation.locked} onChange={event => setTitle(event.target.value)} />
        <Input label="Questions" type="number" value={count} min={1} max={50} required disabled={mutation.locked} onChange={event => setCount(event.target.value)} /></div>
      <div className="actions"><Button type="submit" busy={mutation.busy} disabled={mutation.locked || !title.trim()}>Save test</Button>
        <Button variant="ghost" disabled={mutation.locked} onClick={() => setCreating(false)}>Cancel</Button></div>
    </form>}
    <div className="tests-controls">
      <form onSubmit={event => { event.preventDefault(); setSearch(query); setCursor(null); }}>
        <Input label="Find a saved test" type="search" value={query} onChange={event => setQuery(event.target.value)} />
        <Button variant="secondary" type="submit">Find</Button>
      </form>
      <Select label="Origin" value={origin} onChange={event => filter(event.target.value)}>
        <option value="">All origins</option>{Object.entries(originLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </Select>
      <Select label="Collection" value={lifecycle} onChange={event => { setLifecycle(event.target.value); setCursor(null); }}>
        <option value="active">Active tests</option><option value="archived">Archived tests</option>
      </Select>
    </div>
    <div className="tests-layout">
      <section aria-label="Saved test collection" className="tests-collection">
        {resource.status === 'loading' && <LoadingState label="Loading saved tests" />}
        {resource.status === 'error' && <ErrorState error={resource.error} onRetry={retry} />}
        {resource.status === 'ready' && <>
          {resource.data.items.length === 0 ? <EmptyState title={search || origin ? 'No tests match these filters' : lifecycle === 'archived' ? 'No archived tests' : 'Your saved sets will appear here'}>
            <p>{search || origin ? 'Try another title or origin.' : 'Save a reviewed set to begin. Generated, imported and nightly sets share this collection when available.'}</p>
          </EmptyState> : <ul className="tests-list">{resource.data.items.map(test => <li key={test.id}>
            <button className="test-row" aria-pressed={selected?.test_id === test.id} onClick={() => setSelected({ test_id: test.id })}>
              <BookOpen size={20} aria-hidden="true" /><span className="test-row-content">
                <strong>{test.title}</strong>
                {test.latest_version && <><span className="test-row-meta">{test.latest_version.item_count} questions · {originLabel[test.latest_version.origin]} · Version {test.latest_version.ordinal}</span>
                  <span className="test-row-topics">{test.latest_version.topic_ids.join(' · ')}</span></>}
              </span><Badge tone={test.latest_version?.status === 'ready' ? 'default' : 'warning'}>{test.latest_version?.status === 'ready' ? 'Ready' : 'Needs review'}</Badge>
              <ArrowRight size={18} aria-hidden="true" />
            </button>
          </li>)}</ul>}
          <div className="tests-pagination"><Button variant="ghost" disabled={!cursor} onClick={() => setCursor(null)}>First page</Button>
            <Button variant="secondary" disabled={!resource.data.next_cursor} onClick={() => setCursor(resource.data.next_cursor)}>More tests</Button></div>
        </>}
      </section>
      {selected && <TestSetupPane key={selected.test_id + ':' + (selected.version_id ?? '')} selected={selected}
        onClose={() => setSelected(null)} onChanged={() => { retry(); setNotice('Your collection is up to date.'); }} />}
    </div>
  </div>;
}
