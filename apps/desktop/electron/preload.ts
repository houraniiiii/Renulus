import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('renulus', {
  openAuthorization: (url: string): Promise<void> => ipcRenderer.invoke('renulus:open-authorization', url),
  openSource: (url: string): Promise<void> => ipcRenderer.invoke('renulus:open-source', url),
  version: (): Promise<string> => ipcRenderer.invoke('renulus:version'),
});
