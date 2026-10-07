import { useRef, useState, type FormEvent } from 'react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Button, ErrorState, Select, Textarea } from '../../ui';
import { useMemoryRequest } from './requests';
import { kindLabels, type Fact, type FactKind } from './types';

// Intent: a doctor deliberately retains general learning. The text is the focal control.
// Shared Flow paper/teal, Source Sans, quiet borders and the 4px spacing scale preserve the established surface.
export function AddFact({ onAdded, onClose }: { onAdded: (fact: Fact) => void; onClose: () => void }) {
  const [text, setText] = useState('');
  const [kind, setKind] = useState<FactKind>('learning-point');
  const [topic, setTopic] = useState('');
  const attempt = useRef<{ payload: string; key: string } | null>(null);
  const request = useMemoryRequest();
  const { resource: topics, retry: retryTopics } = useResource(signal => api<{ id: string; title: string }[]>('/content/topics', { signal }));

  function save(event: FormEvent) {
    event.preventDefault();
    if (!text.trim() || request.busy) return;
    const body = { text: text.trim(), kind, ...(topic ? { topic_id: topic } : {}), scope: { kind: 'study' as const } };
    const payload = JSON.stringify(body);
    if (attempt.current?.payload !== payload) attempt.current = { payload, key: crypto.randomUUID() };
    void request.run(signal => api<Fact>('/memory/facts', { method: 'POST', signal, body: { ...body, idempotency_key: attempt.current!.key } }), fact => {
      attempt.current = null; onAdded(fact); onClose();
    });
  }

  return <form className="memory-editor memory-add" onSubmit={save} aria-label="Add retained learning">
    <h2>Add learning</h2>
    <Textarea label="Learning to retain" hint="Save a general learning point, preference or goal, up to 2,000 characters. Bring case details through Cases." value={text} onChange={event => setText(event.target.value)} disabled={request.busy} required maxLength={2000} autoFocus autoComplete="off" />
    <div className="memory-editor-fields">
      <Select label="Kind of learning" value={kind} disabled={request.busy} onChange={event => setKind(event.target.value as FactKind)}>
        {Object.entries(kindLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
      </Select>
      <Select label="Topic" value={topic} disabled={request.busy || topics.status !== 'ready'} onChange={event => setTopic(event.target.value)} hint="Optional; leave open for learning across topics.">
        <option value="">{topics.status === 'loading' ? 'Loading topics' : 'Across topics'}</option>
        {topics.status === 'ready' && topics.data.map(value => <option key={value.id} value={value.id}>{value.title}</option>)}
      </Select>
    </div>
    {topics.status === 'error' && <div className="memory-inline-actions"><p className="muted">Topics could not be loaded. You can save without a topic.</p><Button variant="ghost" onClick={retryTopics}>Retry topics</Button></div>}
    {request.error !== null && <ErrorState title="Learning could not be saved" error={request.error} />}
    <div className="actions"><Button type="submit" busy={request.busy} disabled={!text.trim()}>Save learning</Button><Button variant="ghost" disabled={request.busy} onClick={onClose}>Cancel</Button></div>
  </form>;
}
