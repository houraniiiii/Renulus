// SPDX-License-Identifier: MIT
import type { Tool } from '@opencode/schema/tool';
import type { Skill } from '@opencode/schema/skill';
import type { CapabilityEnvelope, CapabilityLease } from '../../backend/src/domain/capabilities/contracts.ts';
import type { createCapabilityAuthority } from '../../backend/src/domain/capabilities/authority.ts';
import type { ChildAuthorityBridge } from './child-authority.ts';

export type NativeCapabilityContext = Pick<Tool.Context,'sessionID'|'messageID'|'id'|'agent'>;
export type NativeCapabilityAuthority = ReturnType<typeof createCapabilityAuthority>;
export interface NativeCapabilityPorts {
  authority: NativeCapabilityAuthority;
  /** Resolve the original admitted USER/root and actual assistant/tool ID. */
  resolve(native: NativeCapabilityContext): Promise<CapabilityEnvelope>;
  /** Local seal used inside native permission hooks; never await IPC here. */
  localCurrent(sessionID: string): boolean;
  /** Application execution of adapted native tools. A stock tool registers only when its command exists. */
  commands: Partial<Record<'question'|'permission'|'rename'|'evidence.fetch'|'evidence.search',
    (input: unknown, envelope: CapabilityEnvelope, signal: AbortSignal) => Promise<Tool.Result>>>;
  skills: readonly { info: Skill.Info; sha256: string }[];
  developer?: {
    /** Explicit separate developer profile; supplying the option is not a grant. */
    workspace: string;
    /** Pinned Windows filesystem primitives validate all targets and expected hashes;
     * return is an owned guard held throughout the native filesystem action. */
    files(lease:CapabilityLease,tool:string,input:unknown,signal:AbortSignal):Promise<{close():Promise<void>}>;
    /** Worker-owned Windows Job Object; maps native shell result, waits descendant settlement. */
    shell(input:unknown,lease:CapabilityLease,signal:AbortSignal):Promise<Tool.Result>;
    worktree(tool:string,input:unknown,lease:CapabilityLease,signal:AbortSignal):Promise<{close():Promise<void>}>;
    browser(input:{sessionID:string;connectionID:string}):Promise<{
      current():Promise<void>;revoke():Promise<void>;
      tunnels:{open(target:{host:string;port:number}):unknown;read(id:string):unknown;write(id:string,data:Uint8Array,end?:boolean):unknown;close(id:string):unknown;dispose():void};
    }>;
  };
  /** Each connection resolves endpoint/schema/credential revisions from current Settings.
   * Native OAuth stores are disabled by the narrow patch. This port owns refresh. */
  mcp?(server:string,configuration:unknown):Promise<{
    fetch(input:string|URL|Request,init?:RequestInit):Promise<Response>;
    localTransport(input:unknown):unknown;
    close():Promise<void>;
  }>;
  /** Host checks exact selected server/endpoint/credential/schema revisions, including unknown effects approval. */
  approveMcpTool?(descriptor:{server:string;name:string;inputSchema?:unknown;outputSchema?:unknown},envelope:CapabilityEnvelope,signal:AbortSignal):Promise<void>;
  children?: ChildAuthorityBridge;
}

export function capabilityAction(name:string):string|undefined {
  if(name.startsWith('browser.'))return name.startsWith('browser.files.')?'developer.browser.transfer':
    /browser\.(trace|cpu|heap|lighthouse)/.test(name)?'developer.browser.diagnostics':'developer.browser';
  if(['read','glob','grep'].includes(name))return 'developer.files.read';
  if(['edit','write','patch'].includes(name))return 'developer.files.write';
  if(name==='shell')return 'developer.shell';
  if(name==='execute')return 'developer.codemode';
  if(['opencode.session_move','opencode.worktree_create','opencode.worktree_list','opencode.worktree_remove'].includes(name))return 'developer.worktree';
  if(['opencode.list_mcp_resources','opencode.read_mcp_resource'].includes(name)||name.startsWith('mcp.'))return 'renulus.mcp';
  return ({question:'renulus.question',skill:'renulus.skill',subagent:'renulus.child',webfetch:'renulus.evidence.fetch',websearch:'renulus.evidence.search',
    'opencode.models':'renulus.models','opencode.session_rename':'renulus.title'} as Record<string,string>)[name];
}
