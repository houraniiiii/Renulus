import { useEffect } from 'react';
import { api, ApiError } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { ErrorState, LoadingState, Notice } from '../../ui';

interface Queue { running: boolean; cpu_workers: number; active_job: string | null; error_code: string | null; queued: number }
async function loadQueue(signal: AbortSignal) {
  const value = await api<Queue>('/library/queue', { signal });
  if (typeof value.running !== 'boolean' || !Number.isSafeInteger(value.queued) || value.queued < 0 ||
      !Number.isSafeInteger(value.cpu_workers) || value.cpu_workers < 1 ||
      value.active_job !== null && typeof value.active_job !== 'string' ||
      value.error_code !== null && typeof value.error_code !== 'string') {
    throw new ApiError('Document processing returned an incomplete queue status. Refresh to check it again.', 0, 'invalid_queue_status', true);
  }
  return value;
}

export default function QueueStatus() {
  const { resource, retry } = useResource(loadQueue);
  useEffect(() => {
    if (resource.status !== 'ready') return;
    const timer = window.setTimeout(retry, 3000);
    return () => window.clearTimeout(timer);
  }, [resource, retry]);
  if (resource.status === 'loading') return <LoadingState label="Checking document processing queue" />;
  if (resource.status === 'error') return <ErrorState title="Document processing status is unavailable" error={resource.error} onRetry={retry} />;
  const queue = resource.data;
  return <Notice tone={!queue.running || queue.error_code ? 'warning' : 'default'}>
    <p>{queue.queued} import{queue.queued === 1 ? '' : 's'} waiting for processing.{queue.running && queue.active_job ? ' A document is being processed locally.' : queue.running ? ' Document processing is running.' : ' Document processing is paused.'}</p>
    {(!queue.running || queue.error_code) && <p>Restart Renulus to resume document processing, then refresh your documents. Queued imports are retained.</p>}
  </Notice>;
}
