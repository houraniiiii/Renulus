/** Observe visible native windows, then select the actual loopback Flow renderer. */
export async function waitForFlowWindow(application, { startedAt = Date.now(), timeout = 360_000, requireHeading = true } = {}) {
  const deadline = Date.now() + timeout;
  let firstVisibleWindowSeconds;
  let firstVisibleWindowKind;
  let startupWindowSeen = false;
  while (Date.now() < deadline) {
    const windows = await application.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows().filter(window => !window.isDestroyed()).map(window => ({ visible: window.isVisible(), url: window.webContents.getURL() })));
    const visible = windows.filter(window => window.visible);
    startupWindowSeen ||= visible.some(window => window.url.startsWith('data:'));
    if (firstVisibleWindowSeconds === undefined && visible.length) {
      firstVisibleWindowSeconds = (Date.now() - startedAt) / 1000;
      firstVisibleWindowKind = visible[0].url.startsWith('data:') ? 'startup' : 'renderer';
      console.log(JSON.stringify({ stage: 'first-native-window-visible', firstVisibleWindowSeconds, firstVisibleWindowKind }));
    }
    for (const page of application.windows()) {
      if (page.isClosed()) continue;
      let url;
      try { url = new URL(page.url()); } catch { continue; }
      if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port || !visible.some(window => window.url === page.url())) continue;
      try {
        await page.getByRole('navigation', { name: 'Main navigation', exact: true }).waitFor({ state: 'visible', timeout: 150 });
        if (requireHeading) await page.getByRole('heading', { level: 1 }).first().waitFor({ state: 'visible', timeout: 150 });
      } catch (error) {
        if (page.isClosed() || error.name === 'TimeoutError') continue;
        throw error;
      }
      return { page, firstVisibleWindowSeconds, firstVisibleWindowKind, startupWindowSeen, rendererReadySeconds: (Date.now() - startedAt) / 1000, observationIntervalMs: 100 };
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('The visible loopback Flow renderer did not become ready within the native proof budget.');
}
