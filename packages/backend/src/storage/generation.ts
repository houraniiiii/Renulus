// SPDX-License-Identifier: MIT
import { createHash } from 'node:crypto';
import type { RecoverySnapshot, RecoveryStorage, NativeMapping, RecoveryMerge } from '../domain/recovery/contracts.ts';
import { StorageError } from './contracts.ts';
import { canonical } from './schema.ts';
export interface GenerationMember { role:'canonical'|'native'|'original'|'plugin'|'selector'|'schema'; path:string; sha256:string; bytes:number }
export interface CompleteGeneration { profileId:string; generation:number; authorityEpoch:number; schemaHash:string; cohortHash:string; frontierDigest:string; members:readonly GenerationMember[] }
const fail=(code:string):never=>{throw new StorageError(code);};
const sha=(v:unknown)=>createHash('sha256').update(canonical(v)).digest('hex');
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
export interface GenerationOwner {
  /** Logical hold first, actual owners settle before any file/snapshot guard. */
  closeAdmission():Promise<void>; drain():Promise<void>;
  snapshotClosed():Promise<{manifest:CompleteGeneration;observedMembers:GenerationMember[]}>;
}
export async function prepareGeneration(owner:GenerationOwner):Promise<CompleteGeneration> {
  await owner.closeAdmission();await owner.drain();
  const {manifest,observedMembers}=await owner.snapshotClosed();validateCompleteGeneration(manifest,observedMembers);return manifest;
}
export interface RecoveryCoordinatorOptions<Graph> {
  current:GenerationOwner;
  currentStorage:RecoveryStorage;
  /** Creates a hidden candidate from the settled CURRENT complete generation. */
  forkCurrent(manifest:CompleteGeneration):Promise<{storage:RecoveryStorage & {close():Promise<void>};candidateId:string}>;
  mergeNative(candidateId:string,incoming:Graph):Promise<NativeMapping>;
  /** Returns native-verified rebased original handles on canonical rows. */
  verifyOriginals(candidateId:string,incoming:CompleteGeneration,canonical:RecoverySnapshot):Promise<RecoverySnapshot>;
  closeCandidate(candidateId:string):Promise<{manifest:CompleteGeneration;observedMembers:GenerationMember[]}>;
  verifyCanonicalClosure(candidateId:string):Promise<void>;
}
/** Stages a complete additive candidate; BF08 alone publishes the outer selector. */
export function createRecoveryCoordinator<Graph>(o:RecoveryCoordinatorOptions<Graph>) {
  let running=false;
  return {async prepare(input:{incoming:CompleteGeneration;observedMembers:GenerationMember[];canonical:RecoverySnapshot;native:Graph}):Promise<{candidateId:string;manifest:CompleteGeneration;preview:RecoveryMerge}> {
    if(running)fail('recovery_busy');running=true;
    try {
      validateCompleteGeneration(input.incoming,input.observedMembers);
      const current=await prepareGeneration(o.current);
      if(current.profileId!==input.incoming.profileId||current.schemaHash!==input.incoming.schemaHash||current.cohortHash!==input.incoming.cohortHash)fail('recovery_generation_incompatible');
      const candidate=await o.forkCurrent(current);
      const snapshot=await candidate.storage.command({type:'recovery.snapshot'});
      const mapping=await o.mergeNative(candidate.candidateId,input.native);
      const verifiedCanonical=await o.verifyOriginals(candidate.candidateId,input.incoming,input.canonical);
      const preview=await candidate.storage.command({type:'recovery.merge',incoming:verifiedCanonical,mapping,currentFrontierDigest:snapshot.frontierDigest});
      await o.verifyCanonicalClosure(candidate.candidateId);
      await candidate.storage.close();
      const closed=await o.closeCandidate(candidate.candidateId);validateCompleteGeneration(closed.manifest,closed.observedMembers);
      return {candidateId:candidate.candidateId,manifest:closed.manifest,preview};
    }finally{running=false;}
  }};
}
