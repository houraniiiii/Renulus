import { useCallback, useEffect, useRef, useState, type FormEvent, type MouseEvent } from 'react';
import { ArrowRight, Check, RefreshCw } from 'lucide-react';
import { api, ApiError, isCancelled } from './api';
import { useResource } from './useResource';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, PageHeader } from '../ui';
import type { Health } from './contracts';
import { DataManagement } from './DataManagement';
import { RetrievalConnections } from './RetrievalConnections';

type Provider = 'codex' | 'opencode-go';
type Availability = 'unknown' | 'available' | 'unavailable' | 'account_unsupported';
type Capability = 'unknown' | 'supported' | 'account_unsupported';
interface Model { id: string; availability: Availability; text_input?: Capability; image_input?: Capability; image_interpretation_verified?: boolean }
interface Connection { provider: Provider; status: string; allowed_models: string[]; models: Model[] }
interface Connections { selected_provider: Provider | null; connections: Connection[]; revocation?: 'failed'; recovery?: string }
interface Login {
  login_id: string; status: 'pending' | 'exchanging' | 'connected' | 'error' | 'cancelled';
  authorization_url?: string; expires_at?: number; error?: { code: string; message: string; retryable: boolean };
}
type Action = { kind: 'start-login' | 'open-login' | 'check-login' | 'cancel-login' | 'go' | 'go-account' }
  | { kind: 'select' | 'refresh' | 'disconnect'; provider: Provider };
interface Failure { error: unknown; action?: Action }
interface Message { text: string; tone?: 'warning' }
const names: Record<Provider, string> = { codex: 'Codex', 'opencode-go': 'OpenCode Go' };
const approvedModels: Record<Provider, string[]> = {
  codex: ['gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna'],
  'opencode-go': ['mimo-v2.6-pro', 'deepseek-v4.1-flash'],
};
const goAccount = 'https://opencode.ai/auth';
const loginPath = (id: string) => '/connections/codex/login/' + encodeURIComponent(id);
const loginActive = (login?: Login) => login?.status === 'pending' || login?.status === 'exchanging';

// Match the existing main-process authorization boundary before exposing a link.
function authorizationUrl(value?: string): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && url.hostname === 'auth.openai.com' && url.pathname === '/api/accounts/authorize'
      && !url.username && !url.password && !url.port && !url.hash) return value;
  } catch { /* Invalid URLs cannot be opened in either desktop or browser mode. */ }
  return undefined;
}
function readLogin(result: Login, expectedId?: string): Login {
  if (!result || typeof result.login_id !== 'string' || !result.login_id || result.login_id.length > 128
    || (expectedId && result.login_id !== expectedId)
    || !['pending', 'exchanging', 'connected', 'error', 'cancelled'].includes(result.status)) {
    throw new ApiError('Renulus returned an invalid sign-in status. Check this attempt again.', 0, 'invalid_login_response', true);
  }
  return result;
}
async function loginStatus(id: string, signal: AbortSignal): Promise<Login> {
  try { return readLogin(await api<Login>(loginPath(id), { signal }), id); }
  catch (error) {
    if (error instanceof ApiError && error.code === 'login_not_found') {
      return { login_id: id, status: 'error', error: { code: error.code, message: 'This sign-in attempt is no longer active. Continue with ChatGPT again.', retryable: true } };
    }
    throw error;
  }
}
function modelRows(connection: Connection): Model[] {
  return approvedModels[connection.provider].map(id => connection.models.find(model => model.id === id) ?? { id, availability: 'unknown' });
}
function statusLabel(status: string): string {
  return ({ connected: 'Account connected', disconnected: 'Not connected', configured: 'Saved · check models',
    no_allowed_models: 'No approved models', authentication_required: 'Sign-in required', connection_required: 'Not connected',
    provider_unavailable: 'Account check unavailable', subscription_limit: 'Subscription limit reached', model_unavailable: 'Models need checking',
  } as Record<string, string>)[status] ?? 'Connection needs attention';
}
function capabilityLabel(kind: 'Text' | 'Images', value?: Capability): string {
  return kind + ': ' + (value === 'supported' ? 'request accepted' : value === 'account_unsupported' ? 'unsupported for this account' : 'not verified');
}

export function ConnectionsPage() {
  const [section, setSection] = useState<'subscriptions' | 'sources' | 'data'>('subscriptions');
  const { resource, retry } = useResource(async signal => {
    const [health, connections] = await Promise.all([
      api<Health>('/health', { signal }), api<Connections>('/connections', { signal }),
    ]);
    return { health, connections };
  });
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState<Action>();
  const [failure, setFailure] = useState<Failure>();
  const [login, setLogin] = useState<Login>();
  const [notice, setNotice] = useState<Message>();
  const [pollVersion, setPollVersion] = useState(0);
  const mounted = useRef(true);
  const active = useRef<AbortController | null>(null);
  const polling = useRef<AbortController | null>(null);
  const loginRef = useRef<Login | undefined>(undefined);
  const pendingLogin = useRef<string | undefined>(undefined);
  const releasedLogins = useRef(new Set<string>());

  const releaseLogin = useCallback((id: string) => {
    if (releasedLogins.current.has(id)) return;
    releasedLogins.current.add(id);
    if (pendingLogin.current === id) pendingLogin.current = undefined;
    void api(loginPath(id), { method: 'DELETE', keepalive: true, timeoutMs: 5000 }).catch(() => {});
  }, []);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; active.current?.abort(); polling.current?.abort();
      if (pendingLogin.current) releaseLogin(pendingLogin.current);
    };
  }, [releaseLogin]);

  const acceptLogin = useCallback((result: Login) => {
    if (!mounted.current) return;
    const previous = loginRef.current;
    const current = previous?.login_id === result.login_id ? { ...previous, ...result } : result;
    loginRef.current = current; pendingLogin.current = loginActive(current) ? current.login_id : undefined;
    setLogin(current);
    setFailure(previousFailure => previousFailure?.action?.kind === 'check-login' ? undefined : previousFailure);
    if (current.status === 'error') {
      const detail = current.error;
      setFailure({ error: new ApiError(detail?.message ?? 'Sign-in did not complete. Continue with ChatGPT again.', 400, detail?.code ?? 'login_failed', detail?.retryable ?? true), action: { kind: 'start-login' } });
    } else if (current.status === 'connected') {
      setFailure(undefined);
      setNotice({ text: 'ChatGPT sign-in completed. Check the approved models below, then explicitly select Codex to use this subscription.' }); retry();
    } else if (current.status === 'cancelled') {
      setFailure(undefined); setNotice({ text: 'ChatGPT sign-in cancelled.' });
    }
  }, [retry]);

  async function operation(action: Action, run: (signal: AbortSignal) => Promise<void>, reload = true) {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setBusy(action); setFailure(undefined); setNotice(undefined);
    try { await run(controller.signal); if (!controller.signal.aborted && mounted.current && reload) retry(); }
    catch (error) {
      if (!controller.signal.aborted && mounted.current && !isCancelled(error)) setFailure({ error, action: action.kind === 'go' ? undefined : action });
    } finally {
      if (!controller.signal.aborted && mounted.current) { setBusy(undefined); active.current = null; }
    }
  }
  async function openLogin(signal?: AbortSignal) {
    const current = loginRef.current;
    const url = authorizationUrl(current?.authorization_url);
    if (!url || !loginActive(current) || signal?.aborted) return;
    if (window.renulus) {
      try { await window.renulus.openAuthorization(url); }
      catch {
        if (!signal?.aborted && mounted.current) setFailure({ error: new ApiError('The sign-in browser could not be opened. Reopen this sign-in attempt, or cancel and start again.', 0, 'authorization_open_failed', true), action: { kind: 'open-login' } });
      }
    }
  }
  async function connectCodex() {
    await operation({ kind: 'start-login' }, async signal => {
      const result = await api<Login>('/connections/codex/login', { method: 'POST', body: { select: false }, signal });
      // JSON can arrive after cancellation of the request. Do not orphan a known listener.
      if (signal.aborted || !mounted.current) {
        if (result?.login_id && loginActive(result)) releaseLogin(result.login_id);
        return;
      }
      try {
        readLogin(result);
        if (loginActive(result) && !authorizationUrl(result.authorization_url)) {
          throw new ApiError('Renulus returned an invalid sign-in link. Start a new sign-in attempt.', 0, 'invalid_authorization_url', true);
        }
      } catch (error) { if (result?.login_id) releaseLogin(result.login_id); throw error; }
      acceptLogin(result);
      await openLogin(signal);
    }, false);
  }
  async function checkLogin() {
    const id = pendingLogin.current; if (!id) return;
    polling.current?.abort();
    await operation({ kind: 'check-login' }, async signal => {
      const result = await loginStatus(id, signal);
      if (!signal.aborted && pendingLogin.current === id) acceptLogin(result);
    }, false);
    if (mounted.current) setPollVersion(value => value + 1);
  }
  async function cancelLogin() {
    const id = pendingLogin.current; if (!id) return;
    polling.current?.abort();
    await operation({ kind: 'cancel-login' }, async signal => {
      let result: Login;
      try { result = readLogin(await api<Login>(loginPath(id), { method: 'DELETE', signal }), id); }
      catch (error) {
        if (!(error instanceof ApiError) || error.code !== 'login_not_found') throw error;
        result = { login_id: id, status: 'cancelled' };
      }
      if (!signal.aborted && pendingLogin.current === id) acceptLogin(result);
    }, false);
    if (mounted.current) setPollVersion(value => value + 1);
  }
  async function connectGo(event: FormEvent) {
    event.preventDefault();
    const entered = key.trim(); setKey('');
    await operation({ kind: 'go' }, async signal => {
      const result = await api<Connections>('/connections/opencode-go', { method: 'POST', body: { api_key: entered, select: false }, signal });
      if (signal.aborted) return;
      const connection = result.connections.find(item => item.provider === 'opencode-go');
      setNotice(connection?.status === 'connected'
        ? { text: 'OpenCode Go access saved. Explicitly select it when you want to use this subscription.' }
        : { text: 'OpenCode Go access saved, but this account lists none of the approved models. Check models or disconnect this account.', tone: 'warning' });
    });
  }
  async function providerAction(action: Extract<Action, { provider: Provider }>) {
    await operation(action, async signal => {
      const result = await api<Connections>(action.kind === 'select' ? '/connections/select' : '/connections/' + action.provider + (action.kind === 'refresh' ? '/refresh' : ''), {
        method: action.kind === 'disconnect' ? 'DELETE' : 'POST', body: action.kind === 'select' ? { provider: action.provider } : undefined, signal,
      });
      if (signal.aborted) return;
      if (action.kind === 'disconnect') {
        setNotice(result.revocation === 'failed'
          ? { text: names[action.provider] + ' was disconnected from this Renulus profile. ChatGPT access could not be revoked. ' + (result.recovery ?? "Remove Renulus in your ChatGPT account's connected apps."), tone: 'warning' }
          : { text: names[action.provider] + ' was disconnected from this Renulus profile.' });
      } else if (action.kind === 'refresh') {
        const connection = result.connections.find(item => item.provider === action.provider);
        const available = connection ? modelRows(connection).filter(model => model.availability === 'available').length : 0;
        setNotice({ text: names[action.provider] + ' catalogue checked: ' + available + ' of ' + approvedModels[action.provider].length + ' approved models listed. Model listing does not verify text or image requests.', tone: available ? undefined : 'warning' });
      } else setNotice({ text: names[action.provider] + ' selected for learning. Renulus will not switch subscriptions automatically.' });
    });
  }
  async function openGoAccount(event?: MouseEvent<HTMLAnchorElement>) {
    if (active.current || loginActive(loginRef.current)) { event?.preventDefault(); return; }
    if (!window.renulus?.openSource) return;
    event?.preventDefault();
    await operation({ kind: 'go-account' }, async () => {
      try { await window.renulus!.openSource!(goAccount); }
      catch { throw new ApiError('The OpenCode Go account page could not be opened. Try opening it again.', 0, 'account_open_failed', true); }
    }, false);
  }
  function retryFailure() {
    const action = failure?.action; if (!action) return;
    switch (action.kind) {
      case 'start-login': void connectCodex(); break;
      case 'check-login': void checkLogin(); break;
      case 'cancel-login': void cancelLogin(); break;
      case 'open-login': void operation(action, openLogin, false); break;
      case 'go-account': void openGoAccount(); break;
      case 'select': case 'refresh': case 'disconnect': void providerAction(action); break;
    }
  }
  useEffect(() => {
    if (!loginActive(login) || !login) return;
    const id = login.login_id; const controller = new AbortController(); polling.current = controller;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await loginStatus(id, controller.signal);
        if (controller.signal.aborted || pendingLogin.current !== id) return;
        acceptLogin(result);
        if (loginActive(result)) timer = setTimeout(poll, 1500);
      } catch (error) {
        if (!controller.signal.aborted && mounted.current) {
          setFailure({ error, action: { kind: 'check-login' } });
          timer = setTimeout(poll, 3000);
        }
      }
    };
    timer = setTimeout(poll, 1500);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [login?.login_id, login?.status, pollVersion, acceptLogin]);

  const signingIn = loginActive(login);
  const signInUrl = authorizationUrl(login?.authorization_url);
  return <>
    <PageHeader title="Connections" description="Choose the subscription Renulus uses for your learning." actions={<Button variant="secondary" disabled={!!busy} onClick={retry}><RefreshCw size={16} />Refresh status</Button>} />
    <nav className="actions connection-settings" aria-label="Connection settings">
      {([{ id: 'subscriptions', label: 'Learning subscriptions' }, { id: 'sources', label: 'Sources and retrieval' }, { id: 'data', label: 'Your study data' }] as const).map(item =>
        <Button key={item.id} variant={section === item.id ? 'secondary' : 'ghost'} aria-pressed={section === item.id} disabled={!!busy || signingIn} onClick={() => setSection(item.id)}>{item.label}</Button>)}
    </nav>
    {section === 'subscriptions' && <>
      {failure && <div className="section"><ErrorState error={failure.error} title="The connection could not be updated" onRetry={failure.action && !busy ? retryFailure : undefined} />{!failure.action && <p>Enter your OpenCode Go key again to retry. The previous entry has been cleared.</p>}</div>}
      {notice && <div className="section"><Notice tone={notice.tone}><p>{notice.text}</p></Notice></div>}
      {signingIn && login && <section className="section" aria-label="Codex sign-in"><Notice><div className="section">
        <p>{login.status === 'exchanging' ? 'ChatGPT sign-in received. Renulus is finishing the account connection.' : 'Finish sign-in in your browser. Renulus is waiting for your account to connect.'}</p>
        {typeof login.expires_at === 'number' && <p className="muted">Sign-in expires at {new Date(login.expires_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.</p>}
        <div className="actions">
          {login.status === 'pending' && signInUrl && (window.renulus
            ? <Button variant="secondary" disabled={!!busy} onClick={() => operation({ kind: 'open-login' }, openLogin, false)}>Reopen sign-in in browser</Button>
            : <a href={signInUrl} target="_blank" rel="noopener noreferrer">Open sign-in in your browser</a>)}
          <Button variant="secondary" busy={busy?.kind === 'check-login'} disabled={!!busy} onClick={checkLogin}>Check sign-in status</Button>
          <Button variant="ghost" busy={busy?.kind === 'cancel-login'} disabled={!!busy} onClick={cancelLogin}>Cancel sign-in</Button>
        </div>
      </div></Notice></section>}
      {resource.status === 'loading' ? <LoadingState label="Checking your learning connections" /> : resource.status === 'error' ? <ErrorState error={resource.error} title="Connections could not be loaded" onRetry={retry} /> : <div className="connection-columns section">
        <section className="connection-list" aria-label="Learning subscriptions">
          {resource.data.connections.connections.map(connection => {
            const models = modelRows(connection);
            const ready = connection.status === 'connected' && models.some(model => model.availability === 'available');
            const saved = !['disconnected', 'connection_required'].includes(connection.status);
            return <section className="connection-row" key={connection.provider} aria-label={names[connection.provider] + ' subscription'}>
              <div className="connection-heading"><h2>{names[connection.provider]}</h2><Badge tone={connection.status === 'connected' ? 'default' : saved ? 'warning' : 'neutral'}>{statusLabel(connection.status)}</Badge>{resource.data.connections.selected_provider === connection.provider && <Badge><Check size={14} />Selected</Badge>}</div>
              <p>{connection.provider === 'codex' ? 'Connect your own account through Continue with ChatGPT.' : 'Enter a key from your OpenCode Go subscription account.'}</p>
              {connection.provider === 'opencode-go' && <p><a href={goAccount} target="_blank" rel="noopener noreferrer" aria-disabled={!!busy || signingIn || undefined} tabIndex={busy || signingIn ? -1 : undefined} className={busy || signingIn ? 'muted' : undefined} onClick={openGoAccount}>Open OpenCode Go account to get your subscription key</a></p>}
              {connection.status === 'configured' && <p>Your account is saved in this Renulus profile. Check models to confirm its current availability.</p>}
              {connection.status === 'no_allowed_models' && <p>This account lists none of the approved models. Check models again or disconnect. Renulus will not substitute a different model or subscription.</p>}
              <ul className="connection-models" aria-label={names[connection.provider] + ' model availability'}>{models.map(model => <li key={model.id}>
                <strong>{model.id}</strong><Badge tone={model.availability === 'available' ? 'default' : 'neutral'}>{({ unknown: 'Availability not checked', available: 'Listed for this account', unavailable: 'Not listed for this account', account_unsupported: 'Account rejected this model' })[model.availability] ?? 'Availability not checked'}</Badge>
                <span className="muted">{capabilityLabel('Text', model.text_input)} · {capabilityLabel('Images', model.image_input)}</span>
              </li>)}</ul>
              {connection.provider === 'opencode-go' && connection.status !== 'connected' && <form className="connection-key" onSubmit={connectGo}>
                <Input label="OpenCode Go key" type="password" value={key} onChange={event => setKey(event.target.value)} autoComplete="off" spellCheck={false} disabled={!!busy || signingIn} maxLength={8192} hint="Stored by Renulus in its protected app profile. Never imported from another application." />
                <div><Button type="submit" busy={busy?.kind === 'go'} disabled={!key.trim() || !!busy || signingIn}>Connect OpenCode Go<ArrowRight size={16} /></Button></div>
              </form>}
              <div className="actions">
                {connection.provider === 'codex' && connection.status !== 'connected' && <Button onClick={connectCodex} disabled={!!busy || signingIn} busy={busy?.kind === 'start-login'}>Continue with ChatGPT<ArrowRight size={16} /></Button>}
                {ready && resource.data.connections.selected_provider !== connection.provider && <Button disabled={!!busy || signingIn} onClick={() => providerAction({ kind: 'select', provider: connection.provider })}>Use {names[connection.provider]}</Button>}
                {saved && <><Button variant="secondary" disabled={!!busy || signingIn} busy={busy?.kind === 'refresh' && busy.provider === connection.provider} onClick={() => providerAction({ kind: 'refresh', provider: connection.provider })}>Check models</Button><Button variant="ghost" disabled={!!busy || signingIn} busy={busy?.kind === 'disconnect' && busy.provider === connection.provider} onClick={() => providerAction({ kind: 'disconnect', provider: connection.provider })}>Disconnect</Button></>}
              </div>
            </section>;
          })}
        </section>
        <aside className="section" style={{ alignSelf: 'start' }}><section className="section"><h2>Your learning connection</h2>
          <p>{resource.data.connections.selected_provider ? names[resource.data.connections.selected_provider] + ' is selected. Its account and model availability are shown here.' : 'No subscription selected. Connect an account, check its models, then choose Use Codex or Use OpenCode Go.'}</p>
          <p>Only the five approved models are used. Model listing does not verify a successful request. Input capability reflects observed requests; image interpretation quality remains unverified.</p>
        </section><Notice><p>Reviewed tests and your saved study material are available without a model connection.</p></Notice><p className="muted">Renulus {resource.data.health.version} · Connecting and checking models do not send a learning prompt.</p></aside>
      </div>}
    </>}
    {section === 'sources' && <RetrievalConnections openSource={window.renulus?.openSource} />}
    {section === 'data' && <DataManagement />}
  </>;
}
