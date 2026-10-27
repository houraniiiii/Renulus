// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import { Context, Effect, Layer } from 'effect';
import { Tool } from '@opencode/core/tool';
import { Skill } from '@opencode/core/skill';
import { State } from '@opencode/core/state';
import { Permission } from '@opencode/core/permission';
import type { Plugin } from '@opencode/plugin/effect/plugin';
import type { Tool as ToolSchema } from '@opencode/schema/tool';
import { createChildAuthority } from './child-authority.ts';
import { capabilityAction, type NativeCapabilityPorts, type NativeCapabilityContext } from './capability-authority.ts';

const failure=(code:string)=>new Tool.Error({message:code});
const qualified=(tool:ToolSchema.Info)=>tool.options?.namespace?tool.options.namespace+'.'+tool.name:tool.name;
/** Install capture before the stock-tool boundary, and plugins after it. No alternate tool bus. */
export async function createNativeCapabilityPlugin(ports:NativeCapabilityPorts) {
  const stock=new Map<string,ToolSchema.Info>();
  let closed=false;
  const Invocation=Context.Reference<{envelope:import('../../backend/src/domain/capabilities/contracts.ts').CapabilityEnvelope;signal:AbortSignal}|undefined>('renulus/capability-invocation',{defaultValue:()=>undefined});
  // The patched module only exists in a validated owned build. Defaults need no patch.
  const patchModule='@opencode/core/renulus-boundary';
  let boundaryTag: Context.Reference<unknown>|undefined;
  if(ports.developer||ports.mcp) {
    try { boundaryTag=(await import(patchModule)).CapabilityBoundary; }
    catch {throw new Error('native_capability_patch_required');}
  }
  const boundary={
    async fetch(native:NativeCapabilityContext,input:string,init:RequestInit={}) {
      if(!ports.developer||closed)throw failure('developer_disabled');
      const e=await ports.resolve(native),response=await ports.authority.fetch(e,String(input),init),bytes=new Uint8Array(await response.arrayBuffer());
      const headers=Object.fromEntries(response.headers),text=()=>new TextDecoder().decode(bytes);
      return {url:String(input),status:response.status,statusText:response.statusText,ok:response.ok,redirected:false,
        headers:{get:(n:string)=>headers[n.toLowerCase()]??null,has:(n:string)=>Object.hasOwn(headers,n.toLowerCase()),entries:()=>Object.entries(headers)},
        text:async()=>text(),json:async()=>JSON.parse(text()),bytes:async()=>bytes};
    },
    async mcp(server:string,config:unknown){if(!ports.mcp||closed)throw failure('mcp_disabled');return ports.mcp(server,config);},
    mcpTool(descriptor:{server:string;name:string;inputSchema?:unknown;outputSchema?:unknown},input:unknown,native:NativeCapabilityContext,execute:Effect.Effect<ToolSchema.Result,unknown>){
      return Effect.context<never>().pipe(Effect.flatMap(context=>Effect.tryPromise({try:async signal=>{
        if(!ports.mcp||!ports.approveMcpTool||closed)throw failure('mcp_disabled');
        const envelope=await ports.resolve(native);
        const approve=ports.approveMcpTool;
        await approve(descriptor,envelope,signal);
        return ports.authority.invoke(envelope,'renulus.mcp',{descriptor,input},async(_lease,ownedSignal)=>{
          const combined=AbortSignal.any([signal,ownedSignal]);
          const result=await Effect.runPromiseWith(context)(provide(execute).pipe(Effect.provideService(Invocation,{envelope,signal:combined})),{signal:combined});
          await approve(descriptor,envelope,combined);return result;
        });
      },catch:()=>failure('mcp_authority_refused')})));
    },
    async browser(input:{sessionID:string;connectionID:string}){if(!ports.developer||closed||!ports.localCurrent(input.sessionID))throw failure('developer_disabled');return ports.developer.browser(input);},
  };
  const provide=<A,E,R>(effect:Effect.Effect<A,E,R>)=>boundaryTag?effect.pipe(Effect.provideService(boundaryTag,boundary)):effect;
  const nativeContext=(native:NativeCapabilityContext):NativeCapabilityContext=>({sessionID:native.sessionID,messageID:native.messageID,id:native.id,agent:native.agent});
  const invoke=(name:string,input:unknown,native:ToolSchema.Context,original:ToolSchema.Info['execute'])=>Effect.context<never>().pipe(
    Effect.flatMap(context=>Effect.tryPromise({try:async signal=>{
      if(closed||!ports.localCurrent(native.sessionID))throw failure('capability_stale');
      const envelope=await ports.resolve(nativeContext(native)),action=capabilityAction(name);
      if(!action)throw failure('capability_unknown');
      return ports.authority.invoke(envelope,action,input,async(lease,ownedSignal)=>{
        const combined=AbortSignal.any([signal,ownedSignal]);combined.throwIfAborted();
        const command=({question:'question',webfetch:'evidence.fetch',websearch:'evidence.search','opencode.models':'models','opencode.session_rename':'rename'} as const)[name as 'question'];
        if(command)return ports.command(command,input,envelope,combined);
        if(name==='skill') {
          const id=input&&typeof input==='object'&&'name' in input?input.name:null;
          const skill=ports.skills.find(s=>s.info.name===id||s.info.id===id);
          if(!skill||!lease.grant.skills.includes(String(skill.info.id)))throw failure('skill_not_curated');
          return {content:skill.info.content,metadata:{skill_id:skill.info.id,sha256:skill.sha256}};
        }
        if(action.startsWith('developer.')&&!ports.developer)throw failure('developer_disabled');
        if(name==='shell')return ports.developer!.shell(input,lease,combined);
        let guard:{close():Promise<void>}|undefined;
        try {
          if(action.startsWith('developer.files.')||['browser.files.upload','browser.files.drop','browser.preview'].includes(name))guard=await ports.developer!.files(lease,name,input,combined);
          if(action==='developer.worktree')guard=await ports.developer!.worktree(name,input,lease,combined);
          return await Effect.runPromiseWith(context)(provide(original(input,native)).pipe(Effect.provideService(Invocation,{envelope,signal:combined})),{signal:combined});
        } finally {await guard?.close();}
      });
    },catch:error=>error instanceof Tool.Error?error:failure(error instanceof Error&&/^[a-z_]+$/.test(error.message)?error.message:'capability_failed')})));
  const capture:Plugin={id:'renulus-native-capability-capture',effect:ctx=>ctx.tool.transform(editor=>{
    for(const tool of editor.list()) {const name=qualified(tool);if(capabilityAction(name)&&!name.startsWith('browser.'))stock.set(name,{...tool});}
  })};
  const child=ports.children?createChildAuthority(ports.children,{maxChildren:32,maxInvocations:32,maxDescriptionBytes:2048,maxPromptBytes:16000,maxReportBytes:65536}):undefined;
  const plugin:Plugin={id:'renulus-native-capabilities',effect:ctx=>Effect.gen(function*(){
    for(const skill of ports.skills)if(createHash('sha256').update(skill.info.content).digest('hex')!==skill.sha256)throw new Error('curated_skill_integrity');
    yield* ctx.skill.transform(editor=>{for(const skill of editor.list())editor.remove(skill.id);for(const skill of ports.skills)editor.add(skill.info);});
    yield* ctx.tool.transform(editor=>{
      for(const [name,tool] of stock) {
        if(name==='subagent'&&!child)continue;
        if(capabilityAction(name)?.startsWith('developer.')&&!ports.developer)continue;
        if(capabilityAction(name)==='renulus.mcp'&&!ports.mcp)continue;
        editor.add({...tool,execute:(input,native)=>invoke(name,input,native,tool.execute),options:{...tool.options,pinned:undefined,
          permission:capabilityAction(name),codemode:ports.developer?tool.options?.codemode??false:false}});
      }
    });
    if(ports.developer) {
      const BrowserPlugin=yield* Effect.promise(()=>import('@opencode/plugin-browser'));
      yield* provide(BrowserPlugin.default.effect(ctx));
      yield* ctx.tool.transform(editor=>{
        for(const tool of editor.list()) {const name=qualified(tool);if(name.startsWith('browser.'))editor.update(tool.id,current=>{
          const execute=current.execute;current.execute=(input,native)=>invoke(name,input,native,execute);
          current.options={...current.options,permission:capabilityAction(name)};
        });}
      });
    }
    yield* ctx.permission.hook('evaluate',event=>Effect.sync(()=>{
      if(!ports.localCurrent(event.sessionID))event.effect='deny';
      // Session-wide native 'always' approval never supplies application authority.
      if(event.effect==='ask')event.message='Approve this operation in Renulus.';
    }));
  })};
  const overrides=[
    Permission.node.replace(Permission.node.mapLayer(original=>Layer.flatMap(original,context=>{
      const service=Context.get(context,Permission.Service);
      return Layer.succeed(Permission.Service,{...service,assert:input=>Effect.gen(function*(){
        const owner=yield* Invocation;if(!owner)return yield* service.assert(input);
        if(input.sessionID!==owner.envelope.session_id||!ports.localCurrent(input.sessionID))return yield* new Permission.BlockedError({permission:input.action,resources:input.resources,rules:[],reason:'capability_stale'});
        const decision=yield* Effect.tryPromise({try:()=>ports.command('permission',{action:input.action,resources:input.resources,source:input.source??null},owner.envelope,owner.signal),
          catch:()=>new Permission.BlockedError({permission:input.action,resources:input.resources,rules:[],reason:'capability_permission_rejected'})});
        if(decision.metadata?.approved!==true||!ports.localCurrent(input.sessionID))return yield* new Permission.BlockedError({permission:input.action,resources:input.resources,rules:[],reason:'capability_permission_rejected'});
      })});
    }))),
    // Skill construction never scans home/workspace/remote directories.
    Skill.node.replace(Layer.sync(Skill.Service,()=>{
      const state=State.create<Map<string,Skill.Info>,Skill.Editor>({initial:()=>new Map(ports.skills.map(s=>[s.info.id,s.info])),
        editor:map=>({list:()=>[...map.values()],get:id=>map.get(id),add:skill=>{map.set(skill.id,skill);},
          update:(id,update)=>{const skill=map.get(id);if(skill)update(skill);},remove:id=>{map.delete(id);}})});
      return {list:()=>Effect.sync(()=>[...state.get().values()]),get:(id:Skill.ID)=>Effect.sync(()=>state.get().get(id)),
        transform:state.transform,reload:state.reload};
    })),
    Tool.node.replace(Tool.node.mapLayer(original=>Layer.flatMap(original,context=>{
      const service=Context.get(context,Tool.Service);
      return Layer.succeed(Tool.Service,{...service,snapshot:rules=>service.snapshot([...rules??[],
        ...!ports.developer?[{action:'execute',resource:'*',effect:'deny' as const}]:[]]).pipe(Effect.map(snapshot=>({...snapshot,
        execute:input=>input.call.name==='execute'?invoke('execute',input.call.input,{sessionID:input.sessionID,agent:input.agent,
          messageID:input.messageID,id:Tool.CallID.make(input.call.id),progress:input.progress??(()=>Effect.void)},
          ()=>snapshot.execute(input)).pipe(Effect.map(result=>({...result,content:typeof result.content==='string'?
            [{type:'text' as const,text:result.content}]:result.content??[]}))):provide(snapshot.execute(input)),
      })))});
    }))),
    ...(child?.overrides??[]),
  ];
  return {capture,plugins:[plugin,...child?[child.plugin]:[]],overrides,provide,
    config:{execute:!!ports.developer,permissions:[...new Set([...stock.keys()].map(capabilityAction).filter(Boolean))]},
    child,
    async stop(root_id:string,binding?:import('./domain-ipc.ts').DomainBinding){await ports.authority.stop(root_id);
      if(child&&binding){const status=await Effect.runPromise(child.familyStop(binding,1000));if(!status.settled)throw new Error('child_cleanup_held');}},
    async close(){closed=true;await ports.authority.close();if(child){const status=await Effect.runPromise(child.close(1000));if(!status.settled)throw new Error('child_cleanup_held');}},
    status:()=>ports.authority.status(),
  };
}
export type NativeCapabilities=Awaited<ReturnType<typeof createNativeCapabilityPlugin>>;
