import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Check, RotateCcw, Square } from 'lucide-react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Badge, Button, EmptyState, ErrorState, Input, LoadingState, Notice, Select } from '../../ui';
import { useTestMutation } from '../tests/useTestMutation';
import { generationBase, getGenerationJob, listGenerationJobs } from './api';
import { generationMessage, type GeneratedVersion, type GenerationCancellation, type GenerationIntent, type GenerationJob, type GenerationTopic } from './types';
import './generation.css';

export interface GenerationPanelProps {
  jobId?: string;
  initial?: Partial<GenerationIntent>;
  onJobCreated?: (job: GenerationJob) => void;
  onPublished?: (version: GeneratedVersion) => void;
  onOpenVersion?: (version: GeneratedVersion) => void;
}

// The nephrologist's chosen count leads; progress distinguishes retained work
// from a Ready set. Reuse the medical paper/teal palette and four-pixel rhythm.
export default function GenerationPanel({ jobId, initial, onJobCreated, onPublished, onOpenVersion }: GenerationPanelProps) {
  const [title, setTitle] = useState(initial?.title ?? 'Generated practice');
  const [count, setCount] = useState<5 | 10 | 20>(initial?.count ?? 5);
  const [topic, setTopic] = useState(initial?.topic_id ?? '');
  const [selected, setSelected] = useState(jobId ?? ''), [job, setJob] = useState<GenerationJob | null>(null);
  const [progressError, setProgressError] = useState<unknown>(null), [refresh, setRefresh] = useState(0);
  const [shorter, setShorter] = useState(false);
  const generation = useRef(0), published = useRef(new Set<string>());
  const publication = useRef(onPublished); publication.current = onPublished;
  const mutation = useTestMutation();
  const { resource: jobs, retry: reloadJobs } = useResource(signal => listGenerationJobs(signal));
  const { resource: topics, retry: reloadTopics } = useResource(signal => api<GenerationTopic[]>('/content/topics', { signal }));

  useEffect(() => { if (jobId) { generation.current++; setSelected(jobId); setJob(null); } }, [jobId]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout> | undefined;
    const sequence = ++generation.current;
    async function read() {
      try {
        const value = await getGenerationJob(selected, controller.signal);
        if (controller.signal.aborted || sequence !== generation.current) return;
        setJob(value); setProgressError(null);
        if (value.state === 'running' || value.state === 'queued') timer = setTimeout(() => void read(), 750);
        else reloadJobs();
      } catch (error) { if (!controller.signal.aborted && sequence === generation.current) setProgressError(error); }
    }
    void read();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selected, refresh, reloadJobs]);
  useEffect(() => { setShorter(false); }, [selected, job?.validated_count]);
  useEffect(() => {
    if (job?.result?.available && !published.current.has(job.result.version_id)) {
      published.current.add(job.result.version_id); publication.current?.(job.result);
    }
  }, [job]);

  function received(value: GenerationJob, created = false) {
    generation.current++; setJob(value); setSelected(value.id); setProgressError(null);
    setRefresh(number => number + 1); reloadJobs();
    if (created) onJobCreated?.(value);
  }
  function create(event: FormEvent) {
    event.preventDefault();
    const intent: GenerationIntent = { title, count, topic_id: topic || null,
      inputs: initial?.inputs ?? [], source_refs: initial?.source_refs ?? [] };
    mutation.mutate<GenerationJob>(generationBase + '/jobs', 'POST', intent, value => received(value, true));
  }
  function action(operation: 'retry' | 'cancel' | 'accept-shorter') {
    if (!job) return;
    if (operation === 'cancel') {
      mutation.mutate<GenerationCancellation>(generationBase + '/jobs/' + encodeURIComponent(job.id) + '/cancel', 'POST', {}, receipt => {
        generation.current++; setJob(null); setSelected(receipt.id); setRefresh(number => number + 1); reloadJobs();
      });
      return;
    }
    mutation.mutate<GenerationJob>(generationBase + '/jobs/' + encodeURIComponent(job.id) + '/' + operation,
      'POST', operation === 'accept-shorter' ? { accepted_count: job.validated_count } : {}, received);
  }
  function select(value: GenerationJob) { generation.current++; setSelected(value.id); setJob(value); setProgressError(null); setRefresh(number => number + 1); }
  const active = job?.state === 'running' || job?.state === 'queued';
  return <div className="generation-panel">
    {mutation.error !== null && <ErrorState title="Your command needs a retry" error={mutation.error} onRetry={mutation.retry} />}
    <form className="generation-setup panel" onSubmit={create}>
      <div><h2>Create personal practice</h2><p>Generate original questions with the subscription and model selected in Connections.</p></div>
      <div className="generation-fields">
        <Input label="Test title" value={title} required maxLength={120} disabled={mutation.locked} onChange={event => setTitle(event.target.value)} />
        <Select label="Question count" value={count} disabled={mutation.locked} onChange={event => setCount(Number(event.target.value) as 5 | 10 | 20)}>
          <option value={5}>5 · Quick practice</option><option value={10}>10 questions</option><option value={20}>20 questions</option>
        </Select>
        <Select label="Learning topic" value={topic} disabled={mutation.locked || topics.status !== 'ready'} onChange={event => setTopic(event.target.value)}>
          <option value="">Across nephrology</option>{topics.status === 'ready' && topics.data.map(entry => <option key={entry.id} value={entry.id}>{entry.label}</option>)}
        </Select>
      </div>
      {topics.status === 'error' && <ErrorState title="Topics could not be loaded" error={topics.error} onRetry={reloadTopics} />}
      {!!initial?.source_refs?.length && <p>{initial.source_refs.length} saved Library source{initial.source_refs.length === 1 ? '' : 's'} selected.</p>}
      <div className="actions"><Button type="submit" busy={mutation.busy} disabled={mutation.locked || !title.trim()}>Generate {count} questions</Button>
        <span className="generation-caption">Personal practice · Generation does not start an attempt timer.</span></div>
    </form>
    <div className="generation-layout">
      <section aria-label="Generation history" className="generation-history">
        <div className="generation-heading"><h2>Your generation jobs</h2><Button variant="ghost" onClick={reloadJobs}>Refresh jobs</Button></div>
        {jobs.status === 'loading' && <LoadingState label="Loading generation jobs" />}
        {jobs.status === 'error' && <ErrorState error={jobs.error} onRetry={reloadJobs} />}
        {jobs.status === 'ready' && (jobs.data.items.length === 0 ? <EmptyState title="Your saved progress will appear here">
          <p>Choose a count and topic above. Return here after leaving or restarting the app.</p></EmptyState>
          : <ul className="generation-job-list">{jobs.data.items.map(value => <li key={value.id}><button className="generation-job-row"
            aria-pressed={selected === value.id} disabled={mutation.locked} onClick={() => select(value)}>
            <span><strong>{value.title}</strong><span>{value.validated_count} of {value.requested_count} validated</span></span>
            <Badge tone={value.state === 'published' ? 'default' : 'neutral'}>{value.state === 'published' ? 'Saved' : value.state === 'running' ? 'Generating' : value.state === 'needs_review' ? 'Needs review' : value.state === 'cancelled' ? 'Stopped' : 'Needs attention'}</Badge>
          </button></li>)}</ul>)}
      </section>
      {selected && <section aria-label="Generation progress" className="generation-progress">
        {progressError !== null && <ErrorState title="Progress could not be loaded" error={progressError} onRetry={() => setRefresh(number => number + 1)} />}
        {!job && progressError === null && <LoadingState label="Loading retained progress" />}
        {job && <>
          <div className="generation-heading"><h2>{job.title}</h2><Badge tone={job.state === 'published' ? 'default' : 'neutral'}>{job.state === 'published' ? 'Saved' : active ? 'Generating' : 'Retained draft'}</Badge></div>
          <div className="generation-count" aria-live="polite">{job.state === 'published' ? job.effective_count : job.validated_count}<span>{job.state === 'published' ? 'saved questions' : 'of ' + job.requested_count + ' validated'}</span></div>
          <progress aria-label="Validated questions" value={job.validated_count} max={job.requested_count} />
          <p>{generationMessage(job)}</p>
          <p className="generation-caption">{job.route.provider} · {job.route.model} · {job.calls_used} batch request{job.calls_used === 1 ? '' : 's'}</p>
          {active && <Button variant="secondary" disabled={mutation.locked} onClick={() => action('cancel')}><Square size={16} aria-hidden="true" />Stop generation</Button>}
          {job.can_retry && <Button variant="secondary" disabled={mutation.locked} onClick={() => action('retry')}><RotateCcw size={16} aria-hidden="true" />{job.validated_count === job.requested_count ? 'Retry saving this set' : 'Retry remaining questions'}</Button>}
          {job.can_accept_shorter && <div className="generation-shorter"><Notice tone="warning">This saves {job.validated_count} questions instead of the requested {job.requested_count}.</Notice>
            <label className="generation-check"><input type="checkbox" checked={shorter} disabled={mutation.locked} onChange={event => setShorter(event.target.checked)} />Accept a {job.validated_count}-question set</label>
            <Button disabled={mutation.locked || !shorter} onClick={() => action('accept-shorter')}><Check size={16} aria-hidden="true" />Save these {job.validated_count} questions</Button></div>}
          {job.result && <Button disabled={!job.result.available || !onOpenVersion} onClick={() => { if (job.result) onOpenVersion?.(job.result); }}>Open saved test<ArrowRight size={16} aria-hidden="true" /></Button>}
        </>}
      </section>}
    </div>
  </div>;
}
