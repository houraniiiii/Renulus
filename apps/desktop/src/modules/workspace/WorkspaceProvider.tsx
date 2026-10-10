import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef } from 'react';
import type { ContentLocator, ContentReference } from '../../platform/designC';
import { contextKey, emptySpace, initialState, reducer, savedPreferences, validContext, validLocator, validReference } from './state';
import type { WorkspaceContext, WorkspaceOpenResult, WorkspacePreferences, WorkspaceProviderProps, WorkspaceSection } from './types';

function useController(props: WorkspaceProviderProps) {
  const [state, dispatch] = useReducer(reducer, props.initialPreferences, initialState);
  const context = props.context === undefined ? state.context : (validContext(props.context) ? props.context : null);
  const key = contextKey(context); const space = state.spaces[key] ?? emptySpace(context);
  const permitted = props.policy.assistance_allowed && props.policy.active_test_id === null;
  const boundary = key + ':' + props.policy.revision + ':' + permitted;
  const currentBoundary = useRef(boundary);
  currentBoundary.current = boundary;
  const previousContext = useRef(context);
  useEffect(() => {
    const previous = previousContext.current;
    if (contextKey(previous) !== key && previous?.retention !== 'saved') dispatch({ type: 'forget', key: contextKey(previous) });
    previousContext.current = context;
  }, [key, context]);
  const snapshot = useMemo(() => savedPreferences(state), [state]);
  const signature = JSON.stringify(snapshot);
  const lastSnapshot = useRef(signature);
  useEffect(() => {
    if (signature === lastSnapshot.current) return;
    lastSnapshot.current = signature;
    props.onPreferencesChange?.(snapshot);
  }, [signature, snapshot, props.onPreferencesChange]);
  const open = useCallback((reference: ContentReference): WorkspaceOpenResult => {
    if (currentBoundary.current !== boundary) return 'restricted';
    if (!validReference(reference)) { dispatch({ type: 'notice', notice: 'invalid_reference' }); return 'invalid_reference'; }
    if (!permitted) { dispatch({ type: 'notice', notice: 'restricted' }); return 'restricted'; }
    dispatch({ type: 'open', context, reference: JSON.parse(JSON.stringify(reference)) as ContentReference }); return 'opened';
  }, [context, permitted, boundary]);
  return {
    context, policy: props.policy, authorize: props.authorize, permitted, isOpen: state.isOpen, notice: state.notice,
    tabs: space.tabs, selectedKey: space.selected, section: space.section, preferredWidth: space.width ?? state.width,
    open,
    close: () => dispatch({ type: 'visible', value: false }),
    toggle: () => dispatch({ type: 'visible', value: !state.isOpen }),
    setContext: (next: WorkspaceContext | null) => {
      if (next !== null && !validContext(next)) return;
      dispatch({ type: 'context', context: next === null ? null : JSON.parse(JSON.stringify(next)) as WorkspaceContext }); props.onContextChange?.(next);
    },
    selectTab: (tabKey: string) => dispatch({ type: 'select', context, key: tabKey }),
    closeTab: (tabKey: string) => dispatch({ type: 'close-tab', context, key: tabKey }),
    moveTab: (tabKey: string, delta: -1 | 1) => dispatch({ type: 'move', context, key: tabKey, delta }),
    showSection: (section: WorkspaceSection) => dispatch({ type: 'section', context, section }),
    setPreferredWidth: (width: number) => dispatch({ type: 'width', context, width }),
    setPosition: (tabKey: string, position: ContentLocator | null) => {
      if (currentBoundary.current !== boundary) return;
      const tab = space.tabs.find(row => row.key === tabKey);
      if (!tab || (position !== null && (!validLocator(position) || tab.reference.target.type === 'saved_test_version'))) return;
      dispatch({ type: 'position', context, key: tabKey, position: position === null ? null : JSON.parse(JSON.stringify(position)) as ContentLocator });
    },
    setScrollPosition: (tabKey: string, scrollTop: number) => {
      if (Number.isFinite(scrollTop) && scrollTop >= 0) dispatch({ type: 'scroll', context, key: tabKey, scrollTop });
    },
    restorePreferences: (preferences: WorkspacePreferences) => dispatch({ type: 'restore', preferences }),
    getPreferences: () => snapshot,
  };
}
export type WorkspaceController = ReturnType<typeof useController>;
const Workspace = createContext<WorkspaceController | null>(null);
export function WorkspaceProvider(props: WorkspaceProviderProps) {
  const controller = useController(props);
  return <Workspace.Provider value={controller}>{props.children}</Workspace.Provider>;
}
export function useWorkspace(): WorkspaceController {
  const value = useContext(Workspace);
  if (!value) throw new Error('WorkspaceProvider is required.');
  return value;
}
