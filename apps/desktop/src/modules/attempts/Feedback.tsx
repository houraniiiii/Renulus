import { Badge } from '../../ui';
import type { Commitment } from './types';

export default function Feedback({ entry }: { entry: Commitment }) {
  const text = (ids: string[]) => entry.question.options.filter(option => ids.includes(option.id)).map(option => option.text).join('; ') || 'No answer';
  return <section className="attempt-feedback" aria-label="Locked feedback"><div className="attempt-meta">
    <Badge tone={entry.correct ? 'default' : 'warning'}>{entry.outcome === 'excluded' ? 'Excluded from score' : entry.correct ? 'Correct' : 'Review this answer'}</Badge>
    <span>{entry.assisted ? 'Assisted' : 'Unassisted'} · {entry.repeat ? 'Previously seen' : 'First presentation'} · {entry.score_bucket === 'personal' ? 'Personal practice' : 'Reviewed bank'}</span>
  </div><dl><div><dt>Your committed answer</dt><dd>{text(entry.selected_option_ids)}</dd></div>
    {entry.outcome !== 'excluded' && <div><dt>Answer for this version</dt><dd>{text(entry.feedback.correct_option_ids)}</dd></div>}</dl>
    <p className="attempt-explanation">{entry.feedback.explanation}</p><p className="muted">This answer is locked.</p></section>;
}
