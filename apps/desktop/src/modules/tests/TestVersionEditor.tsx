import { useState } from 'react';
import { api } from '../../platform/api';
import { useResource } from '../../platform/useResource';
import { Button, ErrorState, LoadingState, Notice, Select, Textarea } from '../../ui';
import { useTestMutation } from './useTestMutation';
import type { PreviewItem, TestSetup } from './types';

interface EditedItem extends PreviewItem { correct_option_ids: string[]; key_version: string | null; explanation: string }

export default function TestVersionEditor({ setup, onSaved }: { setup: TestSetup; onSaved: () => void }) {
  const path = '/assessment/tests/' + encodeURIComponent(setup.test.id);
  const { resource, retry } = useResource(signal => api<{ items: PreviewItem[] }>(path + '/versions/' + encodeURIComponent(setup.version.id) + '/preview', { signal }));
  const [drafts, setDrafts] = useState<EditedItem[] | null>(null), mutation = useTestMutation();
  if (resource.status === 'loading') return <LoadingState label="Opening a personal copy" />;
  if (resource.status === 'error') return <ErrorState error={resource.error} onRetry={retry} />;
  const items = drafts ?? resource.data.items.map(item => ({ ...item, correct_option_ids: [], key_version: null, explanation: '' }));
  function update(index: number, patch: Partial<EditedItem>) { setDrafts(items.map((item, ordinal) => ordinal === index ? { ...item, ...patch } : item)); }
  return <form className="test-editor section" onSubmit={event => { event.preventDefault(); mutation.mutate(path + '/versions', 'POST', {
    expected_revision: setup.test.revision, base_version_id: setup.version.id, items }, onSaved); }}>
    <h3>Edit a personal version</h3>
    <Notice>Each save creates a new version. Original keys are not disclosed here. Supply a personal key for every item, or keep the set in Needs review.</Notice>
    {items.map((item, index) => <fieldset key={item.item_id} disabled={mutation.locked}>
      <legend>Question {index + 1}</legend>
      <Textarea label="Question text" value={item.stem} required maxLength={6000} onChange={event => update(index, { stem: event.target.value })} />
      <ul>{item.options.map(option => <li key={option.id}>{option.id}. {option.text}</li>)}</ul>
      <Select label="Personal answer key" value={item.correct_option_ids[0] ?? ''} onChange={event => update(index, {
        correct_option_ids: event.target.value ? [event.target.value] : [], key_version: event.target.value ? '1' : null })}>
        <option value="">Unresolved — needs review</option>{item.options.map(option => <option key={option.id} value={option.id}>{option.id}. {option.text}</option>)}
      </Select>
      <Textarea label="Personal explanation (optional)" value={item.explanation} maxLength={6000} onChange={event => update(index, { explanation: event.target.value })} />
      <Button variant="ghost" disabled={items.length <= 1} onClick={() => setDrafts(items.filter((_, ordinal) => ordinal !== index))}>Remove question</Button>
    </fieldset>)}
    {mutation.error !== null && <ErrorState error={mutation.error} onRetry={mutation.retry} />}
    <Button type="submit" disabled={mutation.locked} busy={mutation.busy}>Save personal version</Button>
  </form>;
}
