/** Mirrors integration/runtime/renulus/contracts.py API v1. Domain types belong to their modules. */
export type Scope = 'study' | 'personal-library' | 'temporary-case' | 'saved-case' | 'generated-practice' | 'reviewed-assessment' | 'unclassified';
export interface ContextScope { kind: Scope; entity_id?: string | null }
export interface RunEvent { id: string; run_id: string; sequence: number; type: string; payload: Record<string, unknown> }
export interface Health { status: string; version: string; api_version: number; schema_version: number; modules: Record<string, { status: string }> }
