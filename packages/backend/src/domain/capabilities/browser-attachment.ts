// SPDX-License-Identifier: MIT
/** App-owned adapter for the native browser RPC; uses its existing schemas/events. */
import { Effect, Schema, Stream } from 'effect';
import { Browser } from '@opencode/plugin-browser/rpc';
import type { Context } from '@opencode/plugin/effect/plugin';
import { Rpc } from '@opencode/core/rpc';

export interface BrowserEngine {
  identity:string; proxy_only:true;quic_disabled:true;webrtc_disabled:true;
  state(): typeof Browser.State.Type;
  execute(command:typeof Browser.Command.Type,signal:AbortSignal):Promise<typeof Browser.Result.Type>;
  close():Promise<void>;cancelPending():Promise<void>;
}
/** Install in the native location scope after browser registration. A direct attach
 * command must mint the current permit before this is called; no reconnect loop. */
export function attachOwnedBrowser(ctx:Pick<Context,'rpc'|'event'>,input:{sessionID:string;connectionID:string},engine:BrowserEngine) {
  return Effect.gen(function*(){
    const pending=new Map<string,AbortController>();
    const rpc=yield* Rpc.Service;
    const call=(method:string,payload:unknown)=>rpc.call(Browser.Definition.id,method,payload);
    const attachment={sessionID:input.sessionID,connectionID:input.connectionID};
    const report=()=>call('state',{...attachment,state:Schema.encodeSync(Browser.State)(engine.state())});
    yield* ctx.event.subscribe().pipe(Stream.filter(event=>event.type==='rpc.experimental.browser.control'),Stream.runForEach(event=>{
      const raw=event.data as unknown as {connectionID?:string};if(raw.connectionID!==input.connectionID)return Effect.void;
      return Effect.gen(function*(){
        const message=yield* Schema.decodeUnknownEffect(Browser.Control)(event.data);
        if(message.type==='attached'){yield* report();return;}
        if(message.type==='cancel'){pending.get(message.requestID)?.abort();return;}
        const abort=new AbortController();pending.set(message.requestID,abort);
        yield* call('command',{...attachment,requestID:message.requestID}).pipe(Effect.flatMap(raw=>Effect.gen(function*(){
          const command=yield* Schema.decodeUnknownEffect(Browser.Command)((raw as {output?:unknown}).output??raw);
          const result=yield* Effect.tryPromise(()=>engine.execute(command,abort.signal));
          yield* report();
          yield* call('result',{...attachment,requestID:message.requestID,outcome:Schema.encodeSync(Browser.Outcome)({type:'success',result})});
        })),Effect.catchCause(()=>call('result',{...attachment,requestID:message.requestID,outcome:{type:'failure',code:'unavailable',message:'Owned browser action failed or was revoked.'}}).pipe(Effect.ignore)),
          Effect.ensuring(Effect.sync(()=>{pending.delete(message.requestID);})),Effect.forkScoped);
      }).pipe(Effect.orDie);
    }),Effect.forkScoped);
    yield* Effect.addFinalizer(()=>Effect.promise(async()=>{for(const abort of pending.values())abort.abort();await engine.cancelPending();await engine.close();}));
    yield* call('attach',{...attachment,version:4});
  }).pipe(Effect.scoped);
}
