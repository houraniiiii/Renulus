export {};
declare global {
  interface Window {
    renulus?: { openAuthorization(url: string): Promise<void>; version(): Promise<string> };
  }
}
