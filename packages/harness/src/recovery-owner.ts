// SPDX-License-Identifier: MIT
import type { GenerationOwner, RecoveryCoordinatorOptions, CompleteGeneration } from '../../backend/src/storage/generation.ts';
import type { RecoveryStorage } from '../../backend/src/domain/recovery/contracts.ts';
import { verifyNativeClosure } from '../../backend/src/storage/recovery.ts';
import { createGraphRecovery, mergeRecoveryGraphs, type RecoveryGraph } from './graph-recovery.ts';
import { createHash, randomUUID } from 'node:crypto';
import type { RecoverySnapshot } from '../../backend/src/domain/recovery/contracts.ts';
import type { KnowledgeNativeIO, SourcePin, Rights, ImportIntent } from '../../backend/src/domain/knowledge/contracts.ts';
import type { NativeStorageIO } from '../../backend/src/workers/knowledge.ts';

/** Only surviving canonical originals are published; shared bytes remain available
 * to other eligible owners when one attachment has lost its cache rights. */
export async function publishRecoveryOriginals(snapshot:RecoverySnapshot,
  read:(table:string,id:string,pin:SourcePin)=>Promise<Uint8Array>, native:KnowledgeNativeIO):Promise<RecoverySnapshot> {
  const next=structuredClone(snapshot),published=new Map<string,string>();
  for(const table of ['knowledge_revisions','knowledge_attachment_originals'])for(const row of next.records[table]??[]) {
    const attachment=table==='knowledge_attachment_originals';
    const metadata=attachment?next.records.knowledge_attachment_metadata?.find(r=>r.attachment_id===row.attachment_id):row;
    const rights=JSON.parse(String(metadata?.rights_json??'{}')) as Rights;
    const media=attachment?next.records.knowledge_attachments?.find(r=>r.id===row.attachment_id)?.media_type:row.media_type;
    if(rights.cache!==true){row.original_path=null;continue;}
    if(typeof row.original_path!=='string'||!row.original_path)throw new Error('recovery_original_unavailable');
    const revision=String(row.id),digest=String(row.sha256),key=revision+':'+digest;
    if(published.has(key)){row.original_path=published.get(key)!;continue;}
    const pin:SourcePin={reference:{target:{type:attachment?'attachment':'library_revision',id:String(attachment?row.attachment_id:row.id)}},
      document_id:attachment?null:String(row.document_id),revision_id:revision,title:'Recovery original',filename:revision,
      media_type:String(media),sha256:digest,bytes:Number(row.bytes),original_handle:row.original_path,rights,
      metadata:{source_id:'recovery'},stamp:snapshot.frontierDigest,fingerprint:snapshot.frontierDigest,
      policy_revision:0,context_epoch:0,attachment_revision:null};
    const id='recovery_'+randomUUID().replaceAll('-','');
    const intent:ImportIntent={id,document_id:pin.document_id??revision,revision_id:revision,job_id:id,reservation_id:id,
      stamp:snapshot.frontierDigest,state:'prepared',original_handle:null,request:{title:pin.title,media_type:pin.media_type,bytes:pin.bytes,sha256:digest,
        metadata:pin.metadata,rights,document_id:null,expected_revision_id:null,project_id:null,note:false,idempotency_key:id}};
    await native.reserve(intent);
    try {
      const body=await read(table,revision,pin);
      if(body.length!==pin.bytes||createHash('sha256').update(body).digest('hex')!==digest)throw new Error('recovery_original_integrity');
      const result=await native.publish({intent,body});row.original_path=result.original_handle;
      published.set(key,result.original_handle);intent.original_handle=result.original_handle;intent.state='ready';
    } finally {await native.settle(intent);}
  }
  return next;
}

export interface RecoveryOwnerOptions {
  current: GenerationOwner;
  storage: RecoveryStorage;
  native: ReturnType<typeof createGraphRecovery>;
  storeId: string;
  /** The owned native storage worker: budget measurement and governed candidate retirement. */
  nativeStorage: NativeStorageIO;
  /** Native owner supplies a closed canonical clone and an EMPTY held native host. */
  forkCurrent(manifest:CompleteGeneration):Promise<{candidateId:string;storage:RecoveryStorage & {close():Promise<void>};native:ReturnType<typeof createGraphRecovery>;close():Promise<void>}>;
  verifyOriginals: RecoveryCoordinatorOptions<RecoveryGraph>['verifyOriginals'];
  closeCandidate: RecoveryCoordinatorOptions<RecoveryGraph>['closeCandidate'];
}

/** Uses the live harness sessions API; no inference, SDK database opener or pathname cleanup. */
export function createRecoveryOwner(o:RecoveryOwnerOptions):RecoveryCoordinatorOptions<RecoveryGraph> {
  const native=o.native, candidates=new Map<string,Awaited<ReturnType<RecoveryOwnerOptions['forkCurrent']>>>();
  let settled:RecoveryGraph|undefined;
  return {
    current:{...o.current,async snapshotClosed(){settled=await native.snapshotAll();return o.current.snapshotClosed();}},
    currentStorage:o.storage,measure:()=>o.nativeStorage.measure(),
    async previewNative(incoming,eligible){
      const merged=mergeRecoveryGraphs(await native.snapshotAll(),incoming,o.storeId,s=>eligible.has(String(s.info.id)));
      return {retained:merged.retained,currentOnly:merged.currentOnly,added:merged.added,excluded:merged.excluded};
    },
    async forkCurrent(manifest){const c=await o.forkCurrent(manifest);candidates.set(c.candidateId,c);return c;},
    async mergeNative(id,incoming,eligible,rollback){
      if(!settled)throw new Error('recovery_current_unsettled');
      if(rollback&&mergeRecoveryGraphs(settled,incoming,o.storeId,s=>eligible.has(String(s.info.id))).currentOnly)throw new Error('recovery_rollback_newer_records');
      return (await candidates.get(id)!.native.importMerged(settled,incoming,s=>eligible.has(String(s.info.id)))).mapping;
    },
    verifyOriginals:o.verifyOriginals,
    async verifyCanonicalClosure(id){
      const c=candidates.get(id)!,graph=await c.native.snapshotAll();
      verifyNativeClosure((await c.storage.command({type:'recovery.snapshot'})).records,{
        sessions:new Set(graph.sessions.map(s=>String(s.info.id))),messages:new Set(graph.sessions.flatMap(s=>s.messages.map(m=>String(m.id))))});
    },
    async closeCandidate(id){await candidates.get(id)!.close();return o.closeCandidate(id);},
    async discardCandidate(id){await candidates.get(id)!.close();await o.nativeStorage.retire(id);candidates.delete(id);},
  };
}
