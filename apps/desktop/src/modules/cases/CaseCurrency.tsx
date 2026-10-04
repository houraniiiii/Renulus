// SPDX-License-Identifier: MIT
import { RefreshCw } from 'lucide-react';
import { Badge, Button, Notice } from '../../ui';
import type { CaseCurrency, TeachingView } from './types';

const statusLabel = (currency?: CaseCurrency) => currency?.status === 'needs-re-review' ? 'Needs re-review' :
  currency?.status === 'no-known-impact' ? 'No recorded source impact' : 'Currency checks unavailable';

export function CaseCurrencyLabel({ currency }: { currency?: CaseCurrency }) {
  return <span className="case-currency-label" data-status={currency?.status ?? 'unavailable'}>{statusLabel(currency)}</span>;
}

export function CaseCurrencyNotice({ teaching, disabled, refreshing, onRefresh, onUpdates }: {
  teaching: TeachingView; disabled: boolean; refreshing: boolean;
  onRefresh: () => void; onUpdates: () => void;
}) {
  const currency = teaching.currency;
  const status = currency?.status ?? 'unavailable';
  return <section className="case-currency" aria-label="Teaching case source currency">
    <Notice tone={status === 'needs-re-review' ? 'warning' : 'default'}>
      <div className="case-currency-heading"><strong>Source currency</strong>
        <Badge tone={status === 'needs-re-review' ? 'warning' : 'neutral'}>{statusLabel(currency)}</Badge></div>
      <p>{status === 'needs-re-review' ?
        'A cited source has a recorded change requiring review of this teaching case.' :
        status === 'no-known-impact' ? 'The installed source check has no recorded impact for this version.' :
        'Recorded source changes could not be checked. Refresh currency to try again.'}</p>
      <p className="muted">Pinned version {teaching.version}. Case stages, discussion and the original content review remain as recorded.</p>
      {status === 'no-known-impact' && <p className="muted">This status does not establish that the case is current.</p>}
      {!!currency?.annotations.length && <details className="case-currency-details"><summary>Source notices ({currency.annotation_count})</summary>
        <ul>{currency.annotations.map((annotation, index) => <li key={annotation.entry_id + '-' + index}>
          <strong>{annotation.title || 'Source change'}</strong>
          <span className="muted">{annotation.state === 'dismissed' ? 'Impact dismissed' : 'Needs re-review'} · {annotation.review_state === 'pending' ?
            'Source review pending' : annotation.review_state === 'reviewed' ? 'Source update reviewed' : 'Source update dismissed'}
            {annotation.detected_at && ' · Detected ' + annotation.detected_at.slice(0, 10)}</span>
        </li>)}</ul>
        {currency.truncated && <p className="muted">Showing {currency.annotations.length} of {currency.annotation_count} notices. Open Updates for the full record.</p>}
      </details>}
      <div className="actions"><Button variant="ghost" disabled={disabled} busy={refreshing} onClick={onRefresh}>
        <RefreshCw size={16} aria-hidden="true" />Refresh currency</Button>
        <Button variant="ghost" onClick={onUpdates}>Open Updates</Button></div>
    </Notice>
  </section>;
}
