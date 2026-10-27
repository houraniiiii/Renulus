// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import type { BrowserAttachment, CapabilityEnvelope, CapabilityGrant, CapabilityLease, CapabilityStorage, CapabilityTransport, HttpPlan, HttpStream } from './contracts.ts';
import { canonical } from '../../storage/schema.ts';
import { reject } from '../../storage/contracts.ts';

type Owned = { lease: CapabilityLease; abort: AbortController; resources: Set<() => Promise<void>>; tasks: Set<Promise<unknown>>;
  closed: boolean; cleanup?: Promise<void>; timer: ReturnType<typeof setTimeout> };
export interface CapabilityAuthorityOptions {
  storage: CapabilityStorage;
  current(envelope: Readonly<CapabilityEnvelope>, action: string): Promise<CapabilityGrant>;
  transport: CapabilityTransport;
}
/** Admission/settlement adapter only. Native OpenCode continues to own execution and jobs. */
export function createCapabilityAuthority(options: CapabilityAuthorityOptions) {
  const owned = new Map<string, Owned>(); let closing = false;
  const sha = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
  async function credit(item: Owned, bytes = 0) {
    if (closing || item.closed || item.abort.signal.aborted) reject('capability_stale');
    await options.current(item.lease.envelope, item.lease.action);
    item.lease = await options.storage.execute({ type:'capability.current',id:item.lease.id,envelope:item.lease.envelope,bytes,now_ms:Date.now() });
    if (closing || item.closed || item.abort.signal.aborted) reject('capability_stale');
  }
  async function settle(item: Owned, uncertain = false) {
    item.closed = true; item.abort.abort(); clearTimeout(item.timer);
    if (item.cleanup) return item.cleanup;
    item.cleanup = (async () => {
      const results = await Promise.allSettled([...item.resources].map(close=>close()));
      await Promise.allSettled([...item.tasks]);
      if(results.some(r=>r.status==='rejected')) { item.cleanup=undefined; reject('capability_cleanup_held'); }
      await options.storage.execute({type:'capability.settle',id:item.lease.id,outcome:uncertain?'uncertain':'settled',effect_reference:uncertain?item.lease.id:null});
      owned.delete(item.lease.id);
    })();
    return item.cleanup;
  }
  async function admit(envelope: CapabilityEnvelope,action:string,input:unknown): Promise<Owned> {
    if(closing || owned.size>=64) reject('capability_closed');
    const frozen=structuredClone(envelope), grant=structuredClone(await options.current(frozen,action));
    const lease=await options.storage.execute({type:'capability.admit',id:'cap_'+randomUUID(),envelope:frozen,action,payload_sha256:sha(canonical(input)),grant});
    const item:Owned={lease,abort:new AbortController(),resources:new Set(),tasks:new Set(),closed:false,timer:undefined!};
    owned.set(lease.id,item);
    item.timer=setTimeout(()=>{ void options.storage.execute({type:'capability.close',root_id:lease.envelope.root_id})
      .then(()=>settle(item,true)).catch(()=>{}); },Math.max(1,lease.grant.expires_at_ms-Date.now())); item.timer.unref();
    try { await credit(item); return item; } catch(error) { await settle(item); throw error; }
  }
  function endpoint(item:Owned,url:URL) {
    if(!['https:','http:'].includes(url.protocol)||url.username||url.password||url.hash || !item.lease.grant.endpoints.some(e=>e.host===url.hostname && e.port===Number(url.port|| (url.protocol==='https:'?443:80)))) reject('capability_endpoint_denied');
  }
  async function http(item:Owned,input:string|URL,init:RequestInit={},credential?:{ref:string;revision:number}):Promise<Response> {
    if(init.redirect && init.redirect!=='manual') reject('capability_redirect_policy');
    const method=(init.method??'GET').toUpperCase();
    if(!['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'].includes(method)) reject('capability_method_denied');
    if(init.body!==undefined && init.body!==null && typeof init.body!=='string' && !(init.body instanceof Uint8Array)) reject('capability_body_invalid');
    let body=Buffer.from(init.body as string|Uint8Array??'');
    const headers=Object.fromEntries(new Headers(init.headers));
    for(const name of Object.keys(headers)) if(!['accept','content-type','mcp-session-id','mcp-protocol-version','last-event-id'].includes(name)) reject('capability_header_denied');
    let url=new URL(String(input));
    for(let hop=0;hop<5;hop++) {
      endpoint(item,url); await credit(item,body.length);
      const plan:HttpPlan={lease:item.lease,lease_id:item.lease.id,url:url.href,method,headers,body_base64:body.toString('base64'),body_sha256:sha(body),
        max_response_bytes:Math.min(1024*1024,item.lease.grant.max_bytes-item.lease.used_bytes),
        ...(credential?{credential_ref:credential.ref,credential_revision:credential.revision}:{})};
      const stream=await options.transport.http(plan,AbortSignal.any([item.abort.signal,...init.signal?[init.signal]:[]]));
      const close=()=>stream.close(); item.resources.add(close);
      try {
        await credit(item);
        if([301,302,303,307,308].includes(stream.status)) {
          const location=stream.headers.location; if(!location||credential) reject('capability_redirect_denied');
          await close(); item.resources.delete(close); url=new URL(location,url); if(method!=='GET'&&method!=='HEAD') reject('capability_redirect_denied'); continue;
        }
        let bytes=0, ended=false;
        const reader=new ReadableStream<Uint8Array>({
          async pull(controller) {
            try { await credit(item); const chunk=await stream.read(item.abort.signal); await credit(item,chunk?.length??0);
              if(chunk===null) {ended=true; await close(); item.resources.delete(close); controller.close();}
              else {bytes+=chunk.length; if(bytes>plan.max_response_bytes) reject('capability_response_limit'); controller.enqueue(chunk);}
            } catch(error) {controller.error(error); await close(); item.resources.delete(close);}
          }, async cancel(){await close();item.resources.delete(close);},
        },{highWaterMark:0});
        const response=new Response([204,205,304].includes(stream.status)||method==='HEAD'?null:reader,{status:stream.status,headers:stream.headers});
        if(response.body===null&&!ended) {await close(); item.resources.delete(close);}
        return response;
      } catch(error) { await close();item.resources.delete(close);throw error; }
    }
    reject('capability_redirect_limit');
  }
  function track<T>(item:Owned,task:Promise<T>):Promise<T> {item.tasks.add(task);void task.finally(()=>item.tasks.delete(task)).catch(()=>{});return task;}
  return {
    async invoke<T>(envelope:CapabilityEnvelope,action:string,input:unknown,run:(lease:CapabilityLease,signal:AbortSignal)=>Promise<T>):Promise<T> {
      const item=await admit(envelope,action,input);let effect=false;
      try {effect=true; const result=await track(item,run(item.lease,item.abort.signal));await credit(item); await settle(item);return result;}
      catch(error){await settle(item,effect);throw error;}
    },
    async fetch(envelope:CapabilityEnvelope,input:string,init:RequestInit={}) {
      const item=await admit(envelope,'developer.http',{url:input,method:init.method??'GET',body_sha256:sha(typeof init.body==='string'?init.body:'')});
      try {const result=await track(item,http(item,input,init)); const bytes=new Uint8Array(await result.arrayBuffer());await credit(item);await settle(item);
        return new Response([204,205,304].includes(result.status)?null:bytes,{status:result.status,headers:result.headers});}
      catch(error){await settle(item,true);throw error;}
    },
    /** Native MCP transport calls this for initialize/catalog/call/GET SSE/DELETE, OAuth refresh and reconnect.
     * Each request binds its current connection schema/endpoint/credential revision at the owner port. */
    async mcp(envelope:CapabilityEnvelope,server:string,credential:{ref:string;revision:number}|undefined) {
      const item=await admit(envelope,'renulus.mcp',{server,credential_revision:credential?.revision??0});
      return {fetch:(input:string|URL,init?:RequestInit)=>track(item,http(item,input,init,credential)),
        close:()=>settle(item), signal:item.abort.signal};
    },
    async browser(envelope:CapabilityEnvelope,attachment:BrowserAttachment) {
      if(attachment.context.proxy_only!==true||attachment.context.quic_disabled!==true||attachment.context.webrtc_disabled!==true) reject('browser_proxy_required');
      const item=await admit(envelope,'developer.browser',{connection_id:attachment.connection_id,client_generation:attachment.client_generation,context:attachment.context.identity});
      const sockets=new Set<string>(), pending=new Set<Promise<unknown>>();
      // Resources remain retained through failed/blocked closure and can be retried.
      item.resources.add(()=>attachment.cancelPending()); item.resources.add(()=>attachment.removeNativeAllow()); item.resources.add(()=>attachment.context.close());
      if(options.transport.release) item.resources.add(()=>options.transport.release!(item.lease.id));
      const observe=<T>(p:Promise<T>)=>{pending.add(p);return track(item,p.finally(()=>pending.delete(p)));};
      const checkTarget=(target:{host:string;port:number})=>{if(!item.lease.grant.endpoints.some(e=>e.host===target.host&&e.port===target.port))reject('browser_endpoint_denied');};
      return {
        lease:item.lease,
        current:()=>credit(item),
        async open(target:{host:string;port:number},signal:AbortSignal) {checkTarget(target);await credit(item);if(sockets.size>=8)reject('browser_socket_limit');
          // Capacity is reserved before the async DNS/connect phase.
          const reservation='pending_'+randomUUID();sockets.add(reservation);
          try{return await observe((async()=>{const id=await options.transport.tunnelOpen(item.lease,target,AbortSignal.any([signal,item.abort.signal]));
            const close=()=>options.transport.tunnelClose(id);item.resources.add(close);sockets.add(id);
            try{await credit(item);return id;}catch(error){await close();sockets.delete(id);item.resources.delete(close);throw error;}})());}
          finally{sockets.delete(reservation);}
        },
        async read(id:string,signal:AbortSignal){if(!sockets.has(id))reject('browser_socket_unbound');await credit(item);
          return observe((async()=>{const result=await options.transport.tunnelRead(id,AbortSignal.any([signal,item.abort.signal]));await credit(item,result.data.length);return result;})());},
        async write(id:string,data:Uint8Array,end:boolean,signal:AbortSignal){if(!sockets.has(id))reject('browser_socket_unbound');await credit(item,data.length);
          await observe(options.transport.tunnelWrite(id,data,end,AbortSignal.any([signal,item.abort.signal])));await credit(item);},
        async closeSocket(id:string){if(!sockets.has(id))return;await options.transport.tunnelClose(id);sockets.delete(id);},
        async revoke(){await options.storage.execute({type:'capability.close',root_id:envelope.root_id});await settle(item,true);},
      };
    },
    async stop(root_id:string) {await options.storage.execute({type:'capability.close',root_id});
      const results=await Promise.allSettled([...owned.values()].filter(i=>i.lease.envelope.root_id===root_id).map(i=>settle(i,true)));
      if(results.some(r=>r.status==='rejected'))reject('capability_cleanup_held');},
    status(){return {active:owned.size,settled:owned.size===0};},
    async close(){closing=true; const roots=new Set([...owned.values()].map(i=>i.lease.envelope.root_id));
      for(const root_id of roots)await options.storage.execute({type:'capability.close',root_id});
      const results=await Promise.allSettled([...owned.values()].map(i=>settle(i,true)));if(results.some(r=>r.status==='rejected'))reject('capability_cleanup_held');},
  };
}
