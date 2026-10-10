import { useEffect, useState } from 'react';
import { api } from '../platform/api';
import { contentKey, studyHelpHeaders, type ContentReference } from '../platform/designC';
import { useWorkspace } from '../modules/workspace';
import { useStudyHelp } from './StudyHelp';

/** Names are current authorized metadata, never saved workspace preferences. */
export function useWorkspaceTitles() {
  const workspace = useWorkspace();
  const help = useStudyHelp();
  const [refresh, setRefresh] = useState(0);
  const [loaded, setLoaded] = useState<{ stamp: string; titles: Record<string, string> }>();
  const references = workspace.tabs.slice(0, 100).map(tab => ({ target: tab.reference.target }));
  const body = JSON.stringify({ references, context: workspace.context, policy: workspace.policy });
  const stamp = JSON.stringify([body, help.context, refresh, workspace.isOpen]);
  useEffect(() => {
    const changed = () => setRefresh(value => value + 1);
    window.addEventListener('renulus:records-changed', changed);
    return () => window.removeEventListener('renulus:records-changed', changed);
  }, []);
  useEffect(() => {
    if (!workspace.permitted || !workspace.isOpen || !references.length) return;
    const controller = new AbortController();
    void api<{ items: { target: ContentReference['target']; title: string }[] }>('/workspace/titles', {
      method: 'POST', body: JSON.parse(body), signal: controller.signal, headers: studyHelpHeaders(help.context), notifyRecordsChanged: false,
    }).then(result => {
      if (controller.signal.aborted) return;
      const requested = new Set(references.map(reference => contentKey(reference.target)));
      const titles: Record<string, string> = {};
      for (const item of result.items) {
        const key = contentKey(item.target);
        if (requested.has(key) && typeof item.title === 'string' && item.title.trim()) titles[key] = item.title;
      }
      setLoaded({ stamp, titles });
    }).catch(() => { /* Unavailable sources retain distinct neutral tab names. */ });
    return () => controller.abort();
  }, [stamp, workspace.permitted]);
  const titles = workspace.permitted && loaded?.stamp === stamp ? loaded.titles : {};
  return (reference: ContentReference) => {
    const key = contentKey(reference.target);
    const index = workspace.tabs.findIndex(tab => contentKey(tab.reference.target) === key);
    const title = titles[key];
    if (title) {
      const duplicates = workspace.tabs.filter(tab => titles[contentKey(tab.reference.target)] === title);
      return duplicates.length > 1 ? title + ' (' + (duplicates.findIndex(tab => contentKey(tab.reference.target) === key) + 1) + ')' : title;
    }
    return ({ library_revision: 'Document', attachment: 'Attachment', note_revision: 'Note', saved_test_version: 'Test preview' }[reference.target.type]) + ' ' + (index + 1);
  };
}
