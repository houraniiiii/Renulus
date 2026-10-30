"""Authenticated worker broker path, synthetic accounts/transport only."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from threading import Condition, Event
import time
from uuid import uuid4

import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from renulus.worker_contracts import (COMMAND, Identity, OutputGrant,
    PRODUCT_ENDPOINTS, payload_digest)
from renulus.workers.broker import ProtectedBroker
from renulus.workers.broker_models import NativeHeader, NativeRequest, TransportPlan, TransportRoute
from renulus.workers.generate import schema_document
from renulus.workers.runtime import Worker
from .support import Process, command, config, output, target

SECRET = "SYNTHETIC_WORKER_CREDENTIAL_SENTINEL"
BODY = b'data: {"choices":[{"delta":{"content":"Synthetic transplant study"}}]}\n\ndata: [DONE]\n\n'


def launch(tmp_path, *, retention="saved", **changes):
    identity = config().identity.model_copy(update={"process_generation": "pg_" + uuid4().hex})
    root = tmp_path / "synthetic-profile"
    return config(identity=identity, retention=retention,
        broker={"profile_root": str(root), "state_root": str(root / "state")}, **changes)


def transport_command(launch, *, reference="credential_synthetic", revision=0, permit=None):
    value = command("transport.execute", {}, identity=launch.identity, revisions=launch.revisions,
                    retention=launch.retention)
    raw = b'{ "stream": true, "model": "mimo-v2.6-pro", "max_completion_tokens": 32, "messages": [] }'
    headers = {"content-type": "application/json", "accept": "text/event-stream"}
    envelope = {"method": "POST", "url": PRODUCT_ENDPOINTS[1], "headers": headers,
                "body_base64": base64.b64encode(raw).decode()}
    plan = TransportPlan(permit_id=permit or uuid4().hex, admission_receipt="admission_" + uuid4().hex,
        identity=Identity(**{k: value[k] for k in Identity.model_fields}), revisions=launch.revisions,
        retention=launch.retention, route=TransportRoute(provider_id="opencode-go", model_id="mimo-v2.6-pro",
            wire_model_id="mimo-v2.6-pro", endpoint=PRODUCT_ENDPOINTS[1], protocol="openai-chat",
            credential_ref=reference, credential_revision=revision),
        native_manifest_sha256="a" * 64, registry_sha256="b" * 64,
        request_sha256=hashlib.sha256(raw).hexdigest(), request_bytes=len(raw),
        envelope_sha256=payload_digest(envelope), max_output_tokens=32,
        expires_at_ms=int(time.time() * 1000) + 60000, output=OutputGrant(**output(max_bytes=4096)),
        serialized_request=NativeRequest(method="POST", url=envelope["url"],
            headers=tuple(NativeHeader(name=k, value=v) for k, v in headers.items()),
            body_base64=envelope["body_base64"]))
    value["input"] = plan.model_dump(mode="json")
    value["payload_sha256"] = payload_digest(value["input"])
    return value


class Harness:
    def __init__(self, launch, **kwargs):
        self.launch, self.replies, self.condition = launch, [], Condition()
        self.worker = Worker(launch, launch.capacity, self.emit, engines=object(), **kwargs)

    def emit(self, reply):
        with self.condition:
            self.replies.append(reply.model_dump(mode="json"))
            self.condition.notify_all()

    def send(self, value):
        self.worker.handle(COMMAND.validate_json(json.dumps(value)), value["input"])
        return value

    def value(self, name, input, **kwargs):
        value = command(name, input, identity=self.launch.identity, retention=self.launch.retention,
                       revisions=self.worker.revisions, **kwargs)
        if name.startswith("credential.") and name not in {"credential.activate", "credential.metadata"}:
            provider = input["provider_id"]
            manager = self.worker.provider_manager
            value["input"] = {**input, "authority": {"authority_id": "authority_" + uuid4().hex,
                "source": "settings", "action": name.split(".")[1], "provider_id": provider,
                "identity": {key: value[key] for key in Identity.model_fields},
                "revisions": self.worker.revisions.model_dump(), "retention": self.launch.retention,
                "credential_ref": manager._credential_refs[provider],
                "credential_revision": manager._credential_epochs[provider],
                "expires_at_ms": int(time.time() * 1000) + 60000}}
            value["payload_sha256"] = payload_digest(value["input"])
        return value

    def wait(self, value, *, terminal=True):
        terminal = terminal and value["command"] != "worker.settle"
        with self.condition:
            def matches():
                return [r for r in self.replies if r["identity"]["request_id"] == value["request_id"]
                        and (not terminal or r["settlement"]["state"] != "pending")]
            assert self.condition.wait_for(lambda: bool(matches()), timeout=10), self.replies
            return matches()[-1]

    def request(self, name, input):
        return self.wait(self.send(self.value(name, input)))

    def activate(self):
        reply = self.request("credential.activate", {})
        assert reply["result"]["tag"] == "credentials", reply
        return next(row for row in reply["result"]["credentials"] if row["provider_id"] == "opencode-go")

    def close(self):
        self.worker.disconnect()


class Stream(httpx.AsyncByteStream):
    def __init__(self, *, block=False):
        self.block = block
        self.entered, self.cleanup, self.finish, self.closed = Event(), Event(), Event(), Event()

    async def __aiter__(self):
        self.entered.set()
        if self.block:
            await asyncio.Event().wait()
        yield BODY

    async def aclose(self):
        self.cleanup.set()
        if self.block:
            while not self.finish.is_set():
                await asyncio.sleep(0.005)
        self.closed.set()


def injection(*, stream=None):
    """Keep real broker validation/guards/cleanup, inject HTTP after validation.

    Product command URLs are never replaced or loosened. This Python-only
    factory installs MockTransport immediately inside the admitted _http seam;
    nothing opens a socket or consumes an account.
    """
    calls, scopes = [], []
    class SyntheticBroker(ProtectedBroker):
        def __init__(self, launch, *, manager=None):
            super().__init__(launch, manager=manager)
            scopes.append(self)

        def activate_credentials(self, *, check_current):
            manager = super().activate_credentials(check_current=check_current)
            manager._settings["connections"]["opencode-go"] = {"access_token": SECRET}
            return manager

        async def _http(self, plan, attempt, body, headers, check_current, cancel):
            def serve(request):
                calls.append((str(request.url), request.content,
                    request.headers["authorization"] == "Bearer " + SECRET))
                return httpx.Response(200, headers={"content-type": "text/event-stream",
                    "authorization": SECRET, "set-cookie": SECRET}, stream=stream or Stream())
            self.synthetic_transport = httpx.MockTransport(serve)
            return await super()._http(plan, attempt, body, headers, check_current, cancel)
    return SyntheticBroker, calls, scopes


def test_authenticated_stdio_no_account_requires_explicit_activation_before_http(tmp_path):
    cfg = launch(tmp_path)
    with Process(tmp_path / "process", launch=cfg) as worker:
        ready = worker.start()
        assert "transport.execute" in ready["supported_commands"]
        assert "credential.activate" in ready["supported_commands"]
        value = transport_command(cfg)
        refused = worker.request(value)
        assert refused["result"]["tag"] == "transport", refused
        assert refused["result"]["code"] == "broker_not_activated"
        assert refused["outcome"] == "rejected_before_admission"
        assert refused["result"]["effect"] == "not_sent"
        assert refused["result"]["network_started"] is False
        assert refused["result"]["artifact"] is None
        assert not (tmp_path / "synthetic-profile").exists()
        activated = worker.request(command("credential.activate", {}, identity=cfg.identity))
        assert activated["result"]["tag"] == "credentials"
        assert all(not row["configured"] and not row["usable"] for row in activated["result"]["credentials"])
        go = next(row for row in activated["result"]["credentials"] if row["provider_id"] == "opencode-go")
        value = transport_command(cfg, reference=go["credential_ref"], revision=go["credential_revision"])
        refused = worker.request(value)
        assert refused["result"]["code"] == "authentication_required", refused
        assert refused["result"]["network_started"] is False
        assert refused["result"]["effect"] == "not_sent"
    assert worker.process.returncode == 0
    assert not list(tmp_path.rglob("*.sqlite*"))
    assert not list(tmp_path.rglob("*.dpapi"))


@pytest.mark.parametrize("retention", ["saved", "temporary"])
def test_exact_artifact_response_shared_activation_and_permit_tombstones(tmp_path, retention, caplog, capsys):
    factory, calls, scopes = injection()
    harness = Harness(launch(tmp_path, retention=retention), broker_factory=factory)
    try:
        assert harness.worker.provider_manager is None and scopes == []
        credential = harness.activate()
        manager = harness.worker.provider_manager
        value = transport_command(harness.launch, reference=credential["credential_ref"])
        reply = harness.wait(harness.send(value))
        result = reply["result"]
        assert reply["outcome"] == "committed_reference", reply
        assert result["tag"] == "transport" and result["effect"] == "response_received"
        artifact = result["artifact"]
        assert artifact["artifact_handle"] == value["input"]["output"]["artifact_handle"]
        assert artifact["artifact_sha256"] == hashlib.sha256(BODY).hexdigest()
        assert artifact["bytes"] == len(BODY)
        read = harness.request("artifact.read", {"artifact_handle": artifact["artifact_handle"],
            "artifact_revision": artifact["artifact_revision"], "offset": 0, "length": 262144})
        assert base64.b64decode(read["result"]["data_base64"]) == BODY
        assert calls == [(PRODUCT_ENDPOINTS[1], base64.b64decode(value["input"]["serialized_request"]["body_base64"]), True)]
        assert scopes[-1].launch.native_manifest_sha256 == "a" * 64
        assert scopes[-1].launch.registry_sha256 == "b" * 64
        assert scopes[-1].manager is manager and scopes[-1].closed
        replay = transport_command(harness.launch, reference=credential["credential_ref"], permit=value["input"]["permit_id"])
        replayed = harness.wait(harness.send(replay))
        assert replayed["result"]["code"] == "transport_permit_replayed"
        assert len(calls) == 1 and scopes[-1].manager is manager
        harness.request("worker.settle", {"action": "release", "artifact_handle": artifact["artifact_handle"]})
        assert harness.worker.artifacts.used == 0
        serialized = json.dumps([reply, replayed])
        assert BODY.decode() not in serialized and "body_base64" not in serialized
        assert SECRET not in serialized + caplog.text
        assert "set-cookie" not in serialized and "authorization" not in serialized
    finally:
        harness.close()
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert all(BODY not in p.read_bytes() and SECRET.encode() not in p.read_bytes()
               for p in tmp_path.rglob("*") if p.is_file())


@pytest.mark.parametrize("action", ["cancel", "revoke", "release", "close"])
def test_transport_controls_retain_reservation_until_actual_http_cleanup(tmp_path, action):
    stream = Stream(block=True)
    factory, calls, _ = injection(stream=stream)
    harness = Harness(launch(tmp_path), broker_factory=factory)
    try:
        credential = harness.activate()
        value = transport_command(harness.launch, reference=credential["credential_ref"])
        harness.send(value)
        pending = harness.wait(value, terminal=False)
        assert pending["settlement"]["state"] == "pending"
        assert stream.entered.wait(3)
        control = {"action": action}
        if action == "cancel":
            control["target"] = target(pending)
        elif action == "revoke":
            control["revisions"] = harness.worker.revisions.model_copy(update={"grant": 13}).model_dump()
        elif action == "release":
            control["artifact_handle"] = value["input"]["output"]["artifact_handle"]
        ack = harness.request("worker.settle", control)
        assert ack["settlement"]["state"] == "pending", ack
        assert stream.cleanup.wait(3)
        assert not stream.closed.is_set()
        assert harness.worker.artifacts.used == 4096
        assert value["request_id"] in harness.worker.jobs
        stream.finish.set()
        terminal = harness.wait(value)
        assert stream.closed.is_set()
        assert terminal["outcome"] == "cancelled_settled", terminal
        assert terminal["result"]["tag"] == "transport"
        assert terminal["result"]["artifact"] is None
        assert terminal["result"]["effect"] == "uncertain"
        assert terminal["settlement"]["worker_lease"] == pending["settlement"]["worker_lease"]
        assert harness.worker.artifacts.used == 0 and len(calls) == 1
        queried = harness.request("worker.settle", {"action": "query", "target": target(pending)})
        assert queried["settlement"]["state"] == "settled"
    finally:
        stream.finish.set()
        harness.close()


def test_transport_plan_and_envelope_binding_precede_reservation_or_broker(tmp_path):
    factory, calls, scopes = injection()
    harness = Harness(launch(tmp_path), broker_factory=factory)
    try:
        value = transport_command(harness.launch)
        value["operation_id"] = "different_operation"
        refused = harness.wait(harness.send(value))
        assert refused["outcome"] == "rejected_before_admission"
        assert refused["result"]["code"] == "stale_identity"
        assert scopes == calls == [] and harness.worker.artifacts.used == 0
    finally:
        harness.close()


def test_product_only_command_schema_and_no_json_secret_or_path(tmp_path):
    cfg = launch(tmp_path)
    validator = Draft202012Validator(schema_document())
    value = transport_command(cfg)
    validator.validate(value)
    for endpoint in ("http://127.0.0.1:9/chat/completions", "https://other.example/chat/completions"):
        invalid = json.loads(json.dumps(value))
        invalid["input"]["route"]["endpoint"] = endpoint
        invalid["input"]["serialized_request"]["url"] = endpoint
        with pytest.raises(ValidationError):
            COMMAND.validate_json(json.dumps(invalid))
        assert not validator.is_valid(invalid)
    for field in ("secret", "secret_reader", "path", "synthetic_endpoints"):
        invalid = command("credential.connect", {"provider_id": "opencode-go", field: SECRET})
        with pytest.raises(ValidationError):
            COMMAND.validate_json(json.dumps(invalid))
        assert not validator.is_valid(invalid)


def test_direct_credential_callback_is_host_only_and_oauth_loop_settles(tmp_path, monkeypatch):
    factory, calls, _ = injection()
    harness = Harness(launch(tmp_path), broker_factory=factory)
    try:
        harness.activate()
        def cancelled():
            raise RuntimeError("synthetic dialog cancelled")
        monkeypatch.setattr("renulus.workers.native_secret.read_go_secret", cancelled)
        refused = harness.request("credential.connect", {"provider_id": "opencode-go"})
        assert refused["result"]["code"] == "credential_command_failed"
        reads, connected = [], []
        harness.worker.secret_reader = lambda: reads.append(True) or SECRET
        async def connect_go(token, *, select):
            connected.append((token == SECRET, select))
        monkeypatch.setattr(harness.worker.provider_manager, "connect_go", connect_go)
        connected_reply = harness.request("credential.connect", {"provider_id": "opencode-go"})
        assert connected_reply["result"]["tag"] == "credentials"
        assert reads == [True] and connected == [(True, False)]
        # The existing login uses base64url IDs, including leading '-'/'_'.
        monkeypatch.setattr("renulus.runtime.auth.secrets.token_urlsafe", lambda n: "_" + "s" * (n - 1))
        login = harness.request("credential.connect", {"provider_id": "codex"})["result"]
        assert login["login_status"] == "pending", login
        login_id = login["login_id"]
        assert login_id.startswith("_")
        pending = harness.request("credential.login-status", {"provider_id": "codex", "login_id": login_id})
        assert pending["result"]["login_status"] == "pending"
        cancelled = harness.request("credential.login-cancel", {"provider_id": "codex", "login_id": login_id})
        assert cancelled["result"]["login_status"] == "cancelled"
        assert calls == []
        assert SECRET not in json.dumps(harness.replies)
    finally:
        harness.close()
