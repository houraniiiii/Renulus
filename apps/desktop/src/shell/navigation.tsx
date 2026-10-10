import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { ContextScope } from '../platform/contracts';

export const routes = [
  { id: 'newchat', label: 'New chat', module: 'home' },
  { id: 'chat', label: 'Chat', module: 'chat' },
  { id: 'projects', label: 'Projects', module: 'projects' },
  { id: 'tests', label: 'Tests', module: 'tests' },
  { id: 'attempts', label: 'Attempt', module: 'attempts' },
  { id: 'more', label: 'More', module: 'more' },
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
  consumeIntent: (kind: 'sendIntent' | 'passageIntent', id: string) => void;
  startFreshStudy: () => void;
}
const NavigationContext = createContext<Navigation | null>(null);
export function routeFromHash(hash: string): RouteId {
  const name = hash.replace(/^#\/?/, '').split(/[?\/]/)[0];
  if (name === 'home' || name === '') return 'newchat';
  if (name === 'test') return 'assessment';
  return routes.some(route => route.id === name) ? name as RouteId : 'newchat';
}
const savedId = /^[A-Za-z0-9_-]{1,128}$/;
export function savedHandoffFromHash(hash: string): Record<string, unknown> | undefined {
  const parts = hash.replace(/^#[/]?/, '').split('/');
  if (parts[0] === 'chat' && parts.length === 3 && ['learn_thread', 'case'].includes(parts[1]) && savedId.test(parts[2])) {
    return { conversation: { type: parts[1], id: parts[2] }, retention: 'saved' };
  }
  if (parts.length === 2 && savedId.test(parts[1])) {
    if (parts[0] === 'projects') return { project_id: parts[1] };
    if (parts[0] === 'attempts') return { attempt_id: parts[1] };
    if (parts[0] === 'tests') return { version_id: parts[1] };
  }
  return undefined;
}
export function destinationHash(route: RouteId, payload?: Record<string, unknown>): string {
  if (route === 'chat' && payload?.retention === 'saved' && payload.conversation && typeof payload.conversation === 'object') {
    const conversation = payload.conversation as { type?: unknown; id?: unknown };
    if (['learn_thread', 'case'].includes(String(conversation.type)) && typeof conversation.id === 'string' && savedId.test(conversation.id)) return '#/chat/' + conversation.type + '/' + conversation.id;
  }
  const key = route === 'projects' ? 'project_id' : route === 'attempts' ? 'attempt_id' : route === 'tests' ? 'version_id' : undefined;
  const id = key ? payload?.[key] : undefined;
  return '#/' + route + (typeof id === 'string' && savedId.test(id) ? '/' + id : '');
}
export function nextScope(current: ContextScope, route: RouteId, options: NavigationOptions = {}): ContextScope {
  if (options.freshStudy) return { kind: 'study' };
  if (current.kind === 'temporary-case') return options.scope?.kind === 'temporary-case' ? options.scope : current;
  if (current.kind === 'unclassified') return current;
  if (route === 'cases' && !options.scope) return { kind: 'temporary-case' };
  return options.scope ?? current;
}
export function NavigationProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(() => routeFromHash(window.location.hash));
  const [scope, setScope] = useState<ContextScope>(() => ({ kind: route === 'cases' ? 'temporary-case' : 'study' }));
  const [handoff, setHandoff] = useState<Record<string, unknown> | undefined>(() => savedHandoffFromHash(window.location.hash));
  const [revision, setRevision] = useState(0);
  const ownHash = useRef<string | undefined>(undefined);
  function navigate(next: RouteId, options: NavigationOptions = {}) {
    setScope(current => nextScope(current, next, options));
    setHandoff(options.freshStudy ? undefined : options.payload);
    setRoute(next);
    setRevision(value => value + 1);
    // Only validated saved identities enter history; drafts/temporary IDs never do.
    const hash = destinationHash(next, options.payload);
    if (window.location.hash !== hash) { ownHash.current = hash; window.location.hash = hash; }
  }
  useEffect(() => {
    const onHash = () => {
      if (ownHash.current === window.location.hash) { ownHash.current = undefined; return; }
      const next = routeFromHash(window.location.hash);
      setRoute(next);
      setScope(current => nextScope(current, next));
      setHandoff(savedHandoffFromHash(window.location.hash));
      setRevision(value => value + 1);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  function consumeIntent(kind: 'sendIntent' | 'passageIntent', id: string) {
    setHandoff(current => {
      const intent = current?.[kind];
      if (!intent || typeof intent !== 'object') return current;
      const value = intent as { request_id?: unknown; id?: unknown };
      if ((kind === 'sendIntent' ? value.request_id : value.id) !== id) return current;
      const next = { ...current }; delete next[kind]; return next;
    });
  }
  return <NavigationContext.Provider value={{ route, scope, handoff, revision, navigate, consumeIntent, startFreshStudy: () => navigate('study', { freshStudy: true }) }}>{children}</NavigationContext.Provider>;
}
export function useNavigation(): Navigation {
  const context = useContext(NavigationContext);
  if (!context) throw new Error('A module must be mounted inside the Renulus shell.');
  return context;
}
