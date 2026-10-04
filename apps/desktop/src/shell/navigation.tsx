import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { ContextScope } from '../platform/contracts';

export const routes = [
  { id: 'study', label: 'Today', module: 'study' },
  { id: 'learn', label: 'Learn', module: 'learn' },
  { id: 'library', label: 'Library', module: 'library' },
  { id: 'cases', label: 'Cases', module: 'cases' },
  { id: 'assessment', label: 'Test', module: 'assessment' },
  { id: 'memory', label: 'Memory', module: 'memory' },
  { id: 'updates', label: 'Updates', module: 'updates' },
  { id: 'connections', label: 'Connections', module: 'connections' },
] as const;
export type RouteId = typeof routes[number]['id'];
export interface NavigationOptions { scope?: ContextScope; payload?: Record<string, unknown>; freshStudy?: boolean }
export interface Navigation {
  route: RouteId;
  scope: ContextScope;
  /** Volatile handoff only. Never add this object to a URL, logs or browser storage. */
  handoff?: Record<string, unknown>;
  revision: number;
  navigate: (route: RouteId, options?: NavigationOptions) => void;
  startFreshStudy: () => void;
}
const NavigationContext = createContext<Navigation | null>(null);
export function routeFromHash(hash: string): RouteId {
  const name = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  if (name === 'home' || name === '') return 'study';
  if (name === 'test') return 'assessment';
  return routes.some(route => route.id === name) ? name as RouteId : 'study';
}
export function nextScope(current: ContextScope, route: RouteId, options: NavigationOptions = {}): ContextScope {
  if (options.freshStudy) return { kind: 'study' };
  if (current.kind === 'temporary-case' || current.kind === 'unclassified') return current;
  if (route === 'cases' && !options.scope) return { kind: 'temporary-case' };
  return options.scope ?? current;
}
export function NavigationProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(() => routeFromHash(window.location.hash));
  const [scope, setScope] = useState<ContextScope>(() => ({ kind: route === 'cases' ? 'temporary-case' : 'study' }));
  const [handoff, setHandoff] = useState<Record<string, unknown>>();
  const [revision, setRevision] = useState(0);
  const ownHash = useRef<string | undefined>(undefined);
  function navigate(next: RouteId, options: NavigationOptions = {}) {
    setScope(current => nextScope(current, next, options));
    setHandoff(options.freshStudy ? undefined : options.payload);
    setRoute(next);
    setRevision(value => value + 1);
    // Only a public destination enters history; payload and scope remain volatile.
    const hash = '#/' + next;
    if (window.location.hash !== hash) { ownHash.current = hash; window.location.hash = '/' + next; }
  }
  useEffect(() => {
    const onHash = () => {
      if (ownHash.current === window.location.hash) { ownHash.current = undefined; return; }
      const next = routeFromHash(window.location.hash);
      setRoute(next);
      setScope(current => nextScope(current, next));
      setHandoff(undefined);
      setRevision(value => value + 1);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return <NavigationContext.Provider value={{ route, scope, handoff, revision, navigate, startFreshStudy: () => navigate('study', { freshStudy: true }) }}>{children}</NavigationContext.Provider>;
}
export function useNavigation(): Navigation {
  const context = useContext(NavigationContext);
  if (!context) throw new Error('A module must be mounted inside the Renulus shell.');
  return context;
}
