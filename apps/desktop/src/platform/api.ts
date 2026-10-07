/** Same-origin transport. App authentication is inserted outside the renderer. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly retryable = false,
    readonly requestId?: string,
  ) { super(message); this.name = 'ApiError'; }
}

export function isCancelled(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

export interface ApiOptions extends Omit<RequestInit, 'body' | 'credentials' | 'cache' | 'redirect'> {
  body?: unknown;
  timeoutMs?: number;
}

export function apiPath(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//') || /[\#]/.test(path)) {
    throw new ApiError('The request must target the local Renulus API.', 0, 'invalid_path');
  }
  const pathname = path.split('?')[0];
  let decoded: string;
  try { decoded = decodeURIComponent(pathname); } catch {
    throw new ApiError('The request path is invalid.', 0, 'invalid_path');
  }
  if (decoded.split('/').some(segment => segment === '..' || segment === '.') || decoded.includes(String.fromCharCode(92))) {
    throw new ApiError('The request path is invalid.', 0, 'invalid_path');
  }
  if (path.startsWith('/api/')) {
    if (!path.startsWith('/api/v1/')) throw new ApiError('The API version is unsupported.', 0, 'invalid_path');
    return path;
  }
  return '/api/v1' + path;
}

async function responseError(response: Response): Promise<ApiError> {
  let message = response.status === 401
    ? 'The app session has expired. Restart Renulus to reconnect.'
    : response.status === 404
      ? 'This operation is not available in the local runtime yet.'
      : 'Renulus could not complete the request. Try again.';
  let code = 'http_' + response.status;
  let requestId = response.headers.get('x-request-id') ?? undefined;
  let retryable = response.status === 429 || response.status >= 500;
  if (response.headers.get('content-type')?.includes('json')) {
    try {
      const payload = await response.json();
      const detail = payload.error ?? payload.detail ?? payload;
      if (detail && typeof detail === 'object') {
        if (typeof detail.message === 'string') message = detail.message;
        if (typeof detail.code === 'string') code = detail.code;
        if (typeof detail.retryable === 'boolean') retryable = detail.retryable;
        if (typeof detail.request_id === 'string') requestId = detail.request_id;
      }
    } catch { /* Keep a safe recovery message; do not expose an HTML traceback. */ }
  }
  return new ApiError(message, response.status, code, retryable, requestId);
}

export async function apiResponse(path: string, options: ApiOptions = {}): Promise<Response> {
  const url = apiPath(path);
  const { body, timeoutMs = 30_000, signal, headers: inputHeaders, ...init } = options;
  const controller = new AbortController();
  const abort = () => controller.abort(new DOMException('Request cancelled.', 'AbortError'));
  signal?.addEventListener('abort', abort, { once: true });
  if (signal?.aborted) abort();
  let timedOut = false;
  const timer = timeoutMs > 0 ? setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs) : undefined;
  const headers = new Headers(inputHeaders);
  headers.set('Accept', headers.get('Accept') ?? 'application/json');
  // Provider credentials and the app token are never owned by a feature page.
  headers.delete('Authorization');
  headers.delete('x-renulus-token');
  let requestBody: BodyInit | undefined;
  if (body instanceof FormData || body instanceof Blob || body instanceof ArrayBuffer) {
    requestBody = body;
  } else if (body !== undefined) {
    headers.set('Content-Type', 'application/json');
    requestBody = JSON.stringify(body);
  }
  try {
    const response = await fetch(url, {
      ...init, headers, body: requestBody, signal: controller.signal,
      credentials: 'same-origin', cache: 'no-store', redirect: 'error',
    });
    if (!response.ok) throw await responseError(response);
    return response;
  } catch (error) {
    if (signal?.aborted) throw new DOMException('Request cancelled.', 'AbortError');
    if (timedOut) throw new ApiError('The local runtime took too long to respond. Try again.', 0, 'timeout', true);
    if (error instanceof ApiError || isCancelled(error)) throw error;
    throw new ApiError('The local runtime is unavailable. Open Connections to check it, then retry.', 0, 'unavailable', true);
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', abort);
  }
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const response = await apiResponse(path, options);
  if (response.status === 204) return undefined as T;
  if (!response.headers.get('content-type')?.includes('json')) {
    throw new ApiError('The local runtime returned an unexpected response.', response.status, 'invalid_response');
  }
  try { return await response.json() as T; } catch {
    throw new ApiError('The local runtime returned incomplete JSON. Try again.', response.status, 'invalid_response', true);
  }
}
