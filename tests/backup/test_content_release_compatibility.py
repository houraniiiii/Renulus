# SPDX-License-Identifier: MIT
"""Real published-pack recovery preserves both learner history and local selection."""
import asyncio
from contextlib import contextmanager
import io
import json
import socket
import zipfile

from fastapi.testclient import TestClient
import pytest

from renulus import server


@pytest.fixture
def profiles(tmp_path_factory, monkeypatch):
    root = tmp_path_factory.mktemp("release-recovery")
    attempts = []

    class NoProvider:
        async def stream(self, *args, **kwargs):
            attempts.append("generation")
            raise AssertionError("Content recovery must not call a provider")
            yield
        async def cancel(self, *args, **kwargs):
            attempts.append("provider-cancellation")
            raise AssertionError("No provider operation is expected")

    def guard_connect(operation):
        def connect(sock, address):
            if not isinstance(address, tuple) or address[0] not in ("localhost", "127.0.0.1", "::1"):
                attempts.append("external-network")
                raise AssertionError("Recovery compatibility uses no external network")
            return operation(sock, address)
        return connect
    monkeypatch.setattr(socket.socket, "connect", guard_connect(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect(socket.socket.connect_ex))

    @contextmanager
    def profile(name, version=None, *, reopen=False):
        path = root / name
        assert path.exists() is reopen
        # Exercise the integrator's supported bootstrap selection before routers
        # initialise; the source genuinely installs only the released 1.0.0 pack.
        original_services = server.Services
        def selected_services(*args, **kwargs):
            services = original_services(*args, **kwargs)
            services.registry["content_pack_selection"] = {"version": version}
            return services
        with monkeypatch.context() as selection:
            if version is not None:
                selection.setattr(server, "Services", selected_services)
            app = server.create_app(path)
        services = app.state.services
        services.registry["provider"] = NoProvider()
        client = TestClient(app)
        try:
            yield client, services
        finally:
            client.close()
            services.registry["knowledge"].index.close()
            asyncio.run(services.registry["memory"].close())
            services.registry["helpers"].startup.close()

    yield profile
    assert attempts == []


def succeeded(response, code=200):
    assert response.status_code == code, response.text
    return response.json()


def learner_records(client, content, prefix):
    thread = succeeded(client.post("/api/v1/learn/threads", json={
        "title": "SYNTHETIC " + prefix + " study thread", "topic_id": "ckd"}))
    note = succeeded(client.post("/api/v1/memory/facts", json={
        "text": "SYNTHETIC " + prefix + " learner preference: revisit transplantation mechanisms",
        "kind": "preference", "topic_id": "transplant", "scope": {"kind": "study"},
        "idempotency_key": prefix + "-note"}), 201)
    session = succeeded(client.post("/api/v1/assessment/start", json={
        "count": 2, "idempotency_key": prefix + "-session"}))
    item = session["current_item"]
    key = content.get_question_version(item["question_id"], int(item["question_version"]))
    request = {"item_id": item["id"], "option_ids": key["correct_option_ids"],
        "idempotency_key": prefix + "-answer"}
    answered = succeeded(client.post(f"/api/v1/assessment/sessions/{session['id']}/answer", json=request))
    assert answered["feedback"]["correct"] is True
    reviewed = succeeded(client.get(f"/api/v1/assessment/sessions/{session['id']}/review"))
    teaching = succeeded(client.get("/api/v1/content/cases"))[0]
    case = succeeded(client.post("/api/v1/cases/sessions", json={
        "kind": "teaching", "teaching_case_id": teaching["id"]}), 201)
    case = succeeded(client.post(f"/api/v1/cases/sessions/{case['id']}/reveal",
        json={"revision": case["revision"]}))
    case = succeeded(client.post(f"/api/v1/cases/sessions/{case['id']}/save",
        json={"revision": case["revision"]}))
    assert case["saved"] and case["teaching"]["revealed_count"] == 2
    return {"thread": thread, "note": note, "session": answered["session"],
        "request": request, "answered": answered, "review": reviewed, "case": case}


def assert_learner_records(client, records):
    thread = succeeded(client.get(f"/api/v1/learn/threads/{records['thread']['id']}"))
    assert thread["title"] == records["thread"]["title"]
    note = succeeded(client.get(f"/api/v1/memory/facts/{records['note']['id']}"))
    assert (note["text"], note["revision"], note["kind"]) == (
        records["note"]["text"], records["note"]["revision"], records["note"]["kind"])
    identifier = records["session"]["id"]
    replay = succeeded(client.post(f"/api/v1/assessment/sessions/{identifier}/answer", json=records["request"]))
    assert replay == records["answered"]
    review = succeeded(client.get(f"/api/v1/assessment/sessions/{identifier}/review"))
    assert review["feedback"] == records["review"]["feedback"]
    case = succeeded(client.get(f"/api/v1/cases/sessions/{records['case']['id']}"))
    assert case["saved"] and case["revision"] == records["case"]["revision"]
    for field in ("id", "version", "revealed_count", "stages"):
        assert case["teaching"][field] == records["case"]["teaching"][field]


def export_legacy(client, kind):
    response = client.get("/api/v1/data/export" if kind == "json" else "/api/v1/data/backup")
    assert response.status_code == 200, response.text
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            records = json.loads(archive.read("records.json"))
    else:
        records = response.json()
    assert [row["version"] for row in records["records"]["content_packs"]] == ["1.0.0"]
    assert records["records"]["content_active_pack"] == [{
        "slot": 1, "pack_id": "renulus-foundations", "pack_version": "1.0.0"}]
    return response.content, records


def restore_backup(client, kind, archive, records):
    if kind == "json":
        return succeeded(client.post("/api/v1/data/restore", json={"bundle": records,
            "confirm_backup_date": True, "confirmed_exported_at": records["exported_at"]}))
    checked = succeeded(client.post("/api/v1/data/backup/preview", content=archive,
        headers={"content-type": "application/zip"}))
    return succeeded(client.post("/api/v1/data/backup/restore", json={
        "preview_token": checked["preview_token"], "confirmed_exported_at": checked["exported_at"],
        "acknowledge_deletion_limits": True}))


def assert_current_bank(client):
    assert succeeded(client.get("/api/v1/content/manifest"))["version"] == "1.1.0"
    assert len(succeeded(client.get("/api/v1/content/questions"))) == 160
    assert len(succeeded(client.get("/api/v1/content/cases"))) == 26


@pytest.mark.parametrize("kind", ["json", "zip"])
def test_legacy_100_backup_keeps_historical_keys_and_sessions_without_downgrading_110_target(profiles, kind):
    with profiles("legacy", "1.0.0") as (client, services):
        content = services.registry["content"]
        assert content.active_manifest()["version"] == "1.0.0"
        historical_keys = {item["id"]: content.get_question_version(item["id"], item["version"])
            for item in content.list_question_summaries()}
        legacy = learner_records(client, content, "legacy")
        archive, records = export_legacy(client, kind)

    with profiles("target") as (client, services):
        assert_current_bank(client)
        target = learner_records(client, services.registry["content"], "target")
        before_keys = {item["id"]: services.registry["content"].get_question_version(item["id"], item["version"])
            for item in services.registry["content"].list_question_summaries()}
        restored = restore_backup(client, kind, archive, records)
        assert restored["restored_records"] > 0
        assert_current_bank(client)
        assert_learner_records(client, legacy)
        assert_learner_records(client, target)
        for identifier, snapshot in historical_keys.items():
            assert services.registry["content"].get_question_version(identifier, snapshot["version"]) == snapshot
        for identifier, snapshot in before_keys.items():
            assert services.registry["content"].get_question_version(identifier, snapshot["version"]) == snapshot
        assert {item["id"] for item in succeeded(client.get("/api/v1/memory/facts"))["records"]} == {
            legacy["note"]["id"], target["note"]["id"]}
        assert restore_backup(client, kind, archive, records)["restored_records"] == 0
        assert_current_bank(client)

    with profiles("target", reopen=True) as (client, services):
        assert_current_bank(client)
        assert_learner_records(client, legacy)
        assert_learner_records(client, target)
        identifier = legacy["session"]["id"]
        current = succeeded(client.get(f"/api/v1/assessment/sessions/{identifier}"))
        item = current["current_item"]
        key = historical_keys[item["question_id"]]
        finished = succeeded(client.post(f"/api/v1/assessment/sessions/{identifier}/answer", json={
            "item_id": item["id"], "option_ids": key["correct_option_ids"], "idempotency_key": "legacy-resumed-answer"}))
        assert finished["feedback"]["correct"] is True
        assert finished["feedback"]["explanation"] == key["rationale"]
        assert finished["feedback"]["item"]["question_version"] == str(key["version"])
        assert finished["feedback"]["item"]["key_version"] == str(key["key_version"])
        assert_current_bank(client)
