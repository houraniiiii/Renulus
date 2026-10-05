"""Offline subscription acceptance with real SDK, DPAPI and controlled requests."""
import asyncio
import ipaddress
import json
import socket
import time
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.runtime.auth import ISSUER, PLAN_SCOPE, SCOPES
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app

SENTINEL = "SYNTHETIC_PROVIDER_PRIVATE_946_NOT_FOR_ERROR_MESSAGES"
SCOPE = ContextScope(kind=Scope.TEMPORARY_CASE)


@pytest.fixture(autouse=True)
def deny_external_sockets(monkeypatch):
    # Windows asyncio uses loopback sockets for its self-pipe and OAuth callback.
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)

        def local_only(sock, address, _original=original):
            assert isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback
            return _original(sock, address)

        monkeypatch.setattr(socket.socket, name, local_only)


def seed_codex(manager, *, expires_at=None):
    record = {"client_id": "synthetic-issued-client", "subject": "synthetic-subject",
              "issuer": ISSUER, "scopes": SCOPES.split(),
              "access_token": "synthetic-plan-token", "refresh_token": "synthetic-refresh",
              "expires_at": time.time() + 600 if expires_at is None else expires_at}
    manager._settings["connections"]["codex"] = record
    manager._settings["selected_provider"] = "codex"
    manager._catalogs["codex"] = {"gpt-6.1-sol"}
    manager._save()
    return record


def go_catalog(request):
    return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})


async def collect(manager, run_id="acceptance", messages=None):
    return [event async for event in manager.events(
        messages or [{"role": "user", "content": SENTINEL}], scope=SCOPE, run_id=run_id)]


@pytest.mark.asyncio
async def test_disconnect_unused_connection_keeps_selected_provider_stream(app_paths):
    entered, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class WaitingTransport:
        async def stream(self, provider, model, token, messages):
            assert provider == "codex" and model == "gpt-6.1-sol"
            try:
                yield {"type": "delta", "text": "Synthetic partial teaching"}
                entered.set()
                await release.wait()
                yield {"type": "completed"}
            finally:
                closed.set()

    manager = ProviderManager(app_paths, transport=WaitingTransport(),
                              http_transport=httpx.MockTransport(go_catalog))
    await manager.connect_go("synthetic-go-key")
    seed_codex(manager)
    manager.context.plan([{"role": "user", "content": "Synthetic teaching"}],
                         provider="codex", model="gpt-6.1-sol")
    task = asyncio.create_task(collect(manager))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await manager.disconnect("opencode-go")
        release.set()
        flow = await asyncio.wait_for(task, 2)
        assert [event.type for event in flow] == ["started", "delta", "completed"]
        assert manager.connections()["selected_provider"] == "codex"
        assert closed.is_set() and not manager.status()["active_runs"]
    finally:
        release.set()
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("result_status,reconnect", [(200, False), (401, False), (200, True), (401, True)])
async def test_stale_catalogue_cannot_change_disconnected_or_reconnected_account(
        app_paths, result_status, reconnect):
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def serve(request):
        calls.append(request)
        if len(calls) == 2:
            entered.set()
            await release.wait()
            return httpx.Response(result_status, json={"data": [{"id": "deepseek-v4.1-flash"}]})
        return go_catalog(request)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    await manager.connect_go("synthetic-old-go-key", select=True)
    task = asyncio.create_task(manager.refresh("opencode-go"))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        await manager.disconnect("opencode-go")
        if reconnect:
            await manager.connect_go("synthetic-new-go-key", select=True)
        expected = manager.connections()
        release.set()
        with pytest.raises(ApiError) as error:
            await asyncio.wait_for(task, 2)
        assert error.value.code == "connection_changed"
        assert manager.connections() == expected
        restarted = ProviderManager(app_paths)
        assert restarted.connections()["connections"][1]["status"] == ("configured" if reconnect else "disconnected")
    finally:
        release.set()
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["error", "response.failed"])
@pytest.mark.parametrize("machine_code,expected", [
    ("subscription_sharing_usage_limit_exceeded", "subscription_limit"),
    ("invalid_api_key", "authentication_required"),
    ("model_not_found", "account_model_unsupported"),
])
async def test_sdk_stream_machine_failure_is_redacted_actionable_and_has_no_retry(
        app_paths, event_type, machine_code, expected):
    calls = []

    def serve(request):
        calls.append(request)
        assert request.url == "https://api.openai.com/v1/responses"
        failure = {"code": machine_code, "message": SENTINEL + "synthetic-plan-token"}
        event = {"type": event_type, "sequence_number": 1}
        if event_type == "error":
            event.update(failure, param=None)
        else:
            event["response"] = {"id": "synthetic", "object": "response", "status": "failed",
                                 "created_at": 1, "model": "gpt-6.1-sol", "output": [], "error": failure}
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content="data: " + json.dumps(event) + "\n\n")

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    seed_codex(manager)
    flow = await collect(manager)
    assert [event.type for event in flow] == ["started", "error"]
    assert [event.sequence for event in flow] == [1, 2]
    assert flow[-1].payload["code"] == expected
    assert SENTINEL not in json.dumps([event.model_dump() for event in flow])
    assert "synthetic-plan-token" not in json.dumps(manager.status())
    assert len(calls) == 1 and manager.connections()["selected_provider"] == "codex"
    assert not manager.status()["live_provider_verified"]
    if expected == "authentication_required":
        assert manager.connections()["connections"][0]["status"] == expected
        assert manager.connections()["connections"][0]["models"][0]["availability"] == "unknown"
    if expected == "account_model_unsupported":
        again = await collect(manager, "no-silent-model-switch")
        assert again[-1].payload["code"] == expected and len(calls) == 1
    for path in app_paths.root.rglob("*"):
        if path.is_file():
            assert SENTINEL.encode() not in path.read_bytes()


def oauth_responder(manager):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update(kid="synthetic-key", use="sig", alg="RS256")

    def response(request):
        if request.url.path.endswith("/oauth/token"):
            attempt = next(iter(manager.auth._attempts.values()))
            now = int(time.time())
            token = jwt.encode({"iss": ISSUER, "aud": "synthetic-issued-client",
                "sub": "synthetic-subject", "nonce": attempt.nonce, "iat": now, "exp": now + 600},
                private_key, algorithm="RS256", headers={"kid": "synthetic-key"})
            return httpx.Response(200, json={"token_type": "Bearer", "access_token": "synthetic-new-plan",
                "refresh_token": "synthetic-new-refresh", "id_token": token, "scope": SCOPES, "expires_in": 600})
        if request.url.path.endswith("/jwks.json"):
            return httpx.Response(200, json={"keys": [jwk]})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"models": [{"slug": "gpt-6.1-sol", "visibility": "list"}]})
        raise AssertionError("Unexpected controlled request")

    return response


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_path", ["/oauth/token", "/jwks.json", "/models"])
async def test_login_cancel_interrupts_owned_exchange_and_allows_fresh_retry(app_paths, blocked_path):
    entered, stopped, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    manager = ProviderManager(app_paths)
    respond = oauth_responder(manager)
    calls = []

    async def serve(request):
        calls.append(request)
        if request.url.path.endswith(blocked_path):
            entered.set()
            try:
                await release.wait()
            finally:
                stopped.set()
        return respond(request)

    manager._http_transport = httpx.MockTransport(serve)
    login = await manager.auth.start(select=True)
    params = parse_qs(urlsplit(login["authorization_url"]).query)
    attempt = manager.auth._attempts[login["login_id"]]
    task = asyncio.create_task(manager.auth.complete(login["login_id"], {
        "state": params["state"][0], "code": "synthetic-code", "client_id": "synthetic-issued-client"}))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        before = len(calls)
        assert (await manager.auth.cancel(login["login_id"]))["status"] == "cancelled"
        assert (await asyncio.wait_for(asyncio.shield(task), 1))["status"] == "cancelled"
        assert stopped.is_set() and len(calls) == before
        assert attempt.server is None and not attempt.verifier
        assert manager.connections()["selected_provider"] is None
        assert all(row["status"] == "disconnected" for row in manager.connections()["connections"])
        retry = await manager.auth.start()
        assert retry["login_id"] != login["login_id"] and retry["status"] == "pending"
    finally:
        release.set()
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_sign_out_keeps_registration_for_same_app_reconnect_without_tokens(app_paths):
    calls = []

    def serve(request):
        calls.append(request)
        assert request.url.path.endswith("/oauth/revoke")
        return httpx.Response(200)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    record = seed_codex(manager)
    await manager.disconnect("codex")
    restarted = ProviderManager(app_paths)
    assert all(row["status"] == "disconnected" for row in restarted.connections()["connections"])
    assert "synthetic-plan-token" not in json.dumps(restarted._settings)
    assert "synthetic-refresh" not in json.dumps(restarted._settings)
    login = await restarted.auth.start()
    try:
        query = parse_qs(urlsplit(login["authorization_url"]).query)
        assert query["client_id"] == [record["client_id"]]
        assert query["ext_agent_host_id"] == [manager._settings["host_id"]]
        assert not restarted._settings["connections"]
        assert "id_token_hint" not in query
        assert len(calls) == 1
    finally:
        await restarted.close()


@pytest.mark.asyncio
async def test_first_login_uses_persistent_protocol_host_identity(app_paths):
    manager = ProviderManager(app_paths)
    calls = []
    manager._http_transport = httpx.MockTransport(lambda request: calls.append(request))
    first = await manager.auth.start()
    try:
        host = parse_qs(urlsplit(first["authorization_url"]).query)["ext_agent_host_id"][0]
        assert host.startswith("urn:uuid:") and UUID(host).version == 4
        await manager.close()
        restarted = ProviderManager(app_paths)
        second = await restarted.auth.start()
        assert parse_qs(urlsplit(second["authorization_url"]).query)["ext_agent_host_id"] == [host]
        assert not calls
        await restarted.close()
    finally:
        await manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("registered", [False, True])
async def test_legacy_host_identity_upgrades_only_without_existing_registration(app_paths, registered):
    manager = ProviderManager(app_paths)
    manager._settings["host_id"] = "a" * 48
    if registered:
        seed_codex(manager)
    manager._save()
    original = manager.store.path.read_bytes()
    try:
        if registered:
            with pytest.raises(ApiError) as error:
                await manager.auth.start()
            assert error.value.code == "host_identity_invalid"
            assert manager.store.path.read_bytes() == original
            assert manager._settings["host_id"] == "a" * 48
        else:
            login = await manager.auth.start()
            host = parse_qs(urlsplit(login["authorization_url"]).query)["ext_agent_host_id"][0]
            assert host.startswith("urn:uuid:") and UUID(host).version == 4
            assert ProviderManager(app_paths)._settings["host_id"] == host
    finally:
        await manager.close()


@pytest.mark.asyncio
async def test_expiry_interrupts_exchange_without_replacing_expired_error(app_paths, monkeypatch):
    expired, entered, stopped = asyncio.Event(), asyncio.Event(), asyncio.Event()
    real_sleep = asyncio.sleep

    async def controlled_expiry(delay, result=None):
        if delay == 600:
            await expired.wait()
            return result
        return await real_sleep(delay, result)

    monkeypatch.setattr("renulus.runtime.auth.asyncio.sleep", controlled_expiry)

    async def serve(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    login = await manager.auth.start()
    params = parse_qs(urlsplit(login["authorization_url"]).query)
    task = asyncio.create_task(manager.auth.complete(login["login_id"], {
        "state": params["state"][0], "client_id": "synthetic-issued-client", "code": "synthetic-code"}))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        expired.set()
        status = await asyncio.wait_for(task, 2)
        assert status["status"] == "error" and status["error"]["code"] == "login_expired"
        assert stopped.is_set() and not manager._settings["connections"]
        assert manager.auth._attempts[login["login_id"]].server is None
    finally:
        expired.set()
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("change,expected", [
    ({"expires_in": "nan"}, "invalid_token_response"),
    ({"expires_in": -1}, "invalid_token_response"),
    ({"access_token": ""}, "invalid_token_response"),
    ({"token_type": "MAC"}, "invalid_token_response"),
    ({"scope": PLAN_SCOPE}, "plan_permission_required"),
])
async def test_invalid_refresh_never_replaces_owned_credentials_or_invokes_model(app_paths, change, expected):
    calls = []

    def serve(request):
        calls.append(request)
        assert request.url.path.endswith("/oauth/token")
        tokens = {"access_token": "synthetic-rotated-token", "refresh_token": "synthetic-rotated-refresh",
                  "token_type": "Bearer", "expires_in": 600, "scope": SCOPES}
        return httpx.Response(200, json=tokens | change)

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    original = seed_codex(manager, expires_at=0).copy()
    flow = await collect(manager)
    assert flow[-1].type == "error" and flow[-1].payload["code"] == expected
    assert manager._settings["connections"]["codex"] == original
    assert ProviderManager(app_paths)._settings["connections"]["codex"] == original
    assert len(calls) == 1 and not manager.status()["active_runs"]


@pytest.mark.asyncio
async def test_transient_refresh_failure_preserves_rotating_token_and_is_retryable(app_paths):
    phase = {"status": 503}
    calls = []

    def serve(request):
        calls.append(request)
        if request.url.path.endswith("/oauth/token"):
            if phase["status"] != 200:
                return httpx.Response(phase["status"], json={"error": {"message": SENTINEL}})
            form = parse_qs(request.content.decode())
            assert form["refresh_token"] == ["synthetic-refresh"]
            # Omitted scope means the previously granted scope was unchanged.
            return httpx.Response(200, json={"access_token": "synthetic-rotated-token",
                "refresh_token": "synthetic-rotated-refresh", "token_type": "Bearer", "expires_in": 600})
        assert request.url.path.endswith("/models")
        assert request.headers["authorization"] == "Bearer synthetic-rotated-token"
        return httpx.Response(200, json={"models": [
            {"slug": "gpt-6.1-sol", "visibility": "list"},
            {"slug": "gpt-6-astra", "visibility": "hidden"},
            {"slug": "unapproved-model", "visibility": "list"}]})

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    original = seed_codex(manager, expires_at=0).copy()
    with pytest.raises(ApiError) as error:
        await manager.refresh("codex")
    assert error.value.code == "provider_unavailable" and error.value.retryable
    assert manager._settings["connections"]["codex"] == original
    assert manager.connections()["connections"][0]["status"] == "provider_unavailable"
    phase["status"] = 200
    status = await manager.refresh("codex")
    assert status["selected_provider"] == "codex" and status["connections"][0]["status"] == "connected"
    assert manager._settings["connections"]["codex"]["refresh_token"] == "synthetic-rotated-refresh"
    assert ProviderManager(app_paths)._settings["connections"]["codex"]["access_token"] == "synthetic-rotated-token"
    assert status["connections"][0]["models"][0]["text_input"] == "unknown"
    assert status["connections"][0]["models"][1]["availability"] == "unavailable"
    assert len(calls) == 3 and all(not request.url.path.endswith("/responses") for request in calls)


@pytest.mark.asyncio
async def test_new_login_supersedes_pending_exchange_with_honest_cancelled_result(app_paths):
    entered, stopped = asyncio.Event(), asyncio.Event()

    async def serve(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    first = await manager.auth.start()
    query = parse_qs(urlsplit(first["authorization_url"]).query)
    task = asyncio.create_task(manager.auth.complete(first["login_id"], {
        "state": query["state"][0], "client_id": "synthetic-issued-client", "code": "synthetic-code"}))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        second = await manager.auth.start()
        assert second["login_id"] != first["login_id"] and second["status"] == "pending"
        assert (await asyncio.wait_for(task, 2))["status"] == "cancelled"
        assert stopped.is_set() and not manager._settings["connections"]
    finally:
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancel_during_token_refresh_stops_before_catalogue_or_generation(app_paths):
    entered, stopped = asyncio.Event(), asyncio.Event()
    calls = []

    async def serve(request):
        calls.append(request)
        assert request.url.path.endswith("/oauth/token")
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    original = seed_codex(manager, expires_at=0).copy()
    task = asyncio.create_task(collect(manager, "cancel-refresh"))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        assert await manager.cancel("cancel-refresh")
        flow = await asyncio.wait_for(task, 2)
        assert [event.type for event in flow] == ["cancelled"]
        assert stopped.is_set() and not manager.status()["active_runs"] and len(calls) == 1
        assert manager._settings["connections"]["codex"] == original
    finally:
        await manager.close()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status,expected", [(401, "authentication_required"),
    (429, "subscription_limit"), (None, "provider_unavailable")])
async def test_real_sdk_failure_preserves_learn_thread_across_restart_and_explicit_retry(
        app_paths, http_status, expected):
    phase = {"failure": True}
    inference = []

    def serve(request):
        if request.url.path.endswith("/models"):
            return go_catalog(request)
        assert request.url == "https://opencode.ai/zen/go/v1/chat/completions"
        inference.append(request)
        if phase["failure"]:
            if http_status is None:
                raise httpx.ConnectError("Synthetic offline " + SENTINEL, request=request)
            return httpx.Response(http_status, json={"error": {"message": SENTINEL}})
        chunks = [{"id": "synthetic", "object": "chat.completion.chunk", "created": 1,
            "model": "mimo-v2.6-pro", "choices": [{"index": 0, "delta": {"content": text},
                                                     "finish_reason": reason}]}
                  for text, reason in [("Synthetic retained study explanation", None), (None, "stop")]]
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content="".join("data: " + json.dumps(chunk) + "\n\n" for chunk in chunks) + "data: [DONE]\n\n")

    def configured_app():
        app = create_app(app_paths.root, token="synthetic-local-token", source_root=app_paths.source_root)
        # This acceptance check isolates the approved generation seam from helper workers.
        app.state.services.registry["knowledge"] = None
        app.state.services.registry["memory"] = None
        provider = app.state.services.registry["provider"]
        provider._http_transport = httpx.MockTransport(serve)
        return app, provider

    def decoded(response):
        return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]

    app, provider = configured_app()
    await provider.connect_go("synthetic-retained-go-key", select=True)
    body = {"question": "Explain synthetic dialysis study", "scope": {"kind": "study"}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
                                 headers={"x-renulus-token": "synthetic-local-token"}) as local:
        flow = decoded(await local.post("/api/v1/learn/ask", json=body))
        assert flow[-1]["type"] == "error" and flow[-1]["payload"]["code"] == expected
        assert SENTINEL not in json.dumps(flow)
        thread_id = flow[0]["payload"]["thread_id"]
        thread = (await local.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in thread["messages"]] == ["user"]
        assert thread["messages"][0]["content"] == body["question"]
        assert thread["runs"][0]["state"] == "failed" and len(inference) == 1
    restarted, resumed = configured_app()
    assert resumed.connections()["connections"][1]["status"] == "configured"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url="http://127.0.0.1",
                                 headers={"x-renulus-token": "synthetic-local-token"}) as local:
        assert (await local.get("/api/v1/learn/threads/" + thread_id)).json()["messages"] == thread["messages"]
        phase["failure"] = False
        assert (await local.post("/api/v1/connections/opencode-go/refresh")).status_code == 200
        success = decoded(await local.post("/api/v1/learn/ask", json=body | {"thread_id": thread_id}))
        assert success[-1]["type"] == "completed" and success[-1]["payload"]["thread_id"] == thread_id
        saved = (await local.get("/api/v1/learn/threads/" + thread_id)).json()
        assert [message["role"] for message in saved["messages"]] == ["user", "user", "assistant"]
        assert len(inference) == 2 and not resumed.status()["live_provider_verified"]
        assert all(json.loads(request.content)["model"] == "mimo-v2.6-pro" for request in inference)
    await provider.close()
    await resumed.close()
