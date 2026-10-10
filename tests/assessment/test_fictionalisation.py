# SPDX-License-Identifier: MIT
"""Real selected ProviderManager, canonical publication, only transport synthetic."""
import asyncio
from copy import deepcopy
import json

import pytest

from renulus.assessment.fictionalisation import fictionalise_test, _authority, privacy_overlap
from renulus.contracts import ApiError
from renulus.design_c_contracts import FictionalTestArtifact
from renulus.server import create_app
from renulus.storage.assessment_policy import advance_policy
from renulus.storage.backup import export_records
from renulus.storage.invalidation import bump_context_epoch

RAW = "Patient name: SYNTHETIC_PRIVATE_PERSON\nidentifier: CASE_SENTINEL_928374\nDiscuss a conceptual kidney teaching point."


class Transport:
    def __init__(self):
        self.calls = []
        self.release = None
        self.started = asyncio.Event()
        self.change = None
        self.bad = None

    async def stream(self, provider, model, token, messages):
        assert token == "synthetic-fictional-token"
        payload = json.loads(messages[-1]["content"])
        self.calls.append((provider, model, deepcopy(messages)))
        self.started.set()
        if self.release is not None:
            await self.release.wait()
        if self.change:
            self.change(payload)
        if "artifact_sha256" in payload:
            output = {"schema":"fictional-test-review/1", "artifact_sha256":payload["artifact_sha256"],
                "source_identity_removed":True, "clinical_details_generalised":True, "no_source_links":True, "issues":[]}
            if self.bad == "review_false": output["clinical_details_generalised"] = False
            if self.bad == "review_string": output["source_identity_removed"] = "true"
            if self.bad == "review_digest": output["artifact_sha256"] = "0"*64
            if self.bad == "review_issues": output["issues"] = ["uncertain"]
        else:
            start = len(payload["prior_fictional_stems"])
            output = {"items":[{"stem":f"Independent fictional CKD learning question {index}",
                "options":[{"id":"a","text":"First interpretation"},{"id":"b","text":"Second interpretation"}],
                "correct_option_id":"a", "explanation":"Fictional educational rationale.", "hint":None,
                "source_indices":[]} for index in range(start,start+5)]}
            if self.bad == "identifier": output["items"][0]["stem"] += " CASE_SENTINEL_928374"
            if self.bad == "duplicate": output["items"][1]["stem"] = output["items"][0]["stem"]
            if self.bad == "key": output["items"][0]["correct_option_id"] = "unknown"
            if self.bad == "source": output["items"][0]["source_indices"] = [0]
        raw = json.dumps(output)
        if self.bad == "json": raw = "invalid"
        if self.bad == "duplicate_json": raw = raw[:-1]+',"items":[]}'
        yield {"type":"delta", "text":raw}
        yield {"type":"completed", "response_model":model}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("runtime", "content", "knowledge", "learn", "cases", "assessment", "memory", "study"))
    app = create_app(tmp_path / "owned-fictional")
    provider = app.state.services.get("provider")
    provider._settings["connections"]["codex"] = {"access_token":"synthetic-fictional-token", "expires_at":9999999999}
    provider._settings["selected_provider"] = "codex"
    provider._settings.setdefault("selected_models", {})["codex"] = "gpt-6.1-sol"
    provider._transport = Transport()
    return app


async def artifact(app, cancel=None, count=5):
    return await fictionalise_test(app.state.services, source_text=RAW, instruction="Teach the general concept", count=count,
        cancel=cancel or asyncio.Event(), expected_policy_revision=1, expected_context_epoch=0)


async def publish(app, value):
    return await app.state.services.get("saved_generation").publish_fictional_artifact(value,
        expected_policy_revision=1, expected_context_epoch=0)


def assert_private(app):
    services = app.state.services
    serialised = json.dumps(export_records(services))
    for sentinel in ("SYNTHETIC_PRIVATE_PERSON", "CASE_SENTINEL_928374", RAW):
        assert sentinel not in serialised
        assert all(sentinel.encode() not in path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file())


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [5,10,20])
async def test_transform_separate_review_publish_once_and_keep_all_raw_details_volatile(app, count):
    value = await artifact(app, count=count)
    services = app.state.services
    assert len(services.get("provider")._transport.calls) == count//5+1
    assert services.db.fetch_all("SELECT * FROM assessment_tests") == []
    first, second = await asyncio.gather(publish(app,value),publish(app,value))
    assert first == second and first["item_count"] == count
    assert len(services.db.fetch_all("SELECT * FROM assessment_test_versions")) == 1
    assert services.db.fetch_all("SELECT * FROM assessment_test_jobs") == []
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []
    assert services.db.fetch_all("SELECT * FROM memory_jobs") == []
    setup = services.get("saved_tests").setup_version(first["version_id"])
    assert setup["version"]["item_count"] == count
    assert "correct_option_ids" not in json.dumps(setup)
    with services.db.transaction() as conn:
        pinned = services.get("saved_tests").pinned_version(conn,first["version_id"])
        assert not pinned.bank_cohort_eligible and pinned.source_refs == ()
    assert_private(app)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["identifier","duplicate","key","source","json","duplicate_json","review_false","review_string","review_digest","review_issues"])
async def test_bad_transform_or_independent_review_never_mints_or_publishes(app,bad):
    app.state.services.get("provider")._transport.bad = bad
    with pytest.raises(ApiError):
        await artifact(app)
    assert _authority(app.state.services).receipts == {}
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_test_versions") == []
    assert_private(app)


@pytest.mark.asyncio
async def test_a_parsed_or_copied_artifact_is_not_producer_authority(app):
    original = await artifact(app)
    parsed = FictionalTestArtifact.model_validate(original.model_dump(mode="json"))
    with pytest.raises(ApiError) as failure:
        await publish(app,parsed)
    assert failure.value.code == "fictional_artifact_untrusted"
    assert app.state.services.db.fetch_all("SELECT * FROM assessment_tests") == []
    assert (await publish(app,original))["item_count"] == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["cancel","epoch","policy","route","connection"])
async def test_wait_and_publication_recheck_private_context_and_route(app,change):
    services = app.state.services
    cancel = asyncio.Event()
    value = await artifact(app,cancel)
    with services.db.transaction() as conn:
        if change == "cancel": cancel.set()
        if change == "epoch": bump_context_epoch(conn)
        if change == "policy": advance_policy(conn)
        if change == "route": services.get("provider")._settings["selected_provider"] = None
        if change == "connection": services.get("provider")._connection_versions["codex"] += 1
    with pytest.raises(ApiError):
        await publish(app,value)
    assert services.db.fetch_all("SELECT * FROM assessment_tests") == []
    assert_private(app)


@pytest.mark.asyncio
async def test_cancel_during_silent_provider_wait_stops_without_receipt_or_rows(app):
    cancel = asyncio.Event()
    transport = app.state.services.get("provider")._transport
    transport.release = asyncio.Event()
    task = asyncio.create_task(artifact(app,cancel))
    await asyncio.wait_for(transport.started.wait(),5)
    cancel.set()
    with pytest.raises(ApiError):
        await asyncio.wait_for(task,2)
    assert _authority(app.state.services).receipts == {}
    assert app.state.services.get("provider").status()["active_runs"] == []
    assert_private(app)


@pytest.mark.asyncio
async def test_restart_expires_authority_and_no_provider_replay(app):
    value = await artifact(app)
    services = app.state.services
    reopened = create_app(services.paths.root).state.services
    assert reopened.get("provider").status()["active_runs"] == []
    with pytest.raises(ApiError) as failure:
        await reopened.get("saved_generation").publish_fictional_artifact(value,
            expected_policy_revision=1,expected_context_epoch=0)
    assert failure.value.code == "fictional_artifact_untrusted"
    assert reopened.db.fetch_all("SELECT * FROM assessment_tests") == []


@pytest.mark.parametrize("fragment", ["person@example.test", "2034-08-19", "CASE_SENTINEL_928374", "Jane Synthetic"])
def test_deterministic_overlap_refusal_handles_identifiers_before_model_attestation(fragment):
    assert privacy_overlap("name: "+fragment,"Unchanged "+fragment)
