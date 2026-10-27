// SPDX-License-Identifier: MIT
/** Electron-main leaf: owned ephemeral context, native OpenCode Chromium driver.
 * No owner profile, extension acquisition, alternate browser engine or OS input.
 * Must run in the app-owned helper whose command-line switches are set before ready.
 */
import electron from 'electron';
import { Browser } from '@opencode/plugin-browser/rpc';
import { BrowserProxy } from '@opencode/plugin-browser/proxy';
import { Schema } from 'effect';
import { createBrowserPage } from './native-browser/chromium.mjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export function configureOwnedBrowserProcess() {
  if(electron.app.isReady())throw new Error('browser_process_configuration_late');
  electron.app.commandLine.appendSwitch('disable-quic');
  electron.app.commandLine.appendSwitch('force-webrtc-ip-handling-policy','disable_non_proxied_udp');
  electron.app.commandLine.appendSwitch('disable-features','MediaRouter,WebRtcAllowInputVolumeAdjustment');
  electron.app.commandLine.appendSwitch('disable-background-networking');
}

export async function openOwnedBrowserContext({transport,current,publish=async()=>{},onDeath=async()=>{},maxTabs=8,workspace}) {
  if(!electron.app.commandLine.hasSwitch('disable-quic')||!electron.app.commandLine.hasSwitch('force-webrtc-ip-handling-policy'))throw new Error('browser_proxy_configuration_required');
  await current();
  const identity='renulus-developer-'+crypto.randomUUID(),partition=electron.session.fromPartition(identity,{cache:false});
  const proxy=await BrowserProxy.make(transport);
  let closed=false,focused=null,ref=0,cleanup;
  const pages=new Map(),tasks=new Set(),controllers=new Set();
  const win=new electron.BrowserWindow({show:false,focusable:false,skipTaskbar:true,webPreferences:{partition:identity,nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false}});
  win.setMenu(null);
  partition.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
  partition.setPermissionCheckHandler(()=>false);
  await partition.setProxy({mode:'fixed_servers',proxyRules:proxy.url,proxyBypassRules:'<-loopback>'});
  await partition.closeAllConnections();
  const state=()=>({tabs:[...pages.values()].map(page=>page.state()),focusedTabID:focused});
  const report=()=>{if(!closed)void current().then(()=>publish(state())).catch(()=>close());};
  const network={attach(contents){
    const login=(event,_details,auth,callback)=>{event.preventDefault();
      if(!closed&&auth.isProxy&&auth.host===proxy.host&&auth.port===proxy.port&&auth.scheme==='basic')callback(proxy.credentials.username,proxy.credentials.password);else callback();};
    contents.on('login',login);contents.setWebRTCIPHandlingPolicy('disable_non_proxied_udp');
    contents.on('render-process-gone',()=>{void onDeath().finally(()=>close());});
    return ()=>contents.off('login',login);
  },icon:async()=>undefined};
  const shared={ref:()=>`ref_${++ref}`};
  const embeds={create(view){win.contentView.addChildView(view);return {id:'owned_'+crypto.randomUUID(),on(){},show(){},dispose(){if(!win.isDestroyed())win.contentView.removeChildView(view);}};}};
  function make(initialize=true,popupOptions){
    if(closed||pages.size>=maxTabs)throw new Error('browser_tab_limit');
    const id=Browser.TabID.make('tab_'+crypto.randomUUID());
    const page=createBrowserPage(win,{id,partition:identity,network,initialize,popupOptions,shared,embeds,
      publish:report,fail:()=>{void onDeath().finally(()=>close());},fileRoots:()=>workspace?[workspace]:[],
      popup:options=>make(false,options).contents});
    pages.set(id,page);if(!focused)focused=id;return page;
  }
  async function close(){
    closed=true;for(const abort of controllers)abort.abort();
    if(cleanup)return cleanup;
    cleanup=(async()=>{
      // Withdraw network before native diagnostics/files are awaited.
      await proxy.close();await partition.closeAllConnections();
      const results=await Promise.allSettled([...pages.values()].map(async page=>{
        const dead=page.contents.isDestroyed()?Promise.resolve():new Promise(resolve=>page.contents.once('destroyed',resolve));
        await page.dispose();await dead;
      }));
      await Promise.allSettled([...tasks]);
      if(results.some(r=>r.status==='rejected')){cleanup=undefined;throw new Error('browser_context_cleanup_held');}
      pages.clear();focused=null;await partition.clearStorageData();await partition.clearCache();
      if(!win.isDestroyed())win.destroy();
    })();return cleanup;
  }
  win.on('closed',()=>{if(!closed)void onDeath().finally(()=>close());});
  return {identity,proxy_only:true,quic_disabled:true,webrtc_disabled:true,state,
    async execute(raw,signal){
      if(closed)throw new Error('browser_context_closed');await current();
      const command=Schema.decodeUnknownSync(Browser.Command)(raw),action=command.action;
      const abort=new AbortController();controllers.add(abort);const combined=AbortSignal.any([signal,abort.signal]);
      const task=(async()=>{
        combined.throwIfAborted();let result;
        if(action.type==='tabs.list')result={value:state(),files:[]};
        else if(action.type==='tabs.open'){
          const page=make();await page.ready;
          if(action.focus!==false)focused=page.state().id;
          await page.execute({action:{type:'navigate',tabID:page.state().id,url:action.url??'about:blank'},files:[]},combined);
          result={value:page.state(),files:[]};
        } else if(action.type==='preview'){
          if(!workspace||!path.isAbsolute(workspace))throw new Error('browser_preview_requires_declared_handle');
          const file=path.resolve(workspace,action.path),relative=path.relative(workspace,file);
          if(relative==='..'||relative.startsWith('..'+path.sep)||path.isAbsolute(relative))throw new Error('browser_preview_requires_declared_handle');
          const page=make();await page.ready;await page.execute({action:{type:'navigate',tabID:page.state().id,url:pathToFileURL(file).href},files:[]},combined);
          focused=page.state().id;result={value:{path:action.path},files:[]};
        }
        else {
          const page=pages.get(action.tabID);if(!page)throw new Error('browser_tab_unowned');
          if(action.type==='tabs.focus'){focused=action.tabID;result={value:page.state(),files:[]};}
          else if(action.type==='tabs.close'){await page.dispose();pages.delete(action.tabID);if(focused===action.tabID)focused=pages.keys().next().value??null;result={value:state(),files:[]};}
          else result=await page.execute(command,combined);
        }
        await current();combined.throwIfAborted();await publish(state());return result;
      })();tasks.add(task);
      try{return await task;}finally{tasks.delete(task);controllers.delete(abort);}
    },
    async cancelPending(){for(const abort of controllers)abort.abort();await Promise.allSettled([...tasks]);},
    close,
  };
}
