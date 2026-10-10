/** Only trusted host fetches receive app authority; document frames never do. */
export interface ApiFrame { readonly processId: number; readonly routingId: number; readonly url: string }
export interface OwnedApiWindow {
  isDestroyed(): boolean;
  readonly webContents: { readonly id: number; readonly mainFrame: ApiFrame; isDestroyed(): boolean };
}

export interface ApiHeaderRequest { webContentsId?: number; frame?: ApiFrame | null; resourceType: string; requestHeaders: Record<string, string> }
export interface ApiHeaderResult { cancel?: boolean; requestHeaders?: Record<string, string> }

export function ownedApiHeaders(owner: OwnedApiWindow, token: string, origin: string) {
  const contents = owner.webContents;
  const contentsId = contents.id;
  return (details: ApiHeaderRequest, callback: (result: ApiHeaderResult) => void): void => {
    // Late requests can arrive after close. Native getters on a destroyed owner
    // throw, so retain its ID while alive and refuse the closed window first.
    if (owner.isDestroyed() || contents.isDestroyed() || details.webContentsId !== contentsId) {
      callback({ cancel: true });
      return;
    }
    const host = contents.mainFrame;
    const frame = details.frame;
    let trustedUrl = false;
    try {
      const url = new URL(frame?.url ?? '');
      trustedUrl = url.origin === origin && (url.pathname === '/' || url.pathname === '/index.html');
    } catch { /* A detached, opaque or document frame has no API authority. */ }
    if (details.resourceType !== 'xhr' || !frame || !trustedUrl ||
        frame.processId !== host.processId || frame.routingId !== host.routingId) {
      callback({ cancel: true });
      return;
    }
    callback({ requestHeaders: { ...details.requestHeaders, 'x-renulus-token': token } });
  };
}
