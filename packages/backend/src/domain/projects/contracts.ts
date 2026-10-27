// SPDX-License-Identifier: MIT
export interface GoalInput { title: string; topic_id: string | null; target_date: string | null; status: 'active' | 'completed';
  progress: { evidence_ids: string[]; manual_intent: string | null } }
export type ProjectCommand =
  | { type: 'project.list'; limit: number; cursor: string | null; lifecycle: 'active' | 'archived' }
  | { type: 'project.get'; projectId: string }
  | { type: 'project.create'; title: string; idempotencyKey: string }
  | { type: 'project.change'; projectId: string; expectedRevision: number; action: 'rename' | 'archive' | 'restore' | 'delete'; title: string | null; idempotencyKey: string }
  | { type: 'project.document'; projectId: string; expectedRevision: number; revisionId: string; position: number; action: 'link' | 'unlink'; idempotencyKey: string }
  | { type: 'project.find'; query: string; lifecycle: 'active' | 'archived' | 'all'; projectId: string | null; after: string | null; limit: number; epoch: string | null }
  | { type: 'project.goal'; projectId: string; expectedRevision: number; goalId: string | null; goalRevision: number | null;
      action: 'save' | 'delete'; input: GoalInput | null; idempotencyKey: string };
export type ProjectView = Record<string, unknown>;
export interface ProjectResults { 'project.list': { items: ProjectView[]; next_cursor: string | null }; 'project.get': ProjectView;
  'project.create': ProjectView; 'project.change': ProjectView; 'project.document': ProjectView; 'project.goal': ProjectView;
  'project.find': { items: { id: string; title: string; lifecycle: string }[]; next: string | null; epoch: string } }
export interface ProjectStorage { command<C extends ProjectCommand>(command: C): Promise<ProjectResults[C['type']]> }
