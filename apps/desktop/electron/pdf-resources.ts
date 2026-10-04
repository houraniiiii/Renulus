/** Only Chromium's bundled PDF viewer and its bundled UI resources. */
export function isBuiltinPdfResource(value: string): boolean {
  try {
    const url = new URL(value);
    if (url.username || url.password || url.port) return false;
    return (url.protocol === 'chrome-extension:' && url.hostname === 'mhjfbmdgcfjbbpaeojofohoefgiehjai')
      || (url.protocol === 'chrome:' && url.hostname === 'resources');
  } catch { return false; }
}
