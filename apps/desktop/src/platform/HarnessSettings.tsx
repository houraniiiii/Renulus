import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ChevronDown } from 'lucide-react';
import { api, apiResponse, ApiError, isCancelled } from './api';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, Select } from '../ui';
import './HarnessSettings.css';

export interface HarnessRolePolicy {
  purpose: string; enabled: boolean; model_id: string | null; output_tokens: number; dispatch_limit: number | null;
}
export interface HarnessConfiguration {
  roles: HarnessRolePolicy[];
  attempts: { foreground_dispatches: number; standalone_dispatches: number; title_dispatches: number; retries: number };
}
export interface HarnessConfigurationStatus {
  requested: string | null; effective: string | null; failed: string | null; failure_code: string | null;
  admission_open: boolean; configuration: HarnessConfiguration | null; requested_configuration: HarnessConfiguration | null;
  pinned_runs: Array<{ run_id: string; purpose: string; version: string }>; catalogue: string[];
}
const path = '/runtime/harness/configuration';
const purposeNames: Record<string, string> = {
  explain: 'Explain a topic', 'case-discuss': 'Case discussion', 'case-image-discuss': 'Image case discussion',
  'evidence-review': 'Evidence review', 'generated-practice': 'Generated practice', 'fictional-test': 'Fictional test',
  'test-import': 'Test import', 'memory-extraction': 'Learning memory', compaction: 'Context compaction',
  summary: 'Summary', 'test-result-narrative': 'Test result explanation', daily_suggestions: 'Daily suggestions',
  'updates-digest': 'Updates digest', title: 'Title',
};
const standalone = new Set(['memory-extraction', 'compaction', 'summary', 'test-result-narrative', 'daily_suggestions', 'updates-digest']);
type RoleDraft = Omit<HarnessRolePolicy, 'output_tokens' | 'dispatch_limit'> & { output_tokens: string; dispatch_limit: string };
function wholeNumber(value: string, minimum: number, maximum: number) {
  return value !== '' && Number.isInteger(Number(value)) && Number(value) >= minimum && Number(value) <= maximum;
}
function RoleSettings({ configuration, catalogue, busy, staging, canStage, stage }: {
  configuration: HarnessConfiguration; catalogue: string[]; busy: boolean; staging: boolean; canStage: boolean;
  stage: (roles: HarnessRolePolicy[]) => Promise<void>;
}) {
  const [initial] = useState(() => Object.keys(purposeNames).map(purpose => {
    const policy = configuration.roles.find(role => role.purpose === purpose) ?? { purpose, enabled: purpose !== 'title', model_id: null, output_tokens: 4096, dispatch_limit: null };
    return { ...policy, output_tokens: String(policy.output_tokens), dispatch_limit: policy.dispatch_limit === null ? '' : String(policy.dispatch_limit) };
  }));
  const [roles, setRoles] = useState<RoleDraft[]>(initial);
  const dirty = JSON.stringify(roles) !== JSON.stringify(initial);
  const valid = roles.every(role => (role.model_id === null || catalogue.includes(role.model_id)) && wholeNumber(role.output_tokens, 1, 32768) && (role.dispatch_limit === '' || wholeNumber(role.dispatch_limit, 0, 128)));
  function change(purpose: string, update: Partial<RoleDraft>) { setRoles(rows => rows.map(row => row.purpose === purpose ? { ...row, ...update } : row)); }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canStage || busy || !dirty || !valid) return;
    await stage(roles.map(role => ({ ...role, output_tokens: Number(role.output_tokens), dispatch_limit: role.dispatch_limit === '' ? null : Number(role.dispatch_limit) })));
  }
  return <form className="harness-role-settings" onSubmit={submit}>
    <div className="section"><h3>Role settings</h3><p>These settings prepare a candidate revision. Models inherit your existing learning selection unless you choose an allowed override.</p>
      <p className="muted">The shared foreground allowance is {configuration.attempts.foreground_dispatches} dispatches. Tool continuations and retries also count. Role limits apply within the owning run’s allowance; output is further bounded by the route. Disabled roles do not dispatch, even with a model override.</p></div>
    <div className="harness-roles">{roles.map(role => {
      const name = purposeNames[role.purpose];
      const defaultLimit = role.purpose === 'title' ? configuration.attempts.title_dispatches : standalone.has(role.purpose) ? configuration.attempts.standalone_dispatches : configuration.attempts.foreground_dispatches;
      return <details className="harness-role" key={role.purpose}>
        <summary><strong>{name}</strong><Badge tone={role.enabled ? 'neutral' : 'warning'}>{role.enabled ? 'Enabled' : 'Disabled'}</Badge><span className="harness-role-model muted">{role.model_id ?? 'Inherit selected model'}</span><ChevronDown size={16} aria-hidden="true" /></summary>
        <fieldset disabled={busy} className="harness-role-fields"><legend className="sr-only">{name} settings</legend>
          <label className="harness-role-enable"><input type="checkbox" checked={role.enabled} onChange={event => change(role.purpose, { enabled: event.target.checked })} />Enable {name}</label>
          <Select label={name + ' model'} value={role.model_id ?? ''} error={role.model_id && !catalogue.includes(role.model_id) ? 'Choose inheritance or a model from the current allowed catalogue.' : undefined} onChange={event => change(role.purpose, { model_id: event.target.value || null })}>
            <option value="">Inherit selected model</option>{catalogue.map(model => <option key={model} value={model}>{model}</option>)}
            {role.model_id && !catalogue.includes(role.model_id) && <option value={role.model_id} disabled>{role.model_id} · no longer allowed</option>}
          </Select>
          <Input label={name + ' output tokens'} type="number" min={1} max={32768} step={1} required value={role.output_tokens} error={!wholeNumber(role.output_tokens, 1, 32768) ? 'Use a whole number from 1 to 32768.' : undefined} onChange={event => change(role.purpose, { output_tokens: event.target.value })} />
          <Input label={name + ' dispatch limit'} type="number" min={0} max={128} step={1} value={role.dispatch_limit} error={role.dispatch_limit !== '' && !wholeNumber(role.dispatch_limit, 0, 128) ? 'Use a whole number from 0 to 128, or leave blank.' : undefined} placeholder={'Default · ' + defaultLimit} hint={'Leave blank for the purpose default (' + defaultLimit + '). Zero blocks dispatch.'} onChange={event => change(role.purpose, { dispatch_limit: event.target.value })} />
        </fieldset>
      </details>;
    })}</div>
    <div className="actions"><Button type="submit" disabled={!dirty || !valid || !canStage || busy} busy={staging}>Stage role settings</Button><span className="muted">{dirty ? 'Unstaged changes' : 'Matches the displayed revision'}</span></div>
  </form>;
}
function Revision({ value }: { value: string | null }) {
  return value ? <span className="harness-revision" title={value}>{value.slice(0, 12)}</span> : <span className="muted">None</span>;
}

export function HarnessSettings() {
  const [snapshot, setSnapshot] = useState<HarnessConfigurationStatus | null>(null);
  const [busy, setBusy] = useState<'refresh' | 'stage' | 'activate' | null>(null);
  const [error, setError] = useState<unknown>();
  const [fresh, setFresh] = useState(false);
  const operation = useRef<AbortController | null>(null);
  async function read(signal: AbortSignal) {
    try {
      const data = await api<HarnessConfigurationStatus>(path, { signal });
      if (!signal.aborted) { setSnapshot(data); setFresh(true); }
    } catch (problem) { if (!signal.aborted && !isCancelled(problem)) { setError(problem); setFresh(false); } }
  }
  async function refresh() {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setBusy('refresh'); setError(undefined); setFresh(false);
    await read(controller.signal);
    if (!controller.signal.aborted) { operation.current = null; setBusy(null); }
  }
  useEffect(() => { void refresh(); return () => { operation.current?.abort(); operation.current = null; }; }, []);
  async function mutate(kind: 'stage' | 'activate', body: { roles: HarnessRolePolicy[] } | { version: string }) {
    if (operation.current) return;
    const controller = new AbortController(); operation.current = controller;
    setBusy(kind); setError(undefined); setFresh(false);
    try { await apiResponse(path + (kind === 'activate' ? '/activate' : ''), { method: 'POST', body, signal: controller.signal }); }
    catch (problem) { if (!controller.signal.aborted && !isCancelled(problem)) setError(problem); }
    if (!controller.signal.aborted) await read(controller.signal);
    if (!controller.signal.aborted) { operation.current = null; setBusy(null); }
  }
  const candidate = snapshot?.requested_configuration ?? snapshot?.configuration;
  return <section className="harness-settings" aria-label="Harness settings">
    <header className="section"><h2>Harness settings</h2><p>Inspect the configuration used for learning and prepare a new revision.</p></header>
    {!snapshot && !error && <LoadingState label="Loading harness configuration" />}
    {error !== undefined && <ErrorState error={error} title="Harness configuration could not be updated" onRetry={!busy ? () => void refresh() : undefined} />}
    {snapshot && <>
      <section aria-label="Configuration revisions" aria-live="polite">
        <Badge tone={fresh && snapshot.effective && snapshot.admission_open ? 'default' : 'warning'}>{!fresh ? busy ? 'Checking configuration status' : 'Status needs refreshing' : snapshot.effective && snapshot.admission_open ? 'Open for new runs' : 'New runs paused'}</Badge>
        {!fresh && <p className="muted">Last reported revisions. Refresh status before staging or activating.</p>}
        <dl className="harness-revisions">
          <div><dt>Effective revision</dt><dd><Revision value={snapshot.effective} /></dd></div>
          <div><dt>Requested revision</dt><dd><Revision value={snapshot.requested} /></dd></div>
          <div><dt>Failed revision</dt><dd><Revision value={snapshot.failed} /></dd></div>
        </dl>
      </section>
      <div className="harness-activation section"><p>Stage role settings first, then activate the requested revision with a runtime restart. Active runs keep their pinned revision.</p>
        <div className="actions"><Button variant="secondary" disabled={!!busy || !fresh || !snapshot.requested || snapshot.requested === snapshot.effective} busy={busy === 'activate'} onClick={() => snapshot.requested && void mutate('activate', { version: snapshot.requested })}>Activate requested revision</Button>
          <Button variant="ghost" disabled={!!busy} busy={busy === 'refresh'} onClick={() => void refresh()}>Refresh configuration status</Button></div>
      </div>
      {snapshot.failed && <Notice tone="warning"><p>Candidate activation failed ({snapshot.failure_code ?? 'reason unavailable'}). The effective revision is shown above.</p></Notice>}
      {error instanceof ApiError && error.code === 'harness_configuration_busy' && <Notice tone="warning"><p>Finish or stop the active runs in their learning views, then refresh status and try activation again. The requested revision remains staged.</p></Notice>}
      <section className="section" aria-label="Pinned runs"><h3>Active runs</h3>
        {snapshot.pinned_runs.length ? <ul className="harness-pinned-runs">{snapshot.pinned_runs.map(run => <li key={run.run_id}>
          <span>{run.run_id}</span> · <span>{purposeNames[run.purpose] ?? run.purpose}</span> · <Revision value={run.version} />
        </li>)}</ul> : <p>No active runs are pinned to a revision.</p>}
      </section>
      {candidate ? <div className="section"><p className="muted">Editing {snapshot.requested_configuration ? 'requested' : 'effective'} revision <Revision value={snapshot.requested_configuration ? snapshot.requested : snapshot.effective} />. Staging keeps the effective revision until activation completes.</p>
        <RoleSettings key={snapshot.requested ?? snapshot.effective} configuration={candidate} catalogue={snapshot.catalogue} busy={!!busy} staging={busy === 'stage'} canStage={fresh && !!snapshot.effective && !!snapshot.configuration} stage={roles => mutate('stage', { roles })} /></div>
        : <Notice><p>Select a learning subscription in Connections, then refresh configuration status to prepare role settings.</p></Notice>}
    </>}
  </section>;
}
