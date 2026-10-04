import { BrowserWindow, session } from 'electron';

// This pre-runtime surface uses the existing Flow token values without loading
// fonts, scripts or a filesystem URL before the trusted app origin is ready.
const openingPage = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Renulus</title><style>
:root{--paper:#faf9f6;--ink:#243b34;--ink-secondary:#50635c;--renal-teal:#17675f;--rail-selected:#dce9df}
html,body{margin:0;height:100%;background:var(--paper);color:var(--ink);font:16px/1.5 'Segoe UI',sans-serif}
body{display:grid;place-items:center}main{max-width:460px;padding:40px}
.brand{color:var(--renal-teal);font-size:26px;font-weight:600;margin:0 0 32px}
h1{font-size:24px;line-height:1.3;letter-spacing:-.02em;font-weight:600;margin:0 0 16px}
p{margin:0 0 12px;color:var(--ink-secondary)}.hint{font-size:14px;margin-top:24px}
.progress{height:4px;overflow:hidden;background:var(--rail-selected);border-radius:4px;margin:28px 0}
.progress::before{content:'';display:block;width:40%;height:100%;background:var(--renal-teal);animation:opening 1.6s ease-in-out infinite}
@keyframes opening{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}
@media(prefers-reduced-motion:reduce){.progress::before{animation:none;transform:translateX(70%)}}
</style></head><body><main><p class="brand">Renulus</p>
<h1 role="status">Opening your learning space</h1>
<p>The first start can take a few minutes.</p><div class="progress" aria-hidden="true"></div>
<p class="hint">You can close this window to stop.</p></main></body></html>`;

export function createStartupWindow(instance: string, icon: string, signal: AbortSignal): BrowserWindow {
  const isolated = session.fromPartition('renulus-opening-' + instance);
  isolated.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  isolated.setPermissionCheckHandler(() => false);
  isolated.webRequest.onBeforeRequest((details, callback) => callback({ cancel: !details.url.startsWith('data:') }));
  const owner = new BrowserWindow({ title: 'Renulus', width: 700, height: 430, show: false,
    resizable: false, backgroundColor: '#faf9f6', icon, autoHideMenuBar: true,
    webPreferences: { session: isolated, nodeIntegration: false, contextIsolation: true,
      sandbox: true, webSecurity: true, javascript: false, spellcheck: false } });
  owner.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  owner.webContents.on('will-navigate', event => event.preventDefault());
  owner.webContents.on('will-attach-webview', event => event.preventDefault());
  owner.once('ready-to-show', () => { if (!signal.aborted && !owner.isDestroyed()) owner.show(); });
  void owner.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(openingPage)).catch(() => {});
  return owner;
}
