import type { ContentLocator, ContentReference } from '../../platform/designC';
import type { SavedWorkspaceTab, WorkspaceContext, WorkspaceLayout, WorkspacePreferences, WorkspaceSection, WorkspaceTab } from './types';

export const DEFAULT_WORKSPACE_WIDTH = 480;
export const MIN_WORKSPACE_WIDTH = 360;
export const MAX_WORKSPACE_WIDTH = 640;
export const MIN_CONVERSATION_WIDTH = 528;
const identifier = (value: unknown): value is string => typeof value === 'string' && value.length <= 256 && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value);
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const exact = (value: Record<string, unknown>, fields: string[]) => Object.keys(value).every(key => fields.includes(key));
const integer = (value: unknown, minimum: number): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
const text = (value: unknown, maximum: number, minimum = 0) => typeof value === 'string' && value.length >= minimum && value.length <= maximum;

export function validContext(value: unknown): value is WorkspaceContext {
  if (!record(value) || !exact(value, ['identity', 'retention']) || !record(value.identity)) return false;
  return exact(value.identity, ['type', 'id']) && ['learn_thread', 'case', 'project'].includes(String(value.identity.type)) && identifier(value.identity.id)
    && (value.retention === 'saved' || (value.retention === 'temporary' && value.identity.type !== 'project'));
}
export function validLocator(value: unknown): value is ContentLocator {
  if (!record(value)) return false;
  switch (value.kind) {
    case 'pdf': return exact(value, ['kind', 'physical_page', 'printed_label']) && integer(value.physical_page, 1) && (value.printed_label == null || text(value.printed_label, 80));
    case 'text': return exact(value, ['kind', 'item_ref', 'section', 'start', 'end']) && text(value.item_ref, 256, 1) && (value.section == null || text(value.section, 240)) && integer(value.start, 0) && integer(value.end, 1) && value.end > value.start;
    case 'table': return exact(value, ['kind', 'format', 'sheet_name', 'first_row', 'last_row', 'first_column', 'last_column'])
      && (value.format === 'csv' ? value.sheet_name == null : value.format === 'xlsx' && text(value.sheet_name, 120, 1))
      && integer(value.first_row, 1) && integer(value.last_row, 1) && value.last_row >= value.first_row
      && integer(value.first_column, 1) && integer(value.last_column, 1) && value.last_column >= value.first_column;
    case 'image': return exact(value, ['kind', 'frame', 'bounds']) && integer(value.frame, 1) && (value.bounds == null || (Array.isArray(value.bounds) && value.bounds.length === 4 && value.bounds.every(n => typeof n === 'number' && Number.isFinite(n)) && value.bounds[0] >= 0 && value.bounds[0] < value.bounds[2] && value.bounds[2] <= 1 && value.bounds[1] >= 0 && value.bounds[1] < value.bounds[3] && value.bounds[3] <= 1));
    default: return false;
  }
}
export function validReference(value: unknown): value is ContentReference {
  if (!record(value) || !exact(value, ['target', 'locator']) || !record(value.target)) return false;
  return exact(value.target, ['type', 'id']) && ['library_revision', 'attachment', 'note_revision', 'saved_test_version'].includes(String(value.target.type))
    && identifier(value.target.id) && (value.locator == null || (value.target.type !== 'saved_test_version' && validLocator(value.locator)));
}
export const referenceKey = (reference: ContentReference) => reference.target.type + ':' + reference.target.id;
export const contextKey = (context: WorkspaceContext | null) => context ? context.retention + ':' + context.identity.type + ':' + context.identity.id : 'unscoped';
/** Copy only the accepted fields, so caller mutation/extra properties cannot enter preferences. */
const copy = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
export const boundedWidth = (width: number) => Number.isFinite(width) ? Math.max(MIN_WORKSPACE_WIDTH, Math.min(MAX_WORKSPACE_WIDTH, Math.round(width))) : DEFAULT_WORKSPACE_WIDTH;
export function workspaceLayout(availableWidth: number, preferredWidth: number): WorkspaceLayout {
  const available = Number.isFinite(availableWidth) ? Math.max(0, Math.floor(availableWidth)) : 0;
  if (available < MIN_CONVERSATION_WIDTH + MIN_WORKSPACE_WIDTH) return { mode: 'focused', width: available, maximum: available };
  const maximum = Math.min(MAX_WORKSPACE_WIDTH, available - MIN_CONVERSATION_WIDTH);
  return { mode: 'split', width: Math.min(boundedWidth(preferredWidth), maximum), maximum };
}
interface Space { context: WorkspaceContext | null; tabs: WorkspaceTab[]; selected: string | null; section: WorkspaceSection; width?: number }
export interface WorkspaceState { context: WorkspaceContext | null; spaces: Record<string, Space>; width: number; isOpen: boolean; notice: 'restricted' | 'invalid_reference' | null }
export const emptySpace = (context: WorkspaceContext | null): Space => ({ context, tabs: [], selected: null, section: 'Files' });
export type Action =
  | { type: 'context'; context: WorkspaceContext | null }
  | { type: 'forget'; key: string }
  | { type: 'open'; context: WorkspaceContext | null; reference: ContentReference }
  | { type: 'select'; context: WorkspaceContext | null; key: string }
  | { type: 'close-tab'; context: WorkspaceContext | null; key: string }
  | { type: 'move'; context: WorkspaceContext | null; key: string; delta: -1 | 1 }
  | { type: 'section'; context: WorkspaceContext | null; section: WorkspaceSection }
  | { type: 'position'; context: WorkspaceContext | null; key: string; position: ContentLocator | null }
  | { type: 'scroll'; context: WorkspaceContext | null; key: string; scrollTop: number }
  | { type: 'width'; context: WorkspaceContext | null; width: number }
  | { type: 'visible'; value: boolean }
  | { type: 'notice'; notice: WorkspaceState['notice'] }
  | { type: 'restore'; preferences: WorkspacePreferences };

export function initialState(preferences?: WorkspacePreferences): WorkspaceState {
  const state: WorkspaceState = { context: null, spaces: {}, width: DEFAULT_WORKSPACE_WIDTH, isOpen: false, notice: null };
  return preferences ? reducer(state, { type: 'restore', preferences }) : state;
}
export function reducer(state: WorkspaceState, action: Action): WorkspaceState {
  if (action.type === 'context') return { ...state, context: action.context, notice: null };
  if (action.type === 'forget') { const spaces = { ...state.spaces }; delete spaces[action.key]; return { ...state, spaces }; }
  if (action.type === 'visible') return { ...state, isOpen: action.value, notice: null };
  if (action.type === 'notice') return { ...state, notice: action.notice, isOpen: true };
  if (action.type === 'restore') {
    if (!action.preferences || !Array.isArray(action.preferences.tabs)) return state;
    const spaces = { ...state.spaces };
    for (const row of action.preferences.tabs.slice(0, 100)) {
      if (!record(row) || !exact(row, ['content', 'context', 'retention', 'position'])) continue;
      const context = { identity: row.context, retention: row.retention };
      if (!validContext(context) || context.retention !== 'saved' || !validReference(row.content) || (row.position != null && !validLocator(row.position)) || (row.content.target.type === 'saved_test_version' && row.position != null)) continue;
      const ctx = copy(context); const space = spaces[contextKey(ctx)] ?? emptySpace(ctx); const key = referenceKey(row.content);
      if (space.tabs.some(tab => tab.key === key)) continue;
      spaces[contextKey(ctx)] = { ...space, selected: space.selected ?? key, tabs: [...space.tabs, { key, reference: copy(row.content), position: copy(row.position ?? row.content.locator ?? null), scrollTop: 0, visited: false }] };
    }
    return { ...state, width: boundedWidth(action.preferences.width), spaces };
  }
  const key = contextKey(action.context); const space = state.spaces[key] ?? emptySpace(copy(action.context));
  let next = space;
  switch (action.type) {
    case 'open': {
      const tabKey = referenceKey(action.reference); const existing = space.tabs.find(tab => tab.key === tabKey);
      const tab = existing ? { ...existing, visited: true, ...(action.reference.locator ? { reference: copy(action.reference), position: copy(action.reference.locator) } : {}) } : { key: tabKey, reference: copy(action.reference), position: copy(action.reference.locator ?? null), scrollTop: 0, visited: true };
      next = { ...space, selected: tabKey, tabs: existing ? space.tabs.map(row => row.key === tabKey ? tab : row) : [...space.tabs, tab] }; break;
    }
    case 'select': if (space.tabs.some(tab => tab.key === action.key)) next = { ...space, selected: action.key, tabs: space.tabs.map(tab => tab.key === action.key ? { ...tab, visited: true } : tab) }; break;
    case 'close-tab': { const index = space.tabs.findIndex(tab => tab.key === action.key); const tabs = space.tabs.filter(tab => tab.key !== action.key); next = { ...space, tabs, selected: space.selected === action.key ? (tabs[Math.min(index, tabs.length - 1)]?.key ?? null) : space.selected }; break; }
    case 'move': { const tabs = [...space.tabs]; const index = tabs.findIndex(tab => tab.key === action.key); const target = index + action.delta; if (index >= 0 && target >= 0 && target < tabs.length) { [tabs[index], tabs[target]] = [tabs[target], tabs[index]]; next = { ...space, tabs }; } break; }
    case 'section': next = { ...space, selected: null, section: action.section }; break;
    case 'position': next = { ...space, tabs: space.tabs.map(tab => tab.key === action.key ? { ...tab, position: copy(action.position) } : tab) }; break;
    case 'scroll': next = { ...space, tabs: space.tabs.map(tab => tab.key === action.key ? { ...tab, scrollTop: action.scrollTop } : tab) }; break;
    case 'width': if (action.context?.retention === 'saved') return { ...state, width: boundedWidth(action.width) }; next = { ...space, width: boundedWidth(action.width) }; break;
  }
  return { ...state, spaces: { ...state.spaces, [key]: next }, notice: null, isOpen: action.type === 'open' || action.type === 'section' ? true : state.isOpen };
}
export function savedPreferences(state: WorkspaceState): WorkspacePreferences {
  const tabs: SavedWorkspaceTab[] = [];
  for (const space of Object.values(state.spaces)) {
    if (space.context?.retention !== 'saved' || !validContext(space.context)) continue;
    for (const tab of space.tabs) tabs.push({ content: copy(tab.reference), context: copy(space.context.identity), retention: 'saved', position: copy(tab.position) });
  }
  return { width: state.width, tabs };
}
