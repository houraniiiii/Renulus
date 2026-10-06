/** Stamp the app token only while the captured renderer still owns its window. */
export interface OwnedApiWindow {
  isDestroyed(): boolean;
  readonly webContents: { readonly id: number; isDestroyed(): boolean };
}

export interface ApiHeaderRequest { webContentsId?: number; requestHeaders: Record<string, string> }
export interface ApiHeaderResult { cancel?: boolean; requestHeaders?: Record<string, string> }

export function ownedApiHeaders(owner: OwnedApiWindow, token: string) {
  const contents = owner.webContents;
  const contentsId = contents.id;
  return (details: ApiHeaderRequest, callback: (result: ApiHeaderResult) => void): void => {
    // Late requests can arrive after close. Native getters on a destroyed owner
    // throw, so retain its ID while alive and refuse the closed window first.
    if (owner.isDestroyed() || contents.isDestroyed() || details.webContentsId !== contentsId) {
      callback({ cancel: true });
      return;
    }
    callback({ requestHeaders: { ...details.requestHeaders, 'x-renulus-token': token } });
  };
}
