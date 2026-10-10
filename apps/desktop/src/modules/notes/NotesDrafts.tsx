import { createContext, useContext, useRef, type ReactNode } from 'react';
import type { NoteCommand, NoteDraft } from './types';
interface Drafts { notes: Map<string, NoteDraft>; selected: Map<string, string>; commands: Map<string, { current?: NoteCommand }> }
const Context = createContext<Drafts | null>(null);
/** Unsaved text remains in this app window across Workspace tab switches. */
export function NotesDraftProvider({ children }: { children: ReactNode }) {
  const value = useRef<Drafts>({ notes: new Map(), selected: new Map(), commands: new Map() });
  return <Context.Provider value={value.current}>{children}</Context.Provider>;
}
export function useNoteDrafts() {
  const value = useContext(Context);
  if (!value) throw new Error('NotesDraftProvider is required');
  return value;
}
