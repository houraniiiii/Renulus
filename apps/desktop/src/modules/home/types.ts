import type { ConversationKind } from '../../platform/designC';
import type { createConversation } from '../chat/api';
import type { prepareQuickPractice } from './practice';

export type SuggestionCategory = 'explain' | 'case' | 'practice';
export interface HomePreferences { doctor_name: string | null; revision: number }
export interface HomeState {
  preferences: HomePreferences;
  suggestions: Record<SuggestionCategory, string[]> | null;
  suggestions_date: string | null;
  stale: boolean;
  job: { id: string; state: string; error_code: string | null } | null;
  error_code: string | null;
  assistance_allowed: boolean;
}
export interface HomeIntent { text: string; kind: ConversationKind }
/** These seams retain canonical typed identity; they never target legacy generation. */
export interface HomeAdapters {
  create?: typeof createConversation;
  practice?: typeof prepareQuickPractice;
}
