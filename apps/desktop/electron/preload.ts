import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('renulus', {
  openAuthorization: (url: string): Promise<void> => ipcRenderer.invoke('renulus:open-authorization', url),
  openSource: (url: string): Promise<void> => ipcRenderer.invoke('renulus:open-source', url),
  version: (): Promise<string> => ipcRenderer.invoke('renulus:version'),
  saveBackup: (kind: 'zip' | 'json', operationId: string) => ipcRenderer.invoke('renulus:save-backup', kind, operationId),
  cancelBackup: (operationId: string): Promise<void> => ipcRenderer.invoke('renulus:cancel-backup', operationId),
});
