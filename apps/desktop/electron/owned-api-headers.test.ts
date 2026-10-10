import { describe, expect, it } from 'vitest';
import { ownedApiHeaders, type ApiHeaderRequest, type ApiHeaderResult } from './owned-api-headers';

function windowFixture() {
  const state = { windowDestroyed: false, contentsDestroyed: false };
  const contents = {
    mainFrame: { processId: 5, routingId: 7, url: 'http://127.0.0.1:8761/#/chat' },
    get id() { if (state.contentsDestroyed) throw new Error('Object has been destroyed'); return 23; },
    isDestroyed: () => state.contentsDestroyed,
  };
  const owner = {
    get webContents() { if (state.windowDestroyed) throw new Error('Object has been destroyed'); return contents; },
    isDestroyed: () => state.windowDestroyed,
  };
  const handle = ownedApiHeaders(owner, 'synthetic-app-token', 'http://127.0.0.1:8761');
  const request = (webContentsId = 23, overrides: Partial<ApiHeaderRequest> = {}) => {
    const results: ApiHeaderResult[] = [];
    handle({ webContentsId, frame: contents.mainFrame, resourceType: 'xhr', requestHeaders: { Accept: 'application/json', 'x-renulus-token': 'untrusted' }, ...overrides }, value => results.push(value));
    expect(results).toHaveLength(1);
    return results[0];
  };
  return { state, request };
}

describe('owned API request lifecycle', () => {
  it('authenticates the live owned renderer and replaces an untrusted token', () => {
    expect(windowFixture().request()).toEqual({ requestHeaders: { Accept: 'application/json', 'x-renulus-token': 'synthetic-app-token' } });
  });
  it('rejects another renderer without disclosing the app token', () => {
    expect(windowFixture().request(24)).toEqual({ cancel: true });
  });
  it('refuses document frames, detached frames and resource navigations even in the owned renderer', () => {
    const { request } = windowFixture();
    for (const resourceType of ['mainFrame', 'subFrame', 'image', 'script', 'other']) {
      expect(request(23, { resourceType })).toEqual({ cancel: true });
    }
    expect(request(23, { frame: null })).toEqual({ cancel: true });
    expect(request(23, { frame: { processId: 5, routingId: 8, url: 'http://127.0.0.1:8761/' } })).toEqual({ cancel: true });
    expect(request(23, { frame: { processId: 5, routingId: 7, url: 'http://127.0.0.1:8761/api/v1/original' } })).toEqual({ cancel: true });
    expect(request(23, { frame: { processId: 5, routingId: 7, url: 'blob:http://127.0.0.1:8761/document' } })).toEqual({ cancel: true });
  });
  it('cancels a late request after window destruction without reading its native getters', () => {
    const { state, request } = windowFixture();
    state.windowDestroyed = true; state.contentsDestroyed = true;
    expect(request()).toEqual({ cancel: true });
  });
  it('cancels a destroyed renderer while its window still exists', () => {
    const { state, request } = windowFixture(); state.contentsDestroyed = true;
    expect(request()).toEqual({ cancel: true });
  });
});
