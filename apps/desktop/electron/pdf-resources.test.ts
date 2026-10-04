import { describe, expect, it } from 'vitest';
import { isBuiltinPdfResource } from './pdf-resources';

describe('bundled Chromium PDF resources', () => {
  it.each([
    'chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html',
    'chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/pdf_embedder.css',
    'chrome://resources/css/text_defaults.css',
    'chrome://resources/js/assert.js',
  ])('permits the installed viewer resource %s', value => {
    expect(isBuiltinPdfResource(value)).toBe(true);
  });

  it.each([
    'chrome-extension://another-extension/index.html',
    'chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai.example/index.html',
    'chrome://resources.example/js/assert.js',
    'chrome://settings/',
    'https://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html',
    'https://resources/js/assert.js',
    'chrome://user@resources/js/assert.js',
    'chrome://resources:8765/js/assert.js',
    'not a URL',
  ])('denies another origin or ambiguous resource %s', value => {
    expect(isBuiltinPdfResource(value)).toBe(false);
  });
});
