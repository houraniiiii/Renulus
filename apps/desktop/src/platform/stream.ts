import { apiResponse, ApiError, type ApiOptions } from './api';

export interface ServerEvent<T = unknown> { event: string; data: T; id?: string }

/** Fetch-based SSE uses the local transport and supports caller cancellation. */
export async function* stream<T>(path: string, options: ApiOptions = {}): AsyncGenerator<ServerEvent<T>> {
  const response = await apiResponse(path, { ...options, timeoutMs: options.timeoutMs ?? 0, headers: { ...Object.fromEntries(new Headers(options.headers)), Accept: 'text/event-stream' } });
  if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) {
    throw new ApiError('The runtime did not start an event stream.', response.status, 'invalid_stream');
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const abort = () => { void reader.cancel(); };
  options.signal?.addEventListener('abort', abort, { once: true });
  try {
    while (true) {
      options.signal?.throwIfAborted();
      const { value, done } = await reader.read();
      options.signal?.throwIfAborted();
      buffer += decoder.decode(value, { stream: !done });
      let match: RegExpExecArray | null;
      while ((match = /\r?\n\r?\n/.exec(buffer))) {
        const block = buffer.slice(0, match.index);
        buffer = buffer.slice(match.index + match[0].length);
        const data: string[] = [];
        let event = 'message';
        let id: string | undefined;
        for (const line of block.split(/\r?\n/)) {
          if (line.startsWith(':')) continue;
          const separator = line.indexOf(':');
          const field = separator < 0 ? line : line.slice(0, separator);
          const text = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '');
          if (field === 'data') data.push(text);
          if (field === 'event') event = text;
          if (field === 'id' && !text.includes('\0')) id = text;
        }
        if (!data.length) continue;
        let parsed: T;
        try { parsed = JSON.parse(data.join('\n')) as T; } catch {
          throw new ApiError('The runtime sent an invalid event.', 0, 'invalid_event');
        }
        yield { event, data: parsed, id };
      }
      if (buffer.length > 2_000_000) throw new ApiError('The runtime event exceeded the supported size.', 0, 'invalid_event');
      if (done) break;
    }
  } finally {
    options.signal?.removeEventListener('abort', abort);
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
