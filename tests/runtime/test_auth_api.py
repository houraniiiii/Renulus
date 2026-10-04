import asyncio
import json
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

from renulus.contracts import ApiError
from renulus.runtime.auth import ISSUER, PLAN_SCOPE, SCOPES
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app


def oauth_provider(manager, *, nonce_mode="correct", plan_enabled=True):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk.update(kid="synthetic-kid", use="sig", alg="RS256")
    calls = []
    def serve(request):
        calls.append(request)
        if request.url.path.endswith("/oauth/token"):
            body = parse_qs(request.content.decode())
            attempt = next(iter(manager.auth._attempts.values()))
            assert body["code_verifier"] == [attempt.verifier]
            assert body["redirect_uri"] == [attempt.redirect_uri]
            assert body["client_id"] == ["synthetic-issued-client"]
            now = int(time.time())
            claims = {"iss": ISSUER, "aud": "synthetic-issued-client", "sub": "synthetic-user",
                      "iat": now, "exp": now + 600,
                      "nonce": attempt.nonce if nonce_mode == "correct" else "wrong-nonce"}
            token = jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "synthetic-kid"})
            return httpx.Response(200, json={"token_type": "Bearer", "access_token": "synthetic-oauth-access",
                "refresh_token": "synthetic-renewable-session", "id_token": token,
                "expires_in": 600, "scope": SCOPES if plan_enabled else "openid profile email"})
        if request.url.path.endswith("/jwks.json"):
            return httpx.Response(200, json={"keys": [jwk]})
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-6-luna"}, {"id": "unapproved-model"}]})
        raise AssertionError("Unexpected network operation " + str(request.url))
    manager._http_transport = httpx.MockTransport(serve)
    return calls


@pytest.mark.asyncio
async def test_app_owned_dynamic_login_pkce_signed_oidc_actual_loopback_and_no_inference(app_paths):
    manager = ProviderManager(app_paths)
    calls = oauth_provider(manager)
    login = await manager.auth.start(select=True)
    authorization = parse_qs(urlsplit(login["authorization_url"]).query)
    assert authorization["client_id"] == ["dynamic_agent_client"]
    assert authorization["agent_name_hint"] == ["Renulus"]
    assert authorization["code_challenge_method"] == ["S256"]
    assert PLAN_SCOPE in authorization["scope"][0]
    assert authorization["redirect_uri"][0].startswith("http://127.0.0.1:")
    assert manager.connections()["selected_provider"] is None
    assert not calls
    async with httpx.AsyncClient(trust_env=False) as local:
        response = await local.get(authorization["redirect_uri"][0], params={
            "state": authorization["state"][0], "code": "synthetic-code",
            "client_id": "synthetic-issued-client"})
    assert response.status_code == 200
    assert manager.auth.status(login["login_id"])["status"] == "connected"
    assert manager.connections()["selected_provider"] == "codex"
    assert [request.url.path for request in calls] == ["/api/accounts/oauth/token", "/.well-known/jwks.json", "/v1/models"]
    public = json.dumps(manager.status())
    assert "synthetic-oauth-access" not in public and "synthetic-renewable-session" not in public
    saved_host = manager._settings["host_id"]
    restarted = ProviderManager(app_paths)
    assert restarted._settings["host_id"] == saved_host
    next_login = await restarted.auth.start()
    query = parse_qs(urlsplit(next_login["authorization_url"]).query)
    assert query["client_id"] == ["synthetic-issued-client"] and "agent_name_hint" not in query
    assert "id_token_hint" not in query
    await restarted.close()
    await manager.close()


@pytest.mark.asyncio
async def test_wrong_state_never_exchanges_token_and_cancel_closes_listener(app_paths):
    manager = ProviderManager(app_paths)
    calls = oauth_provider(manager)
    login = await manager.auth.start()
    query = parse_qs(urlsplit(login["authorization_url"]).query)
    with pytest.raises(ApiError) as failure:
        await manager.auth.complete(login["login_id"], {"state": "wrong-state", "code": "synthetic"})
    assert failure.value.code == "login_state_mismatch" and not calls
    attempt = manager.auth._attempts[login["login_id"]]
    port = urlsplit(query["redirect_uri"][0]).port
    assert (await manager.auth.cancel(login["login_id"]))["status"] == "cancelled"
    assert attempt.server is None and attempt.verifier == ""
    with pytest.raises(OSError):
        await asyncio.open_connection("127.0.0.1", port)


@pytest.mark.asyncio
@pytest.mark.parametrize("nonce_mode,plan_enabled,expected", [
    ("incorrect", True, "identity_validation_failed"),
    ("correct", False, "plan_permission_required")])
async def test_id_token_and_plan_permission_fail_closed(app_paths, nonce_mode, plan_enabled, expected):
    manager = ProviderManager(app_paths)
    calls = oauth_provider(manager, nonce_mode=nonce_mode, plan_enabled=plan_enabled)
    login = await manager.auth.start(select=True)
    query = parse_qs(urlsplit(login["authorization_url"]).query)
    status = await manager.auth.complete(login["login_id"], {"state": query["state"][0],
        "code": "synthetic-code", "client_id": "synthetic-issued-client"})
    assert status["status"] == "error" and status["error"]["code"] == expected
    assert manager.connections()["selected_provider"] is None
    assert "codex" not in manager._settings["connections"]
    assert not any(request.url.path.endswith("/models") for request in calls)
    await manager.close()


@pytest.mark.asyncio
async def test_versioned_api_registers_one_provider_and_masks_validation_payload(app_paths):
    app = create_app(app_paths.root, token="synthetic-app-token", source_root=app_paths.source_root)
    provider = app.state.services.registry["provider"]
    assert isinstance(provider, ProviderManager)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
                                 headers={"x-renulus-token": "synthetic-app-token"}) as local:
        result = await local.get("/api/v1/connections")
        assert result.status_code == 200
        assert all(row["status"] == "disconnected" for row in result.json()["connections"])
        runtime = (await local.get("/api/v1/runtime/status")).json()
        assert runtime["helpers"]["embedding"]["ready"] is False
        invalid = await local.post("/api/v1/runtime/runs", json={"run_id": "synthetic",
            "scope": {"kind": "temporary-case"}, "messages": [{"role": "user", "content": "SYNTHETIC_PRIVATE_INPUT"}],
            "invalid_field": "SYNTHETIC_PRIVATE_INPUT"})
        assert invalid.status_code == 422 and "SYNTHETIC_PRIVATE_INPUT" not in invalid.text
        stream = await local.post("/api/v1/runtime/runs", json={"run_id": "synthetic",
            "scope": {"kind": "temporary-case"}, "messages": [{"role": "user", "content": "SYNTHETIC_PRIVATE_INPUT"}]})
        assert stream.status_code == 200 and stream.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith("data: ")]
        assert len(events) == 1 and events[0]["type"] == "error"
        assert events[0]["payload"]["code"] == "connection_required"
        assert "SYNTHETIC_PRIVATE_INPUT" not in stream.text
    assert not provider.status()["active_runs"]
