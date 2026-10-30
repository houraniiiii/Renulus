// SPDX-License-Identifier: MIT
import type { Plugin } from '@opencode/plugin/effect/plugin';
import type { Tool } from '@opencode/schema/tool';
import type { CapabilityEnvelope } from '../domain/capabilities/contracts.ts';

/** Adapted native tools whose execution the application owns (spec section 4). */
export type NativeCommandName = 'question' | 'permission' | 'rename' | 'evidence.fetch' | 'evidence.search';
export type NativeCommand = (input: unknown, envelope: CapabilityEnvelope, signal: AbortSignal) => Promise<Tool.Result>;

/** Native permission each adapted tool checks (the grant the run's configuration must list). */
const COMMAND_PERMISSION: Record<string, string> = { question: 'renulus.question', rename: 'renulus.title',
  'evidence.fetch': 'renulus.evidence.fetch', 'evidence.search': 'renulus.evidence.search' };

/** The one place trusted tools join the native registry of the connected target. */
export function createToolRegistry() {
  const entries: { plugin: Plugin; permissions: readonly string[] }[] = [];
  const commands: Partial<Record<NativeCommandName, NativeCommand>> = {};
  return {
    /** Register a trusted `renulus_*` tool plugin and the native permission IDs it checks. */
    add(plugin: Plugin, permissions: readonly string[]) { entries.push({ plugin, permissions }); },
    /** Provide the application execution of an adapted native tool (`websearch`, `question`, ...). */
    command(name: NativeCommandName, run: NativeCommand) { commands[name] = run; },
    plugins: () => entries.map(entry => entry.plugin),
    permissions: () => [...new Set([...entries.flatMap(entry => entry.permissions),
      ...Object.keys(commands).flatMap(name => COMMAND_PERMISSION[name] ?? [])])],
    commands,
  };
}
export type ToolRegistry = ReturnType<typeof createToolRegistry>;
