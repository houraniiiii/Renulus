import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import type { StudyHelpContext } from '../platform/designC';
import { useNavigation } from './navigation';

const StudyHelp = createContext<{ context?: StudyHelpContext; setContext: (context?: StudyHelpContext) => void } | null>(null);
/** This receipt lives only in React memory; Workspace preferences never receive it. */
export function StudyHelpProvider({ children }: { children: ReactNode }) {
  const navigation = useNavigation();
  const [context, setContext] = useState<StudyHelpContext>();
  useEffect(() => {
    if (navigation.route !== 'attempts' && !(navigation.route === 'chat' && navigation.handoff?.studyHelpContext)) setContext(undefined);
  }, [navigation.route, navigation.revision]);
  return <StudyHelp.Provider value={{ context, setContext }}>{children}</StudyHelp.Provider>;
}
export function useStudyHelp() {
  const value = useContext(StudyHelp);
  if (!value) throw new Error('StudyHelpProvider is required.');
  return value;
}
