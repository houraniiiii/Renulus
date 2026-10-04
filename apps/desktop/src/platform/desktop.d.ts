export type BackupSaveResult = { status: 'saved'; fileName: string; bytes: number }
  | { status: 'cancelled' }
  | { status: 'error'; code: string; message: string };
declare global {
  interface Window {
    renulus?: {
      openAuthorization(url: string): Promise<void>;
      openSource?(url: string): Promise<void>;
      version(): Promise<string>;
      saveBackup?(kind: 'zip' | 'json', operationId: string): Promise<BackupSaveResult>;
      cancelBackup?(operationId: string): Promise<void>;
    };
  }
}
