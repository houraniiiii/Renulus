"""HTTP Settings activation over production main, with zero inference.

Account/catalogue evidence is synthetic. Initial authority bootstrap uses the
existing real metadata-only inspector and a never-started owner; it does not
prove normal profile startup. Saved runs are admitted before native scheduling,
then cancelled through their public producer. No model registry is installed.
"""
from contextlib import asynccontextmanager
import asyncio
import json

import httpx
import pytest

from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_configuration import (
    AttemptPolicy, CandidateHealth, ChildPolicy, ConfigurationAuthority,
    ConnectionReference, ContextPolicy, RestartBoundary, RolePolicy,
)
from renulus.runtime.harness_configuration_lifecycle import install_harness_configuration
from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.manager import ProviderManager
from renulus.server import create_app

from test_harness_learning_models import SOURCE, command, inspect_candidate, process_config
from test_harness_model_dispatch_sdk import NODE, offline


SETTINGS = "/api/v1/runtime/harness/configuration"
INITIAL_ROLES = [{"purpose": "explain", "enabled": True,
    "model_id": "mimo-v2.6-pro", "output_tokens": 32, "dispatch_limit": 3}]
REQUESTED_ROLES = [
    {"purpose": "explain", "enabled": True, "model_id": "deepseek-v4.1-flash",
        "output_tokens": 64, "dispatch_limit": 3},
    {"purpose": "case-discuss", "enabled": True, "model_id": "mimo-v2.6-pro",
        "output_tokens": 48, "dispatch_limit": 2},
]


@asynccontextmanager
async def settings_owner(tmp_path):
    assert NODE.is_file(), "Use the pinned Node artifact; no install or substitute."
    app = create_app(tmp_path / "profile", source_root=SOURCE)
    services = app.state.services
    authority = ConfigurationAuthority(services.db)
    catalogue_requests = []

    def catalogue(request):
        assert request.method == "GET" and request.url.path.endswith("/models")
        catalogue_requests.append(request.url.path)
        return httpx.Response(200, json={"data": [
            {"id": "mimo-v2.6-pro"}, {"id": "deepseek-v4.1-flash"}]})

    provider = ProviderManager(services.paths, http_transport=httpx.MockTransport(catalogue))
    services.registry["provider"] = provider
    owner = None
    try:
        await provider.connect_go("synthetic_settings_metadata_only_7391", select=True)
        provider.select("opencode-go", "mimo-v2.6-pro")
        route = await provider.prepare_harness_route()
        inspection = await inspect_candidate(tmp_path / "initial-inspection")
        config = process_config(services.paths.root, "synthetic-settings-activation")
        candidates = tmp_path / "configuration-candidates"
        store = LaunchArtifactStore(tmp_path / "launch-artifacts",
            live_root=services.paths.root, candidate_root=candidates)
        frozen = FrozenLaunchInputs(boot_settings=config.boot_settings,
            connection=ConnectionReference(provider=route.provider_id,
                credential_reference=route.credential_ref, credential_revision=route.credential_epoch,
                selected_model=route.catalog_model_id),
            roles=tuple(RolePolicy(**role) for role in INITIAL_ROLES), inputs=(),
            capabilities=("text", "tools"),
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=3, retries=0), children=ChildPolicy())
        store.save(frozen)
        spec = finish_spec(frozen, inspection["registry_hash"])
        version = authority.stage(spec)
        fields = ("registry_hash", "generation_open", "recovery_open",
            "package_acquisition_open", "mcp_startup_open", "live_store_writer")
        assert authority.validate(version, lambda candidate: CandidateHealth(
            configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
            **{key: inspection[key] for key in fields}))
        owner = HarnessLearningOwner(services, config, configuration_id=version,
            configuration_authority=authority)
        # The helper closed and settled its real candidate. This live owner has
        # never started: there is no prior generation or callback to hand off.
        assert (await owner.process.settlement(0))["state"] == "settled"
        assert owner.process.domain_status()["active"] == 0
        authority.activate(version, RestartBoundary(admission_closed=True,
            runtime_stopped=True, domain_settled=True), expected_effective=None)
        authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
        owner.install()
        await owner.start()
        install_harness_configuration(owner, authority=authority, provider=provider,
            candidate_root=candidates, launch_store=store, attempt_timeout=15)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://testserver", timeout=60) as client:
            yield client, owner, authority, store, version, catalogue_requests
    finally:
        assert (await services.shutdown(timeout=30))["state"] == "settled"
        if owner is not None:
            assert (await owner.process.settlement(0))["state"] == "settled"
            assert owner.process.domain_status()["active"] == 0
        await provider.close()
        services.get("helpers").startup.close()


async def cancel_without_native_dispatch(repo, owner, chat, entry, receipt):
    identifier, run_id = chat["identity"]["id"], receipt["run_id"]
    await repo.streaming.cancel("learning", identifier, run_id)
    async with asyncio.timeout(10):
        events = [json.loads(encoded.split("data: ", 1)[1])
            async for encoded in repo.streaming.events(entry, receipt)]
    assert [event["type"] for event in events] == ["cancelled"]
    assert repo.streaming.status("learning", identifier, run_id)["state"] == "cancelled"
    assert (await owner.settle_run(entry, timeout=5))["state"] == "settled"
    assert (await command(owner.process, "session.find", operation=run_id))["sessions"] == []


@pytest.mark.parametrize("held_saved_run", [False, True], ids=["idle", "saved-cancel-retry"])
async def test_settings_stage_busy_refusal_and_activation_replace_the_real_generation(
        tmp_path, offline, held_saved_run):
    async with settings_owner(tmp_path) as (client, owner, authority, store, initial, catalogue_requests):
        response = await client.get(SETTINGS)
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        before = response.json()
        assert before["requested"] == before["effective"] == initial
        assert before["failed"] is before["failure_code"] is None
        assert before["admission_open"] is True
        assert before["configuration"]["roles"] == INITIAL_ROLES
        assert set(before["catalogue"]) == {"mimo-v2.6-pro", "deepseek-v4.1-flash"}
        old_process = owner.process
        native_before = await command(old_process, "host.status")
        assert native_before["state"] == "ready" and native_before["configurationId"] == initial
        repo = owner.services.get("conversations")
        if held_saved_run:
            chat = repo.create(NewConversation())
            request = Send(expected_revision=chat["revision"],
                text="Compare synthetic proteinuria mechanisms for nephrology education.",
                request_id="synthetic-settings-held-saved-run")
            entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
            run_id = receipt["run_id"]
            pinned = authority.run(run_id)
            preserved = repo.get("learning", chat["identity"]["id"])

        staged = await client.post(SETTINGS, json={"roles": REQUESTED_ROLES})
        assert staged.status_code == 200, staged.text
        requested = staged.json()["version"]
        assert requested != initial
        assert staged.json()["requested"] == requested
        assert staged.json()["effective"] == initial
        pending = (await client.get(SETTINGS)).json()
        assert pending["configuration"]["roles"] == INITIAL_ROLES
        assert pending["requested_configuration"]["roles"] == REQUESTED_ROLES
        if held_saved_run:
            assert pending["pinned_runs"] == [{"run_id": run_id, "purpose": "explain", "version": initial}]
        else:
            assert pending["pinned_runs"] == []
        requested_spec = authority.configuration(requested)
        launch = next(item for item in requested_spec.inputs if item.name == "launch")
        assert finish_spec(store.load(launch.sha256), requested_spec.registry_hash) == requested_spec
        assert launch.sha256 != next(item.sha256 for item in authority.configuration(initial).inputs
            if item.name == "launch")

        if held_saved_run:
            refused = await client.post(SETTINGS + "/activate", json={"version": requested})
            assert refused.status_code == 409, refused.text
            assert refused.json()["error"]["code"] == "harness_configuration_busy"
            assert (await client.get(SETTINGS)).json() == pending
            assert owner.process is old_process
            assert await command(old_process, "host.status") == native_before
            assert authority.run(run_id) == pinned
            current = authority.require_current(run_id, required_capabilities=("text", "tools"))
            assert current["version"] == initial and current["route"]["model_id"] == "mimo-v2.6-pro"
            owner.bridge.check(run_id)  # Existing saved scope remains usable after refusal.
            assert repo.streaming.status("learning", chat["identity"]["id"], run_id)["state"] == "running"
            assert repo.get("learning", chat["identity"]["id"]) == preserved
            await cancel_without_native_dispatch(repo, owner, chat, entry, receipt)
            assert authority.run(run_id)["state"] == "settled"
            assert authority.run(run_id)["spent_dispatches"] == 0

        activated = await client.post(SETTINGS + "/activate", json={"version": requested})
        assert activated.status_code == 200, activated.text
        assert activated.headers["cache-control"] == "no-store"
        after = (await client.get(SETTINGS)).json()
        assert after == activated.json()
        assert after["requested"] == after["effective"] == requested
        assert after["admission_open"] is True and after["pinned_runs"] == []
        assert after["failed"] is after["failure_code"] is None
        assert after["configuration"]["roles"] == after["requested_configuration"]["roles"] == REQUESTED_ROLES
        assert owner.process is not old_process
        assert await old_process.settlement(0) == {"state": "settled", "exit_code": 0}
        assert (await old_process.close(0))["state"] == "closed"
        assert old_process.domain_status()["active"] == 0
        live = await command(owner.process, "host.status")
        assert live["state"] == "ready" and live["configurationId"] == requested
        assert live["activeSessionIds"] == live["heldSessionIds"] == []

        next_chat = repo.create(NewConversation())
        next_request = Send(expected_revision=next_chat["revision"],
            text="Compare synthetic kidney replacement modalities.",
            request_id="synthetic-settings-new-saved-run")
        next_entry, next_receipt = repo.streaming.begin("learning", next_chat["identity"]["id"], next_request)
        next_run = authority.run(next_receipt["run_id"])
        assert next_run["version"] == requested
        assert next_run["route"]["model_id"] == "deepseek-v4.1-flash"
        assert next_run["route"]["output_tokens"] == 64
        owner.bridge.check(next_receipt["run_id"])
        await cancel_without_native_dispatch(repo, owner, next_chat, next_entry, next_receipt)
        assert authority.run(next_receipt["run_id"])["spent_dispatches"] == 0
        assert (await client.get(SETTINGS)).json()["pinned_runs"] == []
        assert owner.process.domain_status()["active"] == 0
        assert len(catalogue_requests) == 1  # Stage/activate consume the cached catalogue only.
