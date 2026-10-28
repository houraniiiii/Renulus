// SPDX-License-Identifier: MIT
import { createHash, randomUUID } from 'node:crypto';
import { closeSync, fsyncSync, lstatSync, openSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import type { RecoverySnapshot, RecoveryStorage, NativeMapping, RecoveryMerge } from '../domain/recovery/contracts.ts';
import { StorageError } from './contracts.ts';
import { owned } from './ownership.ts';
import { canonical } from './schema.ts';
export interface GenerationMember { role:'canonical'|'native'|'original'|'plugin'|'selector'|'schema'; path:string; sha256:string; bytes:number }
export interface CompleteGeneration { profileId:string; generation:number; authorityEpoch:number; schemaHash:string; cohortHash:string; frontierDigest:string; members:readonly GenerationMember[] }
const fail=(code:string):never=>{throw new StorageError(code);};
const sha=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
export const GENERATION_MANIFEST_FILE='.renulus-complete-generation.json';
/** Observations must come from closed owned handles; a manifest cannot attest itself. */
export function validateCompleteGeneration(manifest:CompleteGeneration,observedMembers:readonly GenerationMember[]):string {
  if(!manifest||typeof manifest.profileId!=='string'||!manifest.profileId||!Number.isSafeInteger(manifest.generation)||manifest.generation<1||!Number.isSafeInteger(manifest.authorityEpoch)||manifest.authorityEpoch<1||
    ![manifest.schemaHash,manifest.cohortHash,manifest.frontierDigest].every(v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v))||!Array.isArray(manifest.members)||manifest.members.length>100000)fail('recovery_generation_invalid');
  const paths=new Set<string>(),roles=new Map<string,number>();
  for(const m of manifest.members) {
    if(!['canonical','native','original','plugin','selector','schema'].includes(m.role)||typeof m.path!=='string'||!m.path||m.path.length>4096||m.path.includes('\\')||m.path.startsWith('/')||m.path.split('/').some(p=>!p||p==='.'||p==='..'||p.includes(':'))||
      !/^[a-f0-9]{64}$/.test(m.sha256)||!Number.isSafeInteger(m.bytes)||m.bytes<0||paths.has(m.path.toLowerCase()))fail('recovery_generation_member');
    paths.add(m.path.toLowerCase());roles.set(m.role,(roles.get(m.role)??0)+1);
  }
  for(const role of ['canonical','native','selector','schema'])if(roles.get(role)!==1)fail('recovery_generation_incomplete');
  if(!roles.get('plugin'))fail('recovery_generation_incomplete');
  const sort=(members:readonly GenerationMember[])=>[...members].sort((a,b)=>a.path.localeCompare(b.path));
  if(canonical(sort(manifest.members))!==canonical(sort(observedMembers)))fail('recovery_generation_member_mismatch');
  return sha(manifest);
}
/** Hashes members of a CLOSED generation directory and publishes its manifest last (no-replace, fsynced). */
export function sealGeneration(root:string,header:Omit<CompleteGeneration,'members'>,members:readonly Pick<GenerationMember,'role'|'path'>[]):CompleteGeneration {
  const manifest:CompleteGeneration={...header,members:members.map(m=>{
    const file=owned(root,resolve(root,m.path)),stat=lstatSync(file);
    if(!stat.isFile())fail('recovery_generation_member');
    return {role:m.role,path:m.path,sha256:createHash('sha256').update(readFileSync(file)).digest('hex'),bytes:stat.size};
  })};
  const temporary=owned(root,join(root,'.manifest-'+randomUUID()+'.tmp')),fd=openSync(temporary,'wx',0o600);
  try {writeFileSync(fd,canonical(manifest));fsyncSync(fd);}finally{closeSync(fd);}
  renameSync(temporary,owned(root,join(root,GENERATION_MANIFEST_FILE)));
  return manifest;
}
export interface GenerationOwner {
  /** Identity and current size, readable while running; the size sizes the peak reservation. */
  describe():Promise<{profileId:string;schemaHash:string;cohortHash:string;bytes:number;originals:Readonly<Record<string,string>>}>;
  /** Logical hold first, actual owners settle before any file/snapshot guard. */
  closeAdmission():Promise<void>; drain():Promise<void>;
  snapshotClosed():Promise<{manifest:CompleteGeneration;observedMembers:GenerationMember[]}>;
}
export async function prepareGeneration(owner:GenerationOwner):Promise<CompleteGeneration> {
  await owner.closeAdmission();await owner.drain();
  const {manifest,observedMembers}=await owner.snapshotClosed();validateCompleteGeneration(manifest,observedMembers);return manifest;
}
export interface NativePreview { retained:number; currentOnly:number; added:number; excluded:number }
export interface SpaceMeasurement { allocatedBytes:number; freeBytes:number; ceilingBytes:number }
export interface RestorePreview {
  canonical:RecoveryMerge; native:NativePreview; originals:{count:number;bytes:number;retained:number;added:number};
  space:SpaceMeasurement&{peakBytes:number;fits:boolean};
}
export interface RecoveryCoordinatorOptions<Graph> {
  current:GenerationOwner;
  currentStorage:RecoveryStorage;
  /** Measured by the owned native storage worker (allocated bytes, target-volume free bytes, app ceiling). */
  measure():Promise<SpaceMeasurement>;
  /** Read-only comparison of the live native store with the incoming graph; throws on any conflict. */
  previewNative(incoming:Graph,eligibleSessions:ReadonlySet<string>):Promise<NativePreview>;
  /** Creates a hidden candidate from the settled CURRENT complete generation. */
  forkCurrent(manifest:CompleteGeneration):Promise<{storage:RecoveryStorage & {close():Promise<void>};candidateId:string}>;
  mergeNative(candidateId:string,incoming:Graph,eligibleSessions:ReadonlySet<string>,rollback?:boolean):Promise<NativeMapping>;
  /** Returns native-verified rebased original handles on canonical rows. */
  verifyOriginals(candidateId:string,incoming:CompleteGeneration,canonical:RecoverySnapshot):Promise<RecoverySnapshot>;
  closeCandidate(candidateId:string):Promise<{manifest:CompleteGeneration;observedMembers:GenerationMember[]}>;
  verifyCanonicalClosure(candidateId:string):Promise<void>;
  /** Governed removal of an unselected hidden candidate; never touches the selector or the current generation. */
  discardCandidate(candidateId:string):Promise<void>;
}
const sum=(members:readonly GenerationMember[])=>members.reduce((n,m)=>n+m.bytes,0);
/** Stages a complete additive candidate; BF08 alone publishes the outer selector. */
export function createRecoveryCoordinator<Graph>(o:RecoveryCoordinatorOptions<Graph>) {
  let running=false;
  async function compatible(input:{incoming:CompleteGeneration;observedMembers:GenerationMember[]}) {
    validateCompleteGeneration(input.incoming,input.observedMembers);
    const current=await o.current.describe();
    if(current.profileId!==input.incoming.profileId||current.schemaHash!==input.incoming.schemaHash||current.cohortHash!==input.incoming.cohortHash)fail('recovery_generation_incompatible');
    return current;
  }
  async function preview(input:{incoming:CompleteGeneration;observedMembers:GenerationMember[];canonical:RecoverySnapshot;native:Graph}):Promise<RestorePreview&{frontierDigest:string}> {
    const current=await compatible(input),frontier=(await o.currentStorage.command({type:'recovery.snapshot'})).frontierDigest;
    const canonicalPreview=await o.currentStorage.command({type:'recovery.preview',incoming:input.canonical,currentFrontierDigest:frontier});
    const native=await o.previewNative(input.native,new Set(canonicalPreview.eligibleNativeSessions));
    const originals=input.incoming.members.filter(m=>m.role==='original');
    // Immutable originals are identified by path and bytes: the same identity with different bytes is a hard conflict.
    for(const m of originals)if(current.originals[m.path]!==undefined&&current.originals[m.path]!==m.sha256)fail('recovery_immutable_conflict');
    const retained=originals.filter(m=>current.originals[m.path]!==undefined).length;
    const space=await o.measure(),peakBytes=current.bytes+sum(input.incoming.members);
    return {canonical:canonicalPreview,native,originals:{count:originals.length,bytes:sum(originals),retained,added:originals.length-retained},
      space:{...space,peakBytes,fits:space.allocatedBytes+peakBytes<=space.ceilingBytes&&space.freeBytes-peakBytes>=12*1024**3},frontierDigest:frontier};
  }
  async function prepareRollback(input:Parameters<typeof preview>[0]) {
    const checked=await preview(input);
    await o.currentStorage.command({type:'recovery.rollback',incoming:input.canonical,currentFrontierDigest:checked.frontierDigest});
    if(checked.native.currentOnly)fail('recovery_rollback_newer_records');
    return coordinator.prepare(input,true);
  }
  const coordinator={
    prepareRollback,
    /** Read-only: nothing is closed, written, reserved or selected. */
    async preview(input:Parameters<typeof preview>[0]):Promise<RestorePreview> {const {frontierDigest:_,...result}=await preview(input);return result;},
    async prepare(input:Parameters<typeof preview>[0],rollback=false):Promise<{candidateId:string;manifest:CompleteGeneration;preview:RecoveryMerge;reservationId:string}> {
      if(running)fail('recovery_busy');running=true;
      try {
        // Conflicts and low space refuse before admission is closed or any peak is reserved.
        const early=await preview(input);
        if(rollback){await o.currentStorage.command({type:'recovery.rollback',incoming:input.canonical,currentFrontierDigest:early.frontierDigest});if(early.native.currentOnly)fail('recovery_rollback_newer_records');}
        if(!early.space.fits)fail('storage_waiting_space');
        const reservationId='recovery-'+randomUUID();
        await o.currentStorage.command({type:'storage.reserve',request:{id:reservationId,intentId:reservationId,peakBytes:early.space.peakBytes,
          allocatedBytes:early.space.allocatedBytes,freeBytes:early.space.freeBytes,ceilingBytes:early.space.ceilingBytes}});
        const current=await prepareGeneration(o.current);
        const candidate=await o.forkCurrent(current);
        try {
          const snapshot=await candidate.storage.command({type:'recovery.snapshot'});
          if(snapshot.frontierDigest!==current.frontierDigest)fail('recovery_frontier_changed');
          if(rollback)await candidate.storage.command({type:'recovery.rollback',incoming:input.canonical,currentFrontierDigest:snapshot.frontierDigest});
          const eligible=new Set((await candidate.storage.command({type:'recovery.preview',incoming:input.canonical,currentFrontierDigest:snapshot.frontierDigest})).eligibleNativeSessions);
          const mapping=await o.mergeNative(candidate.candidateId,input.native,eligible,rollback);
          const merged=await candidate.storage.command({type:'recovery.merge',incoming:input.canonical,mapping,currentFrontierDigest:snapshot.frontierDigest});
          const verifiedCanonical=await o.verifyOriginals(candidate.candidateId,input.incoming,await candidate.storage.command({type:'recovery.snapshot'}));
          await candidate.storage.command({type:'recovery.originals',originals:(['knowledge_revisions','knowledge_attachment_originals'] as const).flatMap(table=>(verifiedCanonical.records[table]??[]).map(r=>({table,id:String(r.id),handle:r.original_path===null?null:String(r.original_path)})))});
          await o.verifyCanonicalClosure(candidate.candidateId);
          // The current owner is closed; the candidate carries the journal copy taken after the reservation.
          await candidate.storage.command({type:'storage.settle',id:reservationId,intentId:reservationId,settled:true,cleanupDebtBytes:0});
          await candidate.storage.close();
          const closed=await o.closeCandidate(candidate.candidateId);validateCompleteGeneration(closed.manifest,closed.observedMembers);
          return {candidateId:candidate.candidateId,manifest:closed.manifest,preview:merged,reservationId};
        } catch(error) {
          await candidate.storage.close().catch(()=>{});
          // An undiscarded candidate stays hidden and unselected; its owner keeps it as cleanup debt.
          await o.discardCandidate(candidate.candidateId).catch(()=>{});
          throw error;
        }
      }finally{running=false;}
    },
  };
  return coordinator;
}
