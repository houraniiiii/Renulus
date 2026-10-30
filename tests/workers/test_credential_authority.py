"""Required Settings auth paths with synthetic DPAPI, local OAuth and mocked HTTP."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import socket
from threading import Event
import time
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest

from renulus.runtime.auth import ISSUER, JWKS_URL, REVOKE_URL, SCOPES, TOKEN_URL
from renulus.runtime.manager import ProviderManager
from renulus.runtime.policy import BASE_URLS
from renulus.worker_contracts import payload_digest
from renulus.workers.credential_authority import CredentialLease, CredentialRefused, credential_owner
from renulus.workers.broker_models import CredentialAuthority
from renulus.workers.transport_guard import endpoint_network, permitted_connection
from .test_broker_integration import Harness, SECRET, launch


def harness(tmp_path, *, reader=lambda: SECRET):
    h = Harness(launch(tmp_path), secret_reader=reader)
    h.activate()
    return h


def send_modified(h, command, mutate):
    value = h.value(command, {"provider_id": "opencode-go"})
    mutate(value["input"]["authority"])
    value["payload_sha256"] = payload_digest(value["input"])
    return h.wait(h.send(value))


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate()


def test_go_connect_refresh_forget_exact_http_dpapi_namespace_and_no_auto_activation(tmp_path, caplog, capsys):
    reads, calls = [], []
    h = harness(tmp_path, reader=lambda: reads.append(True) or SECRET)
    try:
        manager = h.worker.provider_manager
        path, entropy = manager.store.path, manager.store.entropy
        refs = dict(manager._credential_refs)
        manager._settings["selected_provider"] = "codex"
        manager._settings["selected_models"] = {"codex": "gpt-6-astra"}
        def serve(request):
            assert request.headers["authorization"] == "Bearer " + SECRET
            calls.append((request.method, str(request.url)))
            return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}, {"id": "unapproved"}]})
        manager._http_transport = httpx.MockTransport(serve)
        assert reads == calls == []
        for action in ("connect", "refresh", "forget"):
            reply = h.request("credential." + action, {"provider_id": "opencode-go"})
            assert reply["result"]["tag"] == "credentials", reply
            assert SECRET not in json.dumps(reply)
        assert reads == [True]
        assert calls == [("GET", BASE_URLS["opencode-go"] + "/models")] * 2
        assert manager._settings["selected_provider"] == "codex"
        assert manager._settings["selected_models"] == {"codex": "gpt-6-astra"}
        assert manager._credential_refs == refs
        assert (manager.store.path, manager.store.entropy) == (path, entropy)
        reopened = ProviderManager(manager.paths)
        assert "opencode-go" not in reopened._settings["connections"]
        assert reopened._credential_refs["opencode-go"] == refs["opencode-go"]
        assert SECRET.encode() not in path.read_bytes()
        assert not list(tmp_path.rglob("*.sqlite*"))
    finally:
        h.close()
    captured = capsys.readouterr()
    assert SECRET not in caplog.text + captured.out + captured.err


@pytest.mark.parametrize("field,value", [("action", "forget"), ("provider_id", "codex"),
    ("credential_ref", "wrong"), ("credential_revision", 12), ("retention", "temporary"),
    ("expires_at_ms", 1)])
def test_credential_authority_mismatch_denies_before_secret_or_remote(tmp_path, field, value):
    reads = []
    h = harness(tmp_path, reader=lambda: reads.append(True) or SECRET)
    try:
        reply = send_modified(h, "credential.connect", lambda a: a.update({field: value}))
        assert reply["result"]["tag"] == "error", reply
        assert reply["result"]["code"] in {"credential_authority_invalid", "credential_authority_expired"}
        assert reads == [] and not h.worker.provider_manager.store.path.exists()
    finally:
        h.close()


def test_full_command_identity_binding_precedes_secret_read(tmp_path):
    reads = []
    h = harness(tmp_path, reader=lambda: reads.append(True) or SECRET)
    try:
        reply = send_modified(h, "credential.connect", lambda a: a["identity"].update(request_id="different"))
        assert reply["result"]["code"] == "credential_authority_invalid"
        assert reads == []
    finally:
        h.close()


def test_revoke_between_catalogue_return_and_credential_publication_rolls_back_ram_and_disk(tmp_path, monkeypatch):
    h = harness(tmp_path)
    try:
        manager = h.worker.provider_manager
        manager._http_transport = httpx.MockTransport(lambda r: httpx.Response(200,
            json={"data": [{"id": "mimo-v2.6-pro"}]}))
        catalog = manager._fetch_catalog
        async def stale_after_remote(provider, token):
            result = await catalog(provider, token)
            with h.worker.lock:
                h.worker.revisions = h.worker.revisions.model_copy(update={"grant": 13})
            return result
        monkeypatch.setattr(manager, "_fetch_catalog", stale_after_remote)
        reply = h.request("credential.connect", {"provider_id": "opencode-go"})
        assert reply["outcome"] == "cancelled_settled", reply
        assert "opencode-go" not in manager._settings["connections"]
        assert "opencode-go" not in ProviderManager(manager.paths)._settings["connections"]
        assert not manager.store.path.exists()
    finally:
        h.close()


def test_authority_replay_tombstone_prevents_second_http(tmp_path):
    h = harness(tmp_path)
    calls = []
    try:
        manager = h.worker.provider_manager
        manager._settings["connections"]["opencode-go"] = {"access_token": SECRET}
        manager._http_transport = httpx.MockTransport(lambda r: calls.append(str(r.url)) or
            httpx.Response(200, json={"data": []}))
        value = h.value("credential.refresh", {"provider_id": "opencode-go"})
        assert h.wait(h.send(value))["result"]["tag"] == "credentials"
        second = h.value("credential.refresh", {"provider_id": "opencode-go"})
        second["input"]["authority"]["authority_id"] = value["input"]["authority"]["authority_id"]
        second["payload_sha256"] = payload_digest(second["input"])
        assert h.wait(h.send(second))["result"]["code"] == "credential_authority_replayed"
        assert len(calls) == 1
    finally:
        h.close()


def test_exact_credential_url_method_and_idle_scope_denied(tmp_path):
    h = harness(tmp_path)
    try:
        value = h.value("credential.connect", {"provider_id": "opencode-go"})
        authority = CredentialAuthority.model_validate_json(json.dumps(value["input"]["authority"]))
        lease = CredentialLease(authority, lambda: True)
        endpoint = BASE_URLS["opencode-go"] + "/models"
        lease.endpoint("GET", endpoint)
        for method, url in [("POST", endpoint), ("GET", endpoint + "?key=x"),
            ("GET", endpoint + "/"), ("GET", endpoint.replace("https:", "http:")),
            ("GET", endpoint.replace("opencode.ai", "opencode.ai.evil.example")),
            ("POST", TOKEN_URL), ("GET", BASE_URLS["codex"] + "/models")]:
            with pytest.raises(CredentialRefused, match="credential_endpoint_denied"):
                lease.endpoint(method, url)
        async def idle():
            owner = credential_owner(h.worker.provider_manager)
            with pytest.raises(CredentialRefused, match="broker_authority_unbound"):
                async with h.worker.provider_manager._client() as client:
                    await client.get(endpoint)
        asyncio.run(idle())
    finally:
        h.close()


def test_product_credential_http_uses_exact_socket_guard_and_keeps_sibling_offline(tmp_path, monkeypatch):
    h = harness(tmp_path)
    seen = []
    try:
        async def guarded(endpoint):
            assert endpoint == BASE_URLS["opencode-go"] + "/models"
            loop = asyncio.get_running_loop()
            async def resolve(host, port, **kwargs):
                assert host == "opencode.ai" and port == 443
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.19", 443))]
            monkeypatch.setattr(loop, "getaddrinfo", resolve)
            async with endpoint_network(endpoint):
                yield
        monkeypatch.setattr("renulus.workers.transport_guard.endpoint_network", asynccontextmanager(guarded))
        async def single(client, request):
            assert permitted_connection(("192.0.2.19", 443))
            assert not permitted_connection(("192.0.2.19", 80))
            assert not permitted_connection(("192.0.2.20", 443))
            seen.append(str(request.url))
            return httpx.Response(200, json={"data": []}, request=request)
        monkeypatch.setattr(httpx.AsyncClient, "_send_single_request", single)
        reply = h.request("credential.connect", {"provider_id": "opencode-go"})
        assert reply["result"]["tag"] == "credentials", reply
        assert seen == [BASE_URLS["opencode-go"] + "/models"]
        assert not permitted_connection(("192.0.2.19", 443))
    finally:
        h.close()


def install_oauth(manager, *, block=None):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="synthetic", use="sig", alg="RS256")
    calls = []
    entered, cleanup, finish = Event(), Event(), Event()
    async def serve(request):
        url = str(request.url)
        calls.append((request.method, url))
        if url == block:
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleanup.set()
                while not finish.is_set():
                    await asyncio.sleep(0.01)
        if url == TOKEN_URL:
            body = parse_qs(request.content.decode())
            response = {"token_type": "Bearer", "access_token": SECRET,
                "refresh_token": "SYNTHETIC_REFRESH", "expires_in": 600, "scope": SCOPES}
            if body["grant_type"] == ["authorization_code"]:
                attempt = next(iter(manager.auth._attempts.values()))
                now = int(time.time())
                response["id_token"] = jwt.encode({"iss": ISSUER, "aud": "synthetic-issued-client",
                    "sub": "synthetic-subject", "iat": now, "exp": now + 600, "nonce": attempt.nonce},
                    key, algorithm="RS256", headers={"kid": "synthetic"})
            return httpx.Response(200, json=response)
        if url == JWKS_URL:
            return httpx.Response(200, json={"keys": [jwk]})
        if url == BASE_URLS["codex"] + "/models":
            return httpx.Response(200, json={"data": [{"id": "gpt-6.1-sol"}]})
        if url == REVOKE_URL:
            return httpx.Response(200, json={})
        pytest.fail("unexpected credential endpoint")
    manager._http_transport = httpx.MockTransport(serve)
    return calls, entered, cleanup, finish


async def callback(h, login):
    query = parse_qs(urlsplit(login["authorization_url"]).query)
    async with httpx.AsyncClient(trust_env=False, timeout=5) as local:
        return await local.get(query["redirect_uri"][0], params={"state": query["state"][0],
            "code": "synthetic-code", "client_id": "synthetic-issued-client"})


def test_oauth_callback_after_completed_connect_then_explicit_refresh_and_remote_revoke(tmp_path, caplog):
    h = harness(tmp_path)
    try:
        manager = h.worker.provider_manager
        manager._settings["selected_provider"] = "opencode-go"
        manager._settings["selected_models"] = {"opencode-go": "deepseek-v4.1-flash"}
        calls, _, _, _ = install_oauth(manager)
        login = h.request("credential.connect", {"provider_id": "codex"})["result"]
        assert login["login_status"] == "pending" and h.worker.jobs == {}
        assert calls == []
        assert asyncio.run(callback(h, login)).status_code == 200
        assert manager.auth.status(login["login_id"])["status"] == "connected"
        owner = credential_owner(manager)
        wait_for(lambda: not owner.logins and not owner.monitors)
        assert calls == [("POST", TOKEN_URL), ("GET", JWKS_URL), ("GET", BASE_URLS["codex"] + "/models")]
        assert manager._settings["selected_provider"] == "opencode-go"
        assert manager._settings["selected_models"] == {"opencode-go": "deepseek-v4.1-flash"}
        manager._settings["connections"]["codex"]["expires_at"] = 0
        refresh = h.request("credential.refresh", {"provider_id": "codex"})
        assert refresh["result"]["tag"] == "credentials", refresh
        assert calls[-2:] == [("POST", TOKEN_URL), ("GET", BASE_URLS["codex"] + "/models")]
        forgotten = h.request("credential.forget", {"provider_id": "codex"})
        assert forgotten["result"]["tag"] == "credentials", forgotten
        assert calls[-1] == ("POST", REVOKE_URL)
        assert "codex" not in ProviderManager(manager.paths)._settings["connections"]
        assert SECRET not in json.dumps(h.replies) + caplog.text
        assert SECRET.encode() not in manager.store.path.read_bytes()
    finally:
        h.close()


def test_rejected_oauth_callback_keeps_legitimate_pending_login(tmp_path):
    h = harness(tmp_path)
    try:
        manager = h.worker.provider_manager
        calls, _, _, _ = install_oauth(manager)
        login = h.request("credential.connect", {"provider_id": "codex"})["result"]
        query = parse_qs(urlsplit(login["authorization_url"]).query)

        async def forged():
            async with httpx.AsyncClient(trust_env=False, timeout=5) as local:
                return await local.get(query["redirect_uri"][0], params={"state": "forged",
                    "code": "forged-code", "client_id": "synthetic-issued-client"})
        assert asyncio.run(forged()).status_code == 400
        time.sleep(0.2)
        assert manager.auth.status(login["login_id"])["status"] == "pending"
        assert login["login_id"] in credential_owner(manager).logins and calls == []
        assert asyncio.run(callback(h, login)).status_code == 200
        assert manager.auth.status(login["login_id"])["status"] == "connected"
        wait_for(lambda: not credential_owner(manager).logins and not credential_owner(manager).monitors)
    finally:
        h.close()


@pytest.mark.parametrize("control", ["revoke", "close", "expiry", "login-cancel"])
def test_oauth_revoke_close_expiry_cancel_close_listener_and_fence_late_callback(tmp_path, control):
    h = harness(tmp_path)
    try:
        manager = h.worker.provider_manager
        calls, _, _, _ = install_oauth(manager)
        value = h.value("credential.connect", {"provider_id": "codex"})
        if control == "expiry":
            value["input"]["authority"]["expires_at_ms"] = int(time.time() * 1000) + 180
            value["payload_sha256"] = payload_digest(value["input"])
        login = h.wait(h.send(value))["result"]
        assert login["login_status"] == "pending", login
        attempt = manager.auth._attempts[login["login_id"]]
        old_state = attempt.state
        if control == "expiry":
            wait_for(lambda: attempt.server is None)
        elif control == "login-cancel":
            cancelled = h.request("credential.login-cancel", {"provider_id": "codex", "login_id": login["login_id"]})
            assert cancelled["result"]["login_status"] == "cancelled", cancelled
        else:
            input = {"action": control}
            if control == "revoke":
                input["revisions"] = h.worker.revisions.model_copy(update={"grant": 13}).model_dump()
            h.request("worker.settle", input)
            wait_for(lambda: attempt.server is None)
        wait_for(lambda: not credential_owner(manager).logins)
        assert attempt.state == attempt.verifier == attempt.nonce == ""
        async def stale():
            with pytest.raises(CredentialRefused):
                await manager.auth.complete(login["login_id"], {"state": old_state,
                    "code": "late-code", "client_id": "synthetic-issued-client"})
        future = asyncio.run_coroutine_threadsafe(stale(), h.worker.credential_loop)
        future.result(5)
        assert calls == []
        assert "codex" not in manager._settings["connections"]
    finally:
        h.close()


@pytest.mark.parametrize("url", [TOKEN_URL, JWKS_URL, BASE_URLS["codex"] + "/models"])
def test_oauth_inflight_revoke_holds_actual_cleanup_and_never_publishes(tmp_path, url):
    h = harness(tmp_path)
    client_done = Event()
    try:
        manager = h.worker.provider_manager
        calls, entered, cleanup, finish = install_oauth(manager, block=url)
        login = h.request("credential.connect", {"provider_id": "codex"})["result"]
        async def local():
            try:
                return await callback(h, login)
            finally:
                client_done.set()
        future = asyncio.run_coroutine_threadsafe(local(), h.worker.credential_loop)
        assert entered.wait(4)
        ack = h.request("worker.settle", {"action": "revoke",
            "revisions": h.worker.revisions.model_copy(update={"grant": 13}).model_dump()})
        assert ack["settlement"]["state"] == "pending", ack
        assert cleanup.wait(4)
        assert not client_done.is_set()
        # Repeated host closure must not cancel the remote client's cleanup.
        closed = h.request("worker.settle", {"action": "close"})
        assert closed["settlement"]["state"] == "pending"
        assert not client_done.is_set()
        finish.set()
        future.result(5)
        wait_for(lambda: h.worker.credential_cleanup.done())
        assert "codex" not in manager._settings["connections"]
        assert "codex" not in ProviderManager(manager.paths)._settings["connections"]
        assert SECRET.encode() not in manager.store.path.read_bytes()
        assert manager.auth._attempts[login["login_id"]].server is None
    finally:
        if "finish" in locals():
            finish.set()
        h.close()


def test_pending_oauth_credential_revision_change_closes_retained_lease(tmp_path):
    h = harness(tmp_path)
    try:
        manager = h.worker.provider_manager
        calls, _, _, _ = install_oauth(manager)
        login = h.request("credential.connect", {"provider_id": "codex"})["result"]
        # Synthetic exact analogue of a newly published credential generation.
        manager._credential_epochs["codex"] += 1
        wait_for(lambda: not credential_owner(manager).logins)
        assert manager.auth._attempts[login["login_id"]].server is None
        assert calls == [] and "codex" not in manager._settings["connections"]
    finally:
        h.close()


def test_native_secret_pending_cancel_retains_job_until_reader_settles(tmp_path):
    entered, finish = Event(), Event()
    def read():
        entered.set()
        finish.wait(5)
        return SECRET
    h = harness(tmp_path, reader=read)
    try:
        value = h.value("credential.connect", {"provider_id": "opencode-go"})
        h.send(value)
        assert entered.wait(4)
        ack = h.request("worker.settle", {"action": "close"})
        assert ack["settlement"]["state"] == "pending"
        assert value["request_id"] in h.worker.jobs
        finish.set()
        terminal = h.wait(value)
        assert terminal["outcome"] == "cancelled_settled"
        assert "opencode-go" not in h.worker.provider_manager._settings["connections"]
    finally:
        finish.set()
        h.close()
