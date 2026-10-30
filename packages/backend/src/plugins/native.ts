// SPDX-License-Identifier: MIT
import type { StorageClient } from '../storage/index.ts';
import { reject } from '../storage/contracts.ts';
import { createWorkerHttp } from '../workers/transport.ts';
import { createCapabilityAuthority } from '../domain/capabilities/authority.ts';
import type { CapabilityEnvelope, CapabilityTransport } from '../domain/capabilities/contracts.ts';
import type { DeveloperRuntime } from '../../../harness/src/developer-plugin.ts';
import type { NativeInputBinding } from '../../../harness/src/host.ts';
import type { NativeCapabilityPorts } from '../../../harness/src/capability-authority.ts';
import { curatedSkills } from './skills.ts';
import type { ToolRegistry } from './registry.ts';
import type { Questions } from './questions.ts';

export interface NativePortOptions {
  storage: StorageClient;
  root: string;
  registry: ToolRegistry;
  questions: Questions;
  mcp?: Pick<import('../domain/capabilities/mcp.ts').McpBridge, 'port' | 'approveMcpTool' | 'permission'>;
  /** Binding of the actual native session (parent USER or admitted child USER). */
  binding(sessionId: string): NativeInputBinding;
  /** Synchronous seal used inside native hooks: admission is open. */
  open(): boolean;
  children?: NativeCapabilityPorts['children'];
  /** Separate developer profile only (BF03). Absent = Off: no developer tool registers and none can be admitted. */
  developer?: DeveloperRuntime;
  /** Broker-backed byte transport for the developer browser tunnels. */
  transport?: Omit<CapabilityTransport, 'http'>;
  worker?: Parameters<typeof createWorkerHttp>[0];
  developerEndpoints?: readonly { host: string; port: number; private_network: boolean }[];
}
const refused = () => reject('capability_transport_unavailable');

/** Doctor native Adapters: `skill`, `question`, `subagent`, `opencode.models`, `opencode.session_rename`.
 * Grants come from the run's current configuration capabilities, never from tool arguments. */
export function createNativePorts(options: NativePortOptions): NativeCapabilityPorts {
  const { storage, registry } = options;
  const skills = curatedSkills(options.root);
  const browser = options.transport ?? { tunnelOpen: refused, tunnelRead: refused, tunnelWrite: refused, tunnelClose: refused };
  const http: CapabilityTransport['http'] = (plan, signal) =>
    createWorkerHttp(options.worker ?? reject('capability_worker_unavailable'))(plan, signal);
  const authority = createCapabilityAuthority({
    storage: { execute: command => storage.command(command) },
    // The canonical admit transaction checks the run's current capabilities, epochs and root closure.
    current: async (_envelope, action) => {
      if (!options.open()) reject('capability_stale');
      if (action.startsWith('developer.')) {
        const grant = options.developer?.grant(action) ?? reject('developer_disabled');
        if (action === 'developer.http') grant.endpoints = (options.developerEndpoints ?? []).map(endpoint => ({ ...endpoint }));
        return grant;
      }
      return { actions: [action], roots: [], endpoints: [], skills: skills.map(skill => String(skill.info.id)),
        max_bytes: 1024 * 1024, expires_at_ms: Date.now() + 299_000 };
    },
    transport: { ...browser, http },
  });
  async function envelope(sessionID: string, call: string): Promise<CapabilityEnvelope> {
    if (!options.open()) reject('capability_stale');
    const binding = options.binding(sessionID);
    const run = await storage.command({ type: 'dispatch.run', runId: binding.operation_id });
    const snapshot = await storage.command({ type: 'dispatch.snapshot' });
    if (!snapshot.effective || !snapshot.admission_open) reject('configuration_not_active');
    return { run_id: run.run_id, root_id: run.root_id, session_id: binding.session_id, call_id: call,
      configuration: snapshot.effective, grant_epoch: snapshot.grant_epoch, fence: run.fence, retention: 'saved',
      mode: options.developer ? 'developer' : 'doctor', depth: run.parent_id === null ? 0 : 1 };
  }
  registry.command('question', options.questions.ask);
  // Native approvals never mint application authority; only explicit direct commands do.
  registry.command('permission', options.mcp?.permission ?? (async () => ({ content: '', metadata: { approved: false } })));
  registry.command('rename', async (input, envelope: CapabilityEnvelope) => {
    const { sessionID, title } = (input ?? {}) as { sessionID?: unknown; title?: unknown };
    if (envelope.depth !== 0 || envelope.retention !== 'saved' || (sessionID !== undefined && sessionID !== envelope.session_id)) reject('rename_scope');
    if (typeof title !== 'string' || !title.trim() || title.trim().length > 200) reject('rename_title_invalid');
    const binding = options.binding(envelope.session_id);
    const run = await storage.command({ type: 'learning.current', runId: binding.operation_id, binding });
    // A proposal only: acceptance is the authenticated rename command with this expected revision.
    return { output: { sessionID: envelope.session_id, title: title.trim() },
      content: JSON.stringify({ status: 'proposal', thread_id: run.receipt.conversation.identity.id, title: title.trim(),
        expected_revision: run.receipt.conversation.revision, requires_explicit_acceptance: true }) };
  });
  return {
    authority, skills, commands: registry.commands, children: options.children,
    mcp: options.mcp?.port.mcp, approveMcpTool: options.mcp?.approveMcpTool,
    developer: options.developer?.ports(authority, envelope),
    resolve: native => envelope(native.sessionID, String(native.id)),
    localCurrent: () => options.open(),
  };
}
