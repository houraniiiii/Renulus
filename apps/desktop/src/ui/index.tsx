import { useId, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { AlertCircle, BookOpen, Info } from 'lucide-react';
import { ApiError } from '../platform/api';

export function Button({ variant = 'primary', busy = false, className = '', children, disabled, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; busy?: boolean }) {
  return <button type="button" {...props} disabled={disabled || busy} aria-busy={busy || undefined} className={'button button-' + variant + ' ' + className}>{children}</button>;
}
export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button type="button" {...props} className={'icon-button ' + (props.className ?? '')} aria-label={label} title={label}>{children}</button>;
}
export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return <header className="page-header"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="page-header-actions">{actions}</div>}</header>;
}
export function Panel({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={'panel ' + className}>{children}</section>; }
export function Badge({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'neutral' | 'warning' | 'error' }) { return <span className={'badge badge-' + tone}>{children}</span>; }

interface FieldProps { label: string; hint?: string; error?: string }
export function Input({ label, hint, error, id: inputId, ...props }: InputHTMLAttributes<HTMLInputElement> & FieldProps) {
  const generated = useId(); const id = inputId ?? generated;
  return <div className="field"><label className="field-label" htmlFor={id}>{label}</label><input {...props} id={id} className={'input ' + (props.className ?? '')} aria-invalid={!!error || undefined} aria-describedby={hint || error ? id + '-detail' : undefined} />{(hint || error) && <p id={id + '-detail'} className={error ? 'field-error' : 'field-hint'}>{error ?? hint}</p>}</div>;
}
export function Textarea({ label, hint, error, id: inputId, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement> & FieldProps) {
  const generated = useId(); const id = inputId ?? generated;
  return <div className="field"><label className="field-label" htmlFor={id}>{label}</label><textarea {...props} id={id} className={'textarea ' + (props.className ?? '')} aria-invalid={!!error || undefined} aria-describedby={hint || error ? id + '-detail' : undefined} />{(hint || error) && <p id={id + '-detail'} className={error ? 'field-error' : 'field-hint'}>{error ?? hint}</p>}</div>;
}
export function Select({ label, hint, error, id: inputId, children, ...props }: SelectHTMLAttributes<HTMLSelectElement> & FieldProps) {
  const generated = useId(); const id = inputId ?? generated;
  return <div className="field"><label className="field-label" htmlFor={id}>{label}</label><select {...props} id={id} className={'select ' + (props.className ?? '')} aria-invalid={!!error || undefined} aria-describedby={hint || error ? id + '-detail' : undefined}>{children}</select>{(hint || error) && <p id={id + '-detail'} className={error ? 'field-error' : 'field-hint'}>{error ?? hint}</p>}</div>;
}
export function EmptyState({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return <section className="state"><BookOpen size={28} aria-hidden="true" /><h2>{title}</h2><div>{children}</div>{action}</section>;
}
export function ErrorState({ error, title = 'This could not be loaded', onRetry }: { error: unknown; title?: string; onRetry?: () => void }) {
  const message = error instanceof ApiError ? error.message : 'Renulus could not open this view. Try again.';
  return <section className="state error-state" role="alert"><AlertCircle size={24} aria-hidden="true" /><h2>{title}</h2><p>{message}</p>{onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}</section>;
}
export function Notice({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'warning' }) { return <div className={'notice notice-' + tone} role="status"><Info size={18} aria-hidden="true" /><div>{children}</div></div>; }
export function LoadingState({ label = 'Loading your learning space' }: { label?: string }) { return <div className="skeleton" role="status" aria-label={label}><span className="sr-only">{label}</span>{[0,1,2,3].map(line => <div key={line} className="skeleton-line" aria-hidden="true" />)}</div>; }
