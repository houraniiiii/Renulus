// SPDX-License-Identifier: MIT
import type { IncomingMessage } from 'node:http';
import type { StorageClient } from '../storage/index.ts';
import type { ContentPackPlan } from '../domain/content/contracts.ts';
import { exact,reject } from '../storage/contracts.ts';
import { readJsonObject } from './body.ts';
export interface ContentPorts { validatePack(path:string):Promise<ContentPackPlan> }
export async function contentCommand(request:IncomingMessage,url:URL,storage:StorageClient,ports?:ContentPorts):Promise<{status:number;value:unknown}|undefined> {
  const path=url.pathname;
  if(request.method==='GET'){
    if(path==='/api/v1/content/manifest')return {status:200,value:(await storage.command({type:'content.active'})).manifest};
    if(path==='/api/v1/content/topics')return {status:200,value:(await storage.command({type:'content.topics'})).items};
    if(path==='/api/v1/content/sources')return {status:200,value:(await storage.command({type:'content.sources'})).items};
    const topic=/^\/api\/v1\/content\/topics\/([A-Za-z0-9_.:-]+)$/.exec(path);if(topic)return {status:200,value:await storage.command({type:'content.topic',topicId:topic[1]})};
    const teaching=/^\/api\/v1\/content\/cases\/([A-Za-z0-9_.:-]+)$/.exec(path);if(teaching)return {status:200,value:await storage.command({type:'content.case',caseId:teaching[1],version:null})};
  }
  if(request.method==='POST'&&path==='/api/v1/content/packs/install'){
    const b=await readJsonObject(request,4096);exact(b,['path']);if(typeof b.path!=='string'||!ports)reject('content_validation_unavailable');
    // Existing pure Python content.validation owns schema/licence/source validation and owned path resolution.
    const plan=await ports.validatePack(b.path);return {status:200,value:await storage.command({type:'content.install',plan})};
  }
  const withdrawn=/^\/api\/v1\/content\/questions\/([A-Za-z0-9_.:-]+)\/versions\/([0-9]+)\/withdraw$/.exec(path);
  if(withdrawn&&request.method==='POST'){const b=await readJsonObject(request,4096);exact(b,['reason',...('replacement_version'in b?['replacement_version']:[])]);return {status:200,value:await storage.command({type:'content.withdraw',questionId:withdrawn[1],version:Number(withdrawn[2]),reason:b.reason as string,replacementVersion:(b.replacement_version??null) as number|null})};}
  return undefined;
}
export const handleContentCommand=contentCommand;
