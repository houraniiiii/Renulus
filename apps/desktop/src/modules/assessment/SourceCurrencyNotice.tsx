import { ArrowRight } from 'lucide-react';
import { useNavigation } from '../../shell/navigation';
import { Button, Notice } from '../../ui';
import type { Item, SessionSourceCurrency, SourceCurrency } from './types';

export function currencySummary(currency?: SessionSourceCurrency): string | null {
  if (!currency) return null;
  const parts: string[] = [];
  if (currency.affected_count) {
    parts.push(`${currency.affected_count} ${currency.affected_count === 1 ? 'question needs' : 'questions need'} source re-review`);
  }
  if (currency.dismissed_count) {
    parts.push(`Dismissed source notices on ${currency.dismissed_count} ${currency.dismissed_count === 1 ? 'question' : 'questions'}`);
  }
  if (currency.state !== 'available') {
    parts.push(currency.state === 'partial' ? 'Some source currency checks unavailable' : 'Source currency check unavailable');
  }
  return parts.length ? parts.join(' · ') : null;
}

export function SessionCurrencyNotice({ currency }: { currency?: SessionSourceCurrency }) {
  const nav = useNavigation();
  const summary = currencySummary(currency);
  if (!summary) return null;
  return <div className="assessment-session-currency">
    <Notice tone={currency?.needs_re_review || currency?.state !== 'available' ? 'warning' : 'default'}>
      <strong>{summary}</strong>
      {!!currency?.pending_affected_count && <p>
        {currency.pending_affected_count} {currency.pending_affected_count === 1 ? 'unanswered question is' : 'unanswered questions are'} affected.
      </p>}
      <p>Pinned questions, keys and recorded scores are retained.</p>
      <Button variant="ghost" onClick={() => nav.navigate('updates')}>View source updates<ArrowRight size={16} /></Button>
    </Notice>
  </div>;
}

export default function SourceCurrencyNotice({ currency, item, committed = false }: {
  currency?: SourceCurrency; item: Item; committed?: boolean;
}) {
  const nav = useNavigation();
  if (!currency || (currency.state === 'available' && !currency.annotations.length)) return null;
  const active = currency.annotations.filter(row => row.state === 'needs-re-review');
  const reviewed = active.length > 0 && active.every(row => row.review_state === 'reviewed');
  const unavailable = currency.state === 'unavailable';
  const title = unavailable ? 'Source currency could not be checked'
    : active.length ? reviewed ? 'Source notice reviewed; question review still needed' : 'Source change needs question review'
      : 'Source notice dismissed';
  return <div className="assessment-source-currency" tabIndex={committed ? undefined : -1}>
    <Notice tone={unavailable || active.length ? 'warning' : 'default'}>
      <strong>{title}</strong>
      <p>Question version {item.question_version} · key {item.key_version} remain pinned.
        {committed && ' Recorded answer and score are retained.'}</p>
      {currency.annotations.length > 0 && <details>
        <summary>Source notice details ({currency.annotations.length})</summary>
        <ul>{currency.annotations.map(row => <li key={row.entry_id + ':' + row.pinned_source_id}>
          <strong>{row.pinned_source_id}</strong>
          <span>{row.state === 'dismissed' ? 'Notice dismissed' : row.review_state === 'reviewed'
            ? 'Notice reviewed · question re-review pending' : 'Awaiting notice review'}</span>
          <span>{row.locators.join('; ')}</span>
          <span>Detected {new Date(row.detected_at).toLocaleDateString()}</span>
        </li>)}</ul>
      </details>}
      <Button variant="ghost" onClick={() => nav.navigate('updates')}>View source updates<ArrowRight size={16} /></Button>
    </Notice>
  </div>;
}
