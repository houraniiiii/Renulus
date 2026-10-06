import { describe, expect, it } from 'vitest';
import { ownedApiHeaders, type ApiHeaderResult } from './owned-api-headers';

function windowFixture() {
  const state = { windowDestroyed: false, contentsDestroyed: false };
  const contents = {
    get id() { if (state.contentsDestroyed) throw new Error('Object has been destroyed'); return 23; },
    isDestroyed: () => state.contentsDestroyed,
  };
  const owner = {
    get webContents() { if (state.windowDestroyed) throw new Error('Object has been destroyed'); return contents; },
    isDestroyed: () => state.windowDestroyed,
  };
  const handle = ownedApiHeaders(owner, 'synthetic-app-token');
  const request = (webContentsId = 23) => {
    const results: ApiHeaderResult[] = [];
    handle({ webContentsId, requestHeaders: { Accept: 'application/json', 'x-renulus-token': 'untrusted' } }, value => results.push(value));
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
