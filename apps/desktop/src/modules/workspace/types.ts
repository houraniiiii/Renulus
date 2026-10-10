import type { ComponentType, ReactNode } from 'react';
import type { AssessmentPolicy, ContentLocator, ContentReference, ConversationIdentity, ReaderProps, Retention } from '../../platform/designC';

export type WorkspaceIdentity = ConversationIdentity | { type: 'project'; id: string };
export interface WorkspaceContext { identity: WorkspaceIdentity; retention: Retention }
export type WorkspaceSection = 'Files' | 'Sources' | 'Notes' | 'Goals';
/** Matches the saved WorkspaceTab contract. Titles, bytes and paths never persist. */
export interface SavedWorkspaceTab {
  content: ContentReference; context: WorkspaceIdentity; retention: 'saved'; position: ContentLocator | null;
}
export interface WorkspacePreferences { width: number; tabs: SavedWorkspaceTab[] }
export interface WorkspaceTab {
  key: string; reference: ContentReference; position: ContentLocator | null; scrollTop: number; visited: boolean;
}
export type WorkspaceOpenResult = 'opened' | 'restricted' | 'invalid_reference';
export type WorkspaceAccessRequest = {
  context: WorkspaceContext | null; policy: AssessmentPolicy;
} & ({ kind: 'content'; reference: ContentReference } | { kind: 'section'; section: WorkspaceSection });
export type WorkspaceAccessDecision = { allowed: true } | { allowed: false; reason: 'restricted' | 'unavailable' | 'not_found' | 'access_denied' };
export type WorkspaceAuthorizer = (request: WorkspaceAccessRequest, signal: AbortSignal) => Promise<WorkspaceAccessDecision>;
export interface WorkspaceProviderProps {
  children: ReactNode;
  context?: WorkspaceContext | null;
  policy: AssessmentPolicy;
  initialPreferences?: WorkspacePreferences;
  /** Parent resolves canonical references and policy at its backend boundary. Missing adapter fails closed. */
  authorize?: WorkspaceAuthorizer;
  onPreferencesChange?: (preferences: WorkspacePreferences) => void;
  onContextChange?: (context: WorkspaceContext | null) => void;
}
export interface WorkspaceReaderProps extends ReaderProps {
  context: WorkspaceContext | null; policy: AssessmentPolicy; signal: AbortSignal;
  position: ContentLocator | null; onPositionChange: (position: ContentLocator | null) => void;
}
export interface SavedTestPreviewProps {
  reference: ContentReference; context: WorkspaceContext | null; policy: AssessmentPolicy; signal: AbortSignal;
}
export interface WorkspaceEntryProps {
  context: WorkspaceContext | null; policy: AssessmentPolicy; signal: AbortSignal;
  open: (reference: ContentReference) => WorkspaceOpenResult;
}
export interface WorkspacePanelProps {
  /** Width of the shell content region AFTER navigation, including chat + workspace. */
  availableWidth: number;
  Reader?: ComponentType<WorkspaceReaderProps>;
  SavedTestPreview?: ComponentType<SavedTestPreviewProps>;
  adapters?: Partial<Record<WorkspaceSection, ComponentType<WorkspaceEntryProps>>>;
  getTitle?: (reference: ContentReference) => string | undefined;
  onPassage?: ReaderProps['onPassage'];
  onReturnToChat?: () => void;
  onResumeTest?: (attemptId: string) => void;
  onLayoutChange?: (layout: WorkspaceLayout) => void;
  className?: string;
}
export interface WorkspaceLayout { mode: 'split' | 'focused'; width: number; maximum: number }
