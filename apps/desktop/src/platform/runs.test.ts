import { afterEach, describe, expect, it, vi } from 'vitest';
import { runEvents } from './runs';
afterEach(() => vi.unstubAllGlobals());
function mock(events: { run_id: string; sequence: number; type: string; payload: object }[]) {
  const bytes = new TextEncoder().encode(events.map(event => 'data: ' + JSON.stringify(event) + '\n\n').join(''));
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(bytes, { headers: { 'Content-Type': 'text/event-stream' } })));
}
describe('ordered run envelope', () => {
  it('ignores duplicates and unrelated runs and ends at the terminal result', async () => {
    mock([{ run_id: 'a', sequence: 0, type: 'started', payload: {} }, { run_id: 'a', sequence: 0, type: 'delta', payload: { text: 'duplicate' } }, { run_id: 'b', sequence: 9, type: 'delta', payload: { text: 'other-case' } }, { run_id: 'a', sequence: 1, type: 'completed', payload: {} }, { run_id: 'a', sequence: 2, type: 'delta', payload: { text: 'late' } }]);
    const result = []; for await (const event of runEvents('/learn/ask')) result.push(event.type); expect(result).toEqual(['started', 'completed']);
  });
  it('reports an interrupted stream instead of claiming a completed answer', async () => {
    mock([{ run_id: 'a', sequence: 0, type: 'started', payload: {} }]);
    await expect((async () => { for await (const _event of runEvents('/learn/ask')) { /* drain */ } })()).rejects.toMatchObject({ code: 'interrupted_stream', retryable: true });
  });
});
