import assert from 'node:assert/strict';
import test from 'node:test';
import { classifyPdfFrames } from './pdf-viewer-evidence.mjs';
test('a blank Chromium error frame is a failure even with no body text', () => {
  const result = classifyPdfFrames([{ url: 'chrome-error://chromewebdata/', body: '', embeds: [], inputs: [] }]);
  assert.equal(result.blocked, true);
  assert.equal(result.viewerDetected, false);
  assert.equal(result.citationPageSelected, false);
});
test('an empty or ordinary frame cannot stand in for a PDF viewer', () => {
  for (const frames of [[], [{ url: 'blob:http://127.0.0.1:1234/fixture', body: '', embeds: [], inputs: [] }]]) assert.equal(classifyPdfFrames(frames).viewerDetected, false);
});
test('viewer presence and physical page selection are independent', () => {
  const frame = { url: 'chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html', viewers: ['PDF-VIEWER'], inputs: [{ id: 'pageNumber', value: '1' }] };
  assert.equal(classifyPdfFrames([frame]).viewerDetected, true);
  assert.equal(classifyPdfFrames([frame]).citationPageSelected, false);
  frame.inputs[0].value = '2';
  assert.equal(classifyPdfFrames([frame]).citationPageSelected, true);
});
