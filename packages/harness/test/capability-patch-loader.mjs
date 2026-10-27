// SPDX-License-Identifier: MIT
// Test-only exact-source loader. Production uses native-patch.mjs on owned build copies.
import { registerHooks } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { patches, transform, sha } from '../../backend/src/domain/capabilities/native-patch.mjs';
const hashes=JSON.parse(readFileSync(new URL('../../backend/src/domain/capabilities/native-patch-hashes.json',import.meta.url)));
const core=fileURLToPath(import.meta.resolve('@opencode/core/tool')).replace(/dist[\\/]tool\.js$/,'');
const browser=fileURLToPath(import.meta.resolve('@opencode/plugin-browser')).replace(/dist[\\/]index\.js$/,'');
const boundaryURL=new URL('file:///'+(core+'dist/renulus-boundary.js').replaceAll('\\','/')).href;
const files=new Map(patches.map(p=>[fileURLToPath(new URL('file:///'+((p.package==='core'?core:browser)+p.file).replaceAll('\\','/'))).toLowerCase(),p]));
registerHooks({
  resolve(specifier,context,next){
    if(specifier==='@opencode/core/renulus-boundary'||specifier.endsWith('/renulus-boundary.js'))return {url:boundaryURL,shortCircuit:true};
    return next(specifier,context);
  },
  load(url,context,next){
    if(url===boundaryURL)return {format:'module',source:`import {Context} from 'effect';export const CapabilityBoundary=Context.Reference('renulus/native-capability-boundary/1',{defaultValue:()=>undefined});`,shortCircuit:true};
    const result=next(url,context);if(!url.startsWith('file:'))return result;
    const p=files.get(fileURLToPath(url).toLowerCase());if(!p)return result;
    const source=readFileSync(fileURLToPath(url),'utf8');if(sha(source)!==hashes[p.package+'/'+p.file])throw new Error('patch_fixture_source_changed');
    return {...result,source:transform(source,p)};
  },
});
