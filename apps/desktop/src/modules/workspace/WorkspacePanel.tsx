import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ArrowLeft, FileText, Plus, X } from 'lucide-react';
import { Button, IconButton, LoadingState } from '../../ui';
import { useWorkspace } from './WorkspaceProvider';
import { contextKey, MIN_WORKSPACE_WIDTH, workspaceLayout } from './state';
import type { WorkspaceAccessDecision, WorkspaceAccessRequest, WorkspaceAuthorizer, WorkspacePanelProps, WorkspaceTab } from './types';
import './workspace.css';

function AccessGate({ request, authorize, children }: { request: WorkspaceAccessRequest; authorize?: WorkspaceAuthorizer; children: (signal: AbortSignal) => ReactNode }) {
  const stamp = JSON.stringify(request);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{ stamp: string; authorize?: WorkspaceAuthorizer; decision: WorkspaceAccessDecision; signal: AbortSignal } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    if (authorize) {
      void Promise.resolve().then(() => authorize(request, controller.signal)).then(decision => {
        if (!controller.signal.aborted) setResult({ stamp, authorize, decision, signal: controller.signal });
      }).catch(() => {
        if (!controller.signal.aborted) setResult({ stamp, authorize, decision: { allowed: false, reason: 'unavailable' }, signal: controller.signal });
      });
    }
    return () => controller.abort();
    // Stamp keeps unrelated scroll updates from re-authorizing content.
  }, [stamp, authorize, retry]);
  if (!authorize) return <div className="dc-workspace-state" role="status"><h3>Content access is not connected</h3><p>This view needs the local content-access adapter before it can open.</p></div>;
  if (!result || result.stamp !== stamp || result.authorize !== authorize || result.signal.aborted) return <LoadingState label="Checking content access" />;
  if (result.decision.allowed) return children(result.signal);
  const reason = result.decision.reason;
  return <div className="dc-workspace-state" role="status"><h3>{reason === 'not_found' ? 'Content unavailable' : reason === 'unavailable' ? 'Content could not be opened' : 'Content access restricted'}</h3><p>{reason === 'not_found' ? 'The original may have been removed. Keep this reference or close its tab.' : reason === 'unavailable' ? 'Your place is retained. Retry when the local runtime is available.' : 'This operation is not currently permitted. Your tabs are retained.'}</p><Button variant="secondary" onClick={() => { setResult(null); setRetry(value => value + 1); }}>Check again</Button></div>;
}

function TabContent({ tab, selected, children }: { tab: WorkspaceTab; selected: boolean; children: ReactNode }) {
  const element = useRef<HTMLDivElement>(null);
  const workspace = useWorkspace();
  useLayoutEffect(() => { if (selected && element.current) element.current.scrollTop = tab.scrollTop; }, [selected, tab.key]);
  return <div ref={element} role="tabpanel" id={'dc-tabpanel-' + encodeURIComponent(tab.key)} aria-labelledby={'dc-tab-' + encodeURIComponent(tab.key)} hidden={!selected} className="dc-workspace-content" onScroll={event => workspace.setScrollPosition(tab.key, event.currentTarget.scrollTop)}>{children}</div>;
}

export function WorkspacePanel(props: WorkspacePanelProps) {
  const workspace = useWorkspace();
  const { context, policy, authorize, tabs, selectedKey, permitted } = workspace;
  const panelId = useId(); const headingId = useId(); const toolsId = useId();
  const layout = useMemo(() => workspaceLayout(props.availableWidth, workspace.preferredWidth), [props.availableWidth, workspace.preferredWidth]);
  const onLayoutChange = useRef(props.onLayoutChange);
  onLayoutChange.current = props.onLayoutChange;
  useEffect(() => { if (workspace.isOpen) onLayoutChange.current?.(layout); }, [layout, workspace.isOpen]);
  const drag = useRef<{ pointerId: number; x: number; width: number } | null>(null);
  const tabButtons = useRef(new Map<string, HTMLButtonElement>());
  if (!workspace.isOpen) return null;
  const selected = tabs.find(tab => tab.key === selectedKey);
  const title = (tab: WorkspaceTab) => permitted ? (props.getTitle?.(tab.reference) || ({ library_revision: 'Document', attachment: 'Attachment', note_revision: 'Note', saved_test_version: 'Test preview' }[tab.reference.target.type])) : 'Saved tab';
  const close = () => { workspace.close(); props.onReturnToChat?.(); };
  const resize = (width: number) => workspace.setPreferredWidth(Math.max(MIN_WORKSPACE_WIDTH, Math.min(layout.maximum, width)));
  const resizeKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = event.shiftKey ? 50 : 20;
    const width = event.key === 'ArrowLeft' ? layout.width + step : event.key === 'ArrowRight' ? layout.width - step : event.key === 'Home' ? MIN_WORKSPACE_WIDTH : event.key === 'End' ? layout.maximum : event.key === 'Enter' ? Math.min(480, layout.maximum) : null;
    if (width !== null) { event.preventDefault(); resize(width); }
  };
  const tabKeyboard = (event: KeyboardEvent<HTMLButtonElement>, current: string) => {
    const keys = ['tools', ...tabs.map(tab => tab.key)]; const index = keys.indexOf(current);
    const target = event.key === 'ArrowRight' ? keys[(index + 1) % keys.length] : event.key === 'ArrowLeft' ? keys[(index + keys.length - 1) % keys.length] : event.key === 'Home' ? keys[0] : event.key === 'End' ? keys[keys.length - 1] : null;
    if (target) { event.preventDefault(); if (target === 'tools') workspace.showSection('Files'); else workspace.selectTab(target); tabButtons.current.get(target)?.focus(); }
    if (current !== 'tools' && event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) { event.preventDefault(); workspace.moveTab(current, event.key === 'ArrowUp' ? -1 : 1); }
    if (current !== 'tools' && event.key === 'Delete') { event.preventDefault(); const targetKey = keys[index + 1] ?? keys[index - 1] ?? 'tools'; workspace.closeTab(current); tabButtons.current.get(targetKey)?.focus(); }
  };
  const Reader = props.Reader; const Preview = props.SavedTestPreview; const Entry = props.adapters?.[workspace.section];
  return <aside id={panelId} aria-labelledby={headingId} className={'dc-workspace-panel ' + (props.className ?? '')} data-workspace-layout={layout.mode} style={{ width: layout.width }}>
    {layout.mode === 'split' && <div role="separator" aria-label="Workspace width" aria-orientation="vertical" aria-controls={panelId} aria-valuemin={MIN_WORKSPACE_WIDTH} aria-valuemax={layout.maximum} aria-valuenow={layout.width} aria-valuetext={layout.width + ' pixels'} tabIndex={0} className="dc-workspace-splitter" title="Resize workspace. Left/Right changes width; Home/End selects bounds; Enter restores 480 px." onKeyDown={resizeKeyboard} onPointerDown={event => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.focus(); event.currentTarget.setPointerCapture(event.pointerId); drag.current = { pointerId: event.pointerId, x: event.clientX, width: layout.width }; }} onPointerMove={event => { const start = drag.current; if (start?.pointerId === event.pointerId) resize(start.width + start.x - event.clientX); }} onPointerUp={event => { if (drag.current?.pointerId === event.pointerId) { drag.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); } }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }} />}
    <header className="dc-workspace-header"><h2 id={headingId}>{layout.mode === 'focused' && selected && permitted ? title(selected) : 'Workspace'}</h2>{layout.mode === 'focused' ? <Button variant="ghost" onClick={close}><ArrowLeft size={17} aria-hidden="true" />Back to chat</Button> : <IconButton label="Close workspace" onClick={close}><X size={20} aria-hidden="true" /></IconButton>}</header>
    <div role="tablist" aria-label="Workspace tabs" className="dc-workspace-tabs">
      <button ref={node => { if (node) tabButtons.current.set('tools', node); }} type="button" role="tab" id={toolsId} aria-controls={panelId + '-tools'} aria-selected={!selectedKey} tabIndex={selectedKey ? -1 : 0} onKeyDown={event => tabKeyboard(event, 'tools')} onClick={() => workspace.showSection('Files')}>Files</button>
      {tabs.map(tab => <div className="dc-workspace-tab" key={tab.key}><button ref={node => { if (node) tabButtons.current.set(tab.key, node); else tabButtons.current.delete(tab.key); }} type="button" role="tab" id={'dc-tab-' + encodeURIComponent(tab.key)} aria-controls={'dc-tabpanel-' + encodeURIComponent(tab.key)} aria-selected={tab.key === selectedKey} tabIndex={tab.key === selectedKey ? 0 : -1} onClick={() => workspace.selectTab(tab.key)} onKeyDown={event => tabKeyboard(event, tab.key)}>{title(tab)}</button><IconButton label={'Close ' + title(tab) + ' tab'} onClick={() => workspace.closeTab(tab.key)}><X size={14} aria-hidden="true" /></IconButton></div>)}
      <IconButton label="Workspace tools" onClick={() => workspace.showSection('Files')}><Plus size={18} aria-hidden="true" /></IconButton>
    </div>
    {!permitted ? <div className="dc-workspace-state" role="status"><h3>Active Test</h3><p>Sources, notes and chat assistance are unavailable until final submission. Your tab references are retained.</p>{policy.active_test_id && props.onResumeTest && <Button variant="secondary" onClick={() => props.onResumeTest?.(policy.active_test_id!)}>Resume Test</Button>}</div> : <>
      {workspace.notice === 'invalid_reference' && <p className="dc-workspace-notice" role="alert">This content reference is invalid. Open the item from its current conversation, project or Library.</p>}
      <div id={panelId + '-tools'} role="tabpanel" aria-labelledby={toolsId} hidden={!!selectedKey} className="dc-workspace-content">
        <nav aria-label="Workspace tools" className="dc-workspace-tools">{(['Files', 'Sources', 'Notes', 'Goals'] as const).map(section => <Button key={section} variant={workspace.section === section ? 'secondary' : 'ghost'} aria-current={workspace.section === section ? 'page' : undefined} onClick={() => workspace.showSection(section)}>{section}</Button>)}</nav>
        {!selectedKey && (Entry ? <AccessGate request={{ kind: 'section', section: workspace.section, context, policy }} authorize={authorize}>{signal => <Entry context={context} policy={policy} signal={signal} open={workspace.open} />}</AccessGate> : <div className="dc-workspace-state" role="status"><FileText size={24} aria-hidden="true" /><h3>{workspace.section}</h3><p>This view is not connected in this build. Open a document from Library or the current conversation.</p></div>)}
      </div>
      {tabs.filter(tab => tab.visited || tab.key === selectedKey).map(tab => <TabContent key={contextKey(context) + ':' + tab.key} tab={tab} selected={tab.key === selectedKey}><AccessGate request={{ kind: 'content', reference: tab.reference, context, policy }} authorize={authorize}>{signal => tab.reference.target.type === 'saved_test_version' ? (Preview ? <Preview reference={tab.reference} context={context} policy={policy} signal={signal} /> : <div className="dc-workspace-state" role="status"><h3>Test preview is not connected</h3><p>This tab retains the saved test version reference.</p></div>) : (Reader ? <Reader reference={tab.reference} conversation={context?.identity.type === 'project' ? undefined : context?.identity} context={context} policy={policy} signal={signal} position={tab.position} onPositionChange={position => { if (!signal.aborted) workspace.setPosition(tab.key, position); }} onPassage={passage => { if (!signal.aborted) props.onPassage?.(passage); }} /> : <div className="dc-workspace-state" role="status"><h3>Document reader is not connected</h3><p>Your tab and position are retained until its reader is available.</p></div>)}</AccessGate></TabContent>)}
    </>}
  </aside>;
}
