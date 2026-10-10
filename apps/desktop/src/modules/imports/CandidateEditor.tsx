import { useEffect, useState } from 'react';
import { Badge, Button, Input, Notice, Textarea } from '../../ui';
import { keyLabel, type ImportCandidate, type ImportOption } from './types';

interface Props {
  candidate: ImportCandidate; ordinal: number; locked: boolean; immutable: boolean;
  onDirty: (dirty: boolean) => void;
  onEdit: (value: { stem: string; options: ImportOption[]; explanation: string; topic_id: string }, done: () => void) => void;
  onResolve: (keys: string[]) => void; onVisibility: (removed: boolean) => void;
}

// Question text leads on the medical paper surface; restrained teal marks the
// explicit review action. Border separation, Source Sans and 4px spacing match C.
export default function CandidateEditor({ candidate, ordinal, locked, immutable, onDirty, onEdit, onResolve, onVisibility }: Props) {
  const [stem, setStem] = useState(candidate.stem), [options, setOptions] = useState(candidate.options);
  const [explanation, setExplanation] = useState(candidate.explanation);
  const [dirty, setDirty] = useState(false), [keys, setKeys] = useState(candidate.correct_option_ids);
  const [confirmed, setConfirmed] = useState(false);
  const snapshot = JSON.stringify(candidate);
  useEffect(() => {
    if (!dirty) { setStem(candidate.stem); setOptions(candidate.options); setExplanation(candidate.explanation);
      setKeys(candidate.correct_option_ids); setConfirmed(false); }
  // An equal server refresh must not clear a locally selected answer/review.
  }, [snapshot, dirty]);
  function changed() { setDirty(true); onDirty(true); setConfirmed(false); }
  function discard() { setDirty(false); onDirty(false); }
  const disabled = locked || immutable || candidate.removed;
  return <section className="import-question" aria-label={'Question ' + ordinal}>
    <div className="import-heading"><h3>Question {ordinal}</h3><Badge tone={!candidate.review_confirmed && !candidate.removed ? 'warning' : 'neutral'}>{keyLabel(candidate)}</Badge></div>
    {candidate.removed && <Notice>This question stays in the private original but is excluded from the saved set.</Notice>}
    <Textarea label="Question text" rows={4} value={stem} maxLength={6000} disabled={disabled}
      onChange={event => { setStem(event.target.value); changed(); }} />
    <fieldset className="import-options" disabled={disabled}><legend>Options and correct answers</legend>
      {options.map((option, index) => <div className="import-option" key={option.id}>
        <label className="import-check"><input type="checkbox" aria-label={'Correct answer ' + option.id.toUpperCase()}
          checked={keys.includes(option.id)} disabled={disabled || dirty}
          onChange={event => { setKeys(current => event.target.checked ? [...current, option.id] : current.filter(key => key !== option.id)); setConfirmed(false); }} />
          <span>{option.id.toUpperCase()}</span></label>
        <Input label={'Option ' + option.id.toUpperCase()} value={option.text} required maxLength={2000} disabled={disabled}
          onChange={event => { setOptions(current => current.map((value, position) => position === index ? { ...value, text: event.target.value } : value)); changed(); }} />
      </div>)}
    </fieldset>
    <Textarea label="Personal explanation (optional)" value={explanation} rows={2} maxLength={6000} disabled={disabled}
      onChange={event => { setExplanation(event.target.value); changed(); }} />
    {dirty && <div className="import-edit-actions"><p>Save your edits before resolving the answer. Editing requires a new review.</p>
      <div className="actions"><Button disabled={disabled || !stem.trim() || options.some(option => !option.text.trim())}
        onClick={() => onEdit({ stem, options, explanation, topic_id: candidate.topic_id }, discard)}>Save edits</Button>
        <Button variant="ghost" disabled={locked} onClick={discard}>Discard unsaved edits</Button></div></div>}
    {!immutable && !candidate.removed && <div className="import-resolution">
      {(candidate.key_state === 'missing' || candidate.key_state === 'ambiguous') && <Notice tone="warning">{candidate.edited
        ? 'Your edit requires a new answer review. Select the correct answers and confirm them against the unchanged original.'
        : candidate.key_state === 'missing'
        ? 'The original supplies no clear answer. Choose only answers you can personally resolve.'
        : 'The original supplies conflicting answers. Resolve the conflict against the original.'}</Notice>}
      <label className="import-check"><input type="checkbox" checked={confirmed} disabled={disabled || dirty}
        onChange={event => setConfirmed(event.target.checked)} />I checked this question and chosen answers against the original</label>
      <div className="actions"><Button disabled={disabled || dirty || !confirmed || keys.length === 0} onClick={() => onResolve(keys)}>Confirm answer and review</Button>
        <Button variant="ghost" disabled={locked || dirty} onClick={() => onVisibility(true)}>Remove from set</Button></div>
    </div>}
    {!immutable && candidate.removed && <Button variant="secondary" disabled={locked} onClick={() => onVisibility(false)}>Restore to set</Button>}
  </section>;
}
