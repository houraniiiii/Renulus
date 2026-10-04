import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ArrowRight, Check, RefreshCw } from 'lucide-react';
import { api, ApiError, isCancelled } from './api';
import { useResource } from './useResource';
import { Badge, Button, ErrorState, Input, LoadingState, Notice, PageHeader } from '../ui';
import type { Health } from './contracts';

type Provider = 'codex' | 'opencode-go';
interface Connection {
  provider: Provider;
  status: string;
  allowed_models: string[];
  models: { id: string; availability: 'unknown' | 'available' | 'unavailable'; image_input: 'unverified' }[];
}
interface Connections { selected_provider: Provider | null; connections: Connection[] }
interface Login { login_id: string; status: 'pending' | 'connected' | 'error' | 'cancelled'; authorization_url?: string; expires_at?: string; error?: { code: string; message: string; retryable: boolean } }
const names: Record<Provider, string> = { codex: 'Codex', 'opencode-go': 'OpenCode Go' };

export function ConnectionsPage() {
  const { resource, retry } = useResource(async signal => {
    const [health, connections] = await Promise.all([
      api<Health>('/health', { signal }), api<Connections>('/connections', { signal }),
    ]);
    return { health, connections };
  });
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState<string>();
  const [error, setError] = useState<unknown>();
  const [login, setLogin] = useState<Login>();
  const [notice, setNotice] = useState<string>();
  const active = useRef<AbortController | null>(null);
  const pendingLogin = useRef<string | undefined>(undefined);
  useEffect(() => () => {
    active.current?.abort();
    const id = pendingLogin.current;
    pendingLogin.current = undefined;
    if (id) void api('/connections/codex/login/' + encodeURIComponent(id), { method: 'DELETE', keepalive: true, timeoutMs: 5000 }).catch(() => {});
  }, []);

  async function operation(id: string, run: (signal: AbortSignal) => Promise<void>) {
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setBusy(id); setError(undefined); setNotice(undefined);
    try { await run(controller.signal); if (!controller.signal.aborted) retry(); }
    catch (failure) { if (!controller.signal.aborted && !isCancelled(failure)) setError(failure); }
    finally { if (!controller.signal.aborted) setBusy(undefined); }
  }
  async function connectGo(event: FormEvent) {
    event.preventDefault();
    const entered = key.trim();
    setKey('');
    await operation('go', async signal => {
      await api('/connections/opencode-go', { method: 'POST', body: { api_key: entered, select: false }, signal });
      setNotice('OpenCode Go connection updated. Select it when you want to use this subscription.');
    });
  }
  async function connectCodex() {
    await operation('codex', async signal => {
      const result = await api<Login>('/connections/codex/login', { method: 'POST', body: { select: false }, signal });
      if (signal.aborted) return;
      pendingLogin.current = result.status === 'pending' ? result.login_id : undefined;
      setLogin(result);
      if (result.authorization_url) {
        if (window.renulus) await window.renulus.openAuthorization(result.authorization_url);
      }
    });
  }
  useEffect(() => {
    if (!login || login.status !== 'pending') return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api<Login>('/connections/codex/login/' + encodeURIComponent(login.login_id), { signal: controller.signal });
        if (controller.signal.aborted) return;
        if (result.status !== 'pending') {
          pendingLogin.current = undefined;
          setLogin(result);
          if (result.error) setError(new ApiError(result.error.message, 400, result.error.code, result.error.retryable));
          if (result.status === 'connected') { setNotice('Codex is connected. Select it to use this subscription.'); retry(); }
          return;
        }
        timer = setTimeout(poll, 1500);
      } catch (failure) { if (!controller.signal.aborted) {
        setError(failure);
        // Keep the pending session visible so a transient polling error does not
        // hide the user's cancel action or leave an unseen listener behind.
        timer = setTimeout(poll, 3000);
      } }
    };
    timer = setTimeout(poll, 1500);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [login?.login_id, login?.status, retry]);

  return <>
    <PageHeader title="Connections" description="Choose the subscription Renulus uses for your learning." actions={<Button variant="secondary" disabled={!!busy} onClick={retry}><RefreshCw size={16} />Refresh status</Button>} />
    {error && <div className="section"><ErrorState error={error} title="The connection could not be updated" onRetry={() => { setError(undefined); retry(); }} /></div>}
    {notice && <div className="section"><Notice><p>{notice}</p></Notice></div>}
    {resource.status === 'loading' ? <LoadingState label="Checking your learning connections" /> : resource.status === 'error' ? <ErrorState error={resource.error} title="Connections could not be loaded" onRetry={retry} /> : <div className="connection-columns">
      <section className="connection-list" aria-label="Learning subscriptions">
        {resource.data.connections.connections.map(connection => <section className="connection-row" key={connection.provider}>
          <div className="connection-heading"><h2>{names[connection.provider]}</h2><Badge tone={connection.status === 'connected' ? 'default' : 'neutral'}>{connection.status.replaceAll('-', ' ')}</Badge>{resource.data.connections.selected_provider === connection.provider && <Badge><Check size={14} />Selected</Badge>}</div>
          <p>{connection.provider === 'codex' ? 'Connect your own account through Continue with ChatGPT.' : 'Enter the key for your selected OpenCode Go subscription.'}</p>
          <ul className="connection-models" aria-label={names[connection.provider] + ' model availability'}>{connection.models.map(model => <li key={model.id}><strong>{model.id}</strong><Badge tone={model.availability === 'available' ? 'default' : 'neutral'}>{model.availability === 'unknown' ? 'Availability not checked' : model.availability}</Badge></li>)}</ul>
          {connection.provider === 'opencode-go' && connection.status !== 'connected' && <form className="connection-key" onSubmit={connectGo}><Input label="OpenCode Go key" type="password" value={key} onChange={event => setKey(event.target.value)} autoComplete="off" spellCheck={false} hint="Stored by Renulus in its protected app profile. Never imported from another application." /><div><Button type="submit" busy={busy === 'go'} disabled={!key.trim() || !!busy}>Connect OpenCode Go<ArrowRight size={16} /></Button></div></form>}
          <div className="actions">
            {connection.provider === 'codex' && connection.status !== 'connected' && <Button onClick={connectCodex} disabled={!!busy || login?.status === 'pending'} busy={busy === 'codex'}>Continue with ChatGPT<ArrowRight size={16} /></Button>}
            {connection.status === 'connected' && resource.data.connections.selected_provider !== connection.provider && <Button disabled={!!busy} onClick={() => operation('select', async signal => { await api('/connections/select', { method: 'POST', body: { provider: connection.provider }, signal }); })}>Use {names[connection.provider]}</Button>}
            {connection.status === 'connected' && <><Button variant="secondary" disabled={!!busy} onClick={() => operation('refresh', async signal => { await api('/connections/' + connection.provider + '/refresh', { method: 'POST', signal }); })}>Check models</Button><Button variant="ghost" disabled={!!busy} onClick={() => operation('disconnect', async signal => { await api('/connections/' + connection.provider, { method: 'DELETE', signal }); })}>Disconnect</Button></>}
          </div>
          {connection.provider === 'codex' && login?.status === 'pending' && <Notice><div className="section"><p>Finish sign-in in your browser. Renulus is waiting for your account to connect.</p><div className="actions">{!window.renulus && login.authorization_url && <a href={login.authorization_url} target="_blank" rel="noreferrer">Open sign-in in your browser</a>}<Button variant="ghost" disabled={!!busy} onClick={() => operation('cancel-login', async signal => { await api('/connections/codex/login/' + encodeURIComponent(login.login_id), { method: 'DELETE', signal }); pendingLogin.current = undefined; setLogin(undefined); })}>Cancel sign-in</Button></div></div></Notice>}
        </section>)}
      </section>
      <aside className="section"><section className="section"><h2>Your local runtime</h2><p>Runtime {resource.data.health.version} · API {resource.data.health.api_version}</p><p>Subscription and model availability are reported by the backend. Image input remains unverified until a live check.</p></section><Notice><p>Renulus uses your selected subscription. It does not silently switch subscriptions or add a paid API fallback.</p></Notice><p className="muted">Connecting and checking models do not send a learning prompt. Ask and other model-dependent flows need separate working integration evidence.</p></aside>
    </div>}
  </>;
}
