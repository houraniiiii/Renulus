import { useEffect, useState } from 'react';
import { RefreshCw, Square } from 'lucide-react';
import { api } from '../../platform/api';
import { Badge, Button, ErrorState, LoadingState, Notice } from '../../ui';
import { useMemoryRequest, useMemoryResource } from './requests';
import { readableState, type MemoryJob, type MemoryStatus } from './types';

function JobItem({ job, onChanged }: { job: MemoryJob; onChanged: (job: MemoryJob) => void }) {
  const request = useMemoryRequest();
  return <li className="memory-job"><div className="memory-job-heading"><span className="memory-job-id" title={job.id}>Job {job.id}</span><Badge tone={job.state === 'failed' ? 'error' : job.state === 'queued' || job.state === 'running' ? 'warning' : 'neutral'}>{readableState(job.state)}</Badge></div>
    {job.error_code && <p className="muted">{readableState(job.error_code)}</p>}
    {(job.state === 'queued' || job.state === 'running') && <Button variant="ghost" busy={request.busy} onClick={() => { void request.run(signal => api<MemoryJob>('/memory/jobs/' + encodeURIComponent(job.id) + '/cancel', { method: 'POST', signal }), onChanged); }}><Square size={14} aria-hidden="true" />Cancel job</Button>}
    {request.error !== null && <ErrorState title="Job could not be cancelled" error={request.error} />}
  </li>;
}

// Intent: recovery stays secondary to retained learning. Actual backend state governs every badge and action.
// Flow rail/ink tokens, compact Source Sans metadata and token spacing form one quiet supporting column.
export function IndexStatus({ pendingFacts, refreshRecords, refreshKey }: { pendingFacts: boolean; refreshRecords: () => void; refreshKey: number }) {
  const status = useMemoryResource(signal => api<MemoryStatus>('/memory/status', { signal }));
  const jobs = useMemoryResource(signal => api<{ jobs: MemoryJob[] }>('/memory/jobs', { signal }));
  const request = useMemoryRequest();
  const [action, setAction] = useState<'reindex' | 'retry'>();
  const [notice, setNotice] = useState('');
  const helpersUnavailable = status.data?.index.helper_ready === false;
  const readyForRecall = status.data?.index.ready === true && !helpersUnavailable;
  const activeJobs = jobs.data?.jobs.some(job => job.state === 'queued' || job.state === 'running') ?? false;
  const poll = activeJobs || (pendingFacts && status.data?.index.state !== 'failed' && status.data?.index.helper_ready !== false);
  const refreshStatus = status.refresh;
  const refreshJobs = jobs.refresh;
  useEffect(() => {
    if (refreshKey > 0) { refreshStatus(); refreshJobs(); }
  }, [refreshKey, refreshStatus, refreshJobs]);
  useEffect(() => {
    if (!poll) return;
    const timer = setInterval(() => { refreshStatus(); refreshJobs(); refreshRecords(); }, 5000);
    return () => clearInterval(timer);
  }, [poll, refreshStatus, refreshJobs, refreshRecords]);

  function refresh() { refreshStatus(); refreshJobs(); refreshRecords(); }
  function rebuild() {
    if (request.busy) return;
    setAction('reindex'); setNotice('');
    void request.run(signal => api<{ ready: true; count: number }>('/memory/reindex', { method: 'POST', signal, timeoutMs: 0 }), result => {
      setNotice('Index rebuilt from ' + result.count + ' retained ' + (result.count === 1 ? 'record.' : 'records.')); refresh();
    });
  }
  function retry() {
    if (request.busy) return;
    setAction('retry'); setNotice('');
    void request.run(signal => api<{ processed: number }>('/memory/retry', { method: 'POST', signal, timeoutMs: 0 }), result => {
      setNotice('Retry processed ' + result.processed + ' ' + (result.processed === 1 ? 'job.' : 'jobs.')); refresh();
    });
  }
  function jobChanged(result: MemoryJob) {
    jobs.update(previous => previous ? { jobs: previous.jobs.map(job => job.id === result.id ? result : job) } : undefined);
    setNotice(result.state === 'cancelled' ? 'Job cancelled.' : 'Job is ' + readableState(result.state) + '.');
    refreshStatus(); refreshRecords();
  }

  return <aside className="memory-support" aria-label="Memory index and recovery">
    <section className="memory-status section"><div className="memory-section-heading"><h2>Recall status</h2><Button variant="ghost" disabled={request.busy} onClick={refresh} aria-label="Refresh memory status"><RefreshCw size={16} aria-hidden="true" />Refresh</Button></div>
      {status.error !== null && <ErrorState error={status.error} title="Memory status could not be loaded" onRetry={refreshStatus} />}
      {!status.data && status.loading && <LoadingState label="Checking memory index" />}
      {status.data && <><div className="memory-status-line"><Badge tone={readyForRecall ? 'default' : 'warning'}>{readyForRecall ? 'Ready for recall' : 'Recall unavailable'}</Badge></div>
        {helpersUnavailable ? <p>Local search is unavailable. Your learning is still saved and editable. Retry and rebuild will be available when local search is ready; use Refresh to check again.</p> : !readyForRecall && <p>Recall needs to be rebuilt from retained learning. Retry failed captures if there are any, or rebuild the recall index.</p>}
        <p className="muted">{status.data.pending_jobs} pending {status.data.pending_jobs === 1 ? 'capture' : 'captures'}</p>
        <p>{status.data.automatic_capture ? 'Automatic capture is enabled for eligible learning.' : 'Automatic capture is off. You can retain learning manually.'}</p>
        <details className="memory-jobs"><summary>Recall details</summary><p>{status.data.producer === 'mem0-oss' ? 'Mem0 OSS' : status.data.producer} · {readableState(status.data.index.state)}</p>{status.data.index.message && <p>{status.data.index.message}</p>}{status.data.index.error_code && <p>{readableState(status.data.index.error_code)}</p>}</details>
      </>}
      <p>Retained learning remains editable while the recall index recovers.</p>
      <div className="memory-recovery-actions"><Button variant="secondary" disabled={request.busy || helpersUnavailable} busy={request.busy && action === 'retry'} onClick={retry}>Retry pending jobs</Button><Button variant="ghost" disabled={request.busy || helpersUnavailable} busy={request.busy && action === 'reindex'} onClick={rebuild}>Rebuild recall index</Button></div>
      {request.busy && <p className="muted" role="status">{action === 'reindex' ? 'Rebuilding recall from retained learning…' : 'Retrying pending learning jobs…'}</p>}
      {request.error !== null && <ErrorState error={request.error} title={action === 'reindex' ? 'Index could not be rebuilt' : 'Jobs could not be retried'} />}
      {notice && <Notice><p>{notice}</p></Notice>}
    </section>
    <details className="memory-jobs"><summary>Memory jobs{jobs.data ? ' (' + jobs.data.jobs.length + ')' : ''}</summary>
      {jobs.error !== null && <ErrorState error={jobs.error} title="Jobs could not be loaded" onRetry={refreshJobs} />}
      {!jobs.data && jobs.loading && <LoadingState label="Loading memory jobs" />}
      {jobs.data && (jobs.data.jobs.length ? <ul className="memory-job-list">{jobs.data.jobs.map(job => <JobItem key={job.id} job={job} onChanged={jobChanged} />)}</ul> : <p className="muted">No memory jobs are recorded.</p>)}
    </details>
  </aside>;
}
