# SPDX-License-Identifier: MIT
"""Actual managed startup/reopen in owned children; account metadata is synthetic.

Only catalogue HTTP is injected at original ProviderManager construction. Native
inspection, immutable launch, coordinator, app lifespan and settlement are real;
no prompt, deployment evidence, counter, engine instance or inference is supplied.
"""
import asyncio
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows native profile ownership")
SOURCE = Path(__file__).resolve().parents[2]
SYNTHETIC_ACCOUNT_KEY = "synthetic-managed-startup-never-networked"


def run_owned_child(phase, root):
    from test_harness_profile_owner import ObservedChild

    environment = {**os.environ, "PYTHONPATH": str(SOURCE / "runtime"),
        "PYTHONDONTWRITEBYTECODE": "1", "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "OPENCODE_DISABLE_UPDATE_CHECK": "true"}
    process = subprocess.Popen([sys.executable, "-B", "-u", str(Path(__file__).resolve()),
        phase, str(root)], cwd=SOURCE, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    messages = queue.Queue()

    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    actual = None
    try:
        identity = messages.get(timeout=15)
        assert identity, process.stderr.read()
        actual = ObservedChild(json.loads(identity)["actual_pid"])
        line = messages.get(timeout=120)
        assert line, process.stderr.read()
        result = json.loads(line)
        assert actual.wait(10000) == 0, "Owned managed child did not settle"
        process.wait(timeout=10)
        assert process.returncode == 0, (result, process.stderr.read())
        assert "failure" not in result, result
        return result
    finally:
        if actual is not None:
            if actual.wait(0) == 258:
                actual.terminate()  # Only the retained child created by this fixture.
                assert actual.wait(5000) == 0
            actual.close()
        elif process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        reader.join(timeout=2)
        process.stdout.close()
        process.stderr.close()


def test_managed_startup_initial_and_reopen_use_actual_profile_owner(tmp_path):
    root = tmp_path / "profile"
    initial = run_owned_child("initial", root)
    reopened = run_owned_child("reopen", root)
    assert initial["issuer_generation"] != reopened["issuer_generation"]
    assert initial["native_generation"] != reopened["native_generation"]
    assert initial["predecessor_generation"] is None
    assert reopened["predecessor_generation"] == initial["issuer_generation"]
    assert reopened["predecessor_receipt"] is not None
    for key in ("effective", "requested", "registry_hash", "launch_hash", "grant_epoch"):
        assert initial[key] == reopened[key]
    assert initial["catalogue_requests"] == 1 and reopened["catalogue_requests"] == 0
    assert initial["initial_inspection_settled"] is True
    for observation in (initial, reopened):
        assert observation["admission_open"] is True
        assert observation["ordinary_callback_count"] == 1
        assert observation["same_serving_loop"] is True
        assert observation["active_sessions"] == []
        assert observation["pinned_runs"] == []
        assert observation["provider_completions"] == []
        assert observation["services_shutdown"] == "settled"
        assert observation["native_settlement"] == "settled"
        assert observation["domain_active"] == 0
        assert observation["model_registry_installed"] is False


async def child_main(phase, root):
    # Deliberately import in the dedicated child. An absent parent entry is a
    # public-port red, not an incidental test-collection or native fixture error.
    from renulus.runtime.harness_startup import HarnessStartupOptions, create_managed_app
    import httpx

    from renulus.runtime.harness_configuration import (AttemptPolicy, ChildPolicy,
        ContextPolicy, RolePolicy)
    from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
    from renulus.runtime.harness_process import ManagedHarnessProcess
    from renulus.runtime.harness_profile_owner import ProfileOwnerScope
    from test_harness_learning_models import command, process_config

    assert phase in {"initial", "reopen"}
    serving_loop = asyncio.get_running_loop()
    catalogue_requests, ordinary = [], []
    initial_inspection_settled = False
    config = replace(process_config(root, "synthetic-managed-startup"), boot_settings={})
    scope = ProfileOwnerScope(root, config.profile_id, config.domain_store_id, config.store_id)
    candidate_root = root.parent / "candidates"
    options = HarnessStartupOptions(scope, config, root.parent / "artifacts",
        candidate_root, 30, initialize_new=phase == "initial")

    def catalogue(request):
        assert request.method == "GET" and request.url.path.endswith("/models")
        catalogue_requests.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    async def prepare(app, lease, authority, store):
        nonlocal initial_inspection_settled
        assert asyncio.get_running_loop() is serving_loop
        assert app.state.harness_bootstrap.profile_owner is lease
        assert app.state.harness_configuration_authority is authority
        assert authority.db is app.state.services.db
        assert lease.scope == scope and lease.python_identity.pid == os.getpid()
        lease.require_predecessor(lease.predecessor)
        provider = app.state.services.get("provider")
        assert provider.paths is app.state.services.paths
        if phase == "reopen":
            assert provider.configuration_connection() is not None
            assert authority.activation_snapshot()["effective"] is not None
            return None

        before = authority.activation_snapshot()
        assert before["effective"] is None and before["requested"] is None
        assert before["pinned_runs"] == [] and before["admission_open"] is False
        await provider.connect_go(SYNTHETIC_ACCOUNT_KEY, select=True)
        provider.select("opencode-go", "mimo-v2.6-pro")
        route = await provider.prepare_harness_route()
        connection = provider.configuration_connection()
        assert route.credential_ref == connection.credential_reference
        assert route.credential_epoch == connection.credential_revision

        # This independent native observation supplies the launch's actual hash.
        # It never validates/activates canonical policy or creates a session.
        inspector = ManagedHarnessProcess()
        try:
            await inspector.start(replace(config, profile_root=candidate_root / "initial-hash",
                boot_settings={"ipc": {"max_inflight": 1, "max_domain_inflight": 1,
                    "max_frame_bytes": 65536}}))
            identity = inspector.native_identity()
            observed = lease.register_native(identity.pid, generation=identity.generation)
            assert observed.pid == identity.pid and observed.creation_filetime > 0
            inspection = await command(inspector, "host.inspect")
            assert inspection["state"] == "policy_blocked"
            assert all(inspection[key] is False for key in ("generation_open", "recovery_open",
                "package_acquisition_open", "mcp_startup_open", "live_store_writer"))
        finally:
            assert (await inspector.close(10))["state"] == "closed"
            assert (await inspector.settlement(10))["state"] == "settled"
            assert inspector.domain_status()["active"] == 0
            initial_inspection_settled = True

        inputs = FrozenLaunchInputs(boot_settings={"ipc": {"max_inflight": 1,
                "max_domain_inflight": 1, "max_frame_bytes": 65536}},
            connection=connection, roles=(RolePolicy(purpose="explain", model_id="mimo-v2.6-pro",
                output_tokens=32, dispatch_limit=1),), inputs=(), capabilities=("text", "tools"),
            context=ContextPolicy(requested_window_tokens=640, reserve_tokens=8),
            attempts=AttemptPolicy(foreground_dispatches=1, standalone_dispatches=0,
                title_dispatches=0, retries=0), children=ChildPolicy(max_depth=0, concurrency=0))
        assert store.save(inputs) == inputs.launch_hash
        assert store.load(inputs.sha256) == inputs
        assert authority.activation_snapshot() == before
        return finish_spec(inputs, inspection["registry_hash"])

    app = create_managed_app(options, source_root=SOURCE, prepare_startup=prepare,
        provider_http_transport=httpx.MockTransport(catalogue))
    services = app.state.services
    authority = app.state.harness_configuration_authority

    async def after_managed_gate():
        assert asyncio.get_running_loop() is serving_loop
        result = app.state.harness_bootstrap_result
        snapshot = authority.activation_snapshot()
        assert result.admission_open is True and result.reason_code is None
        assert snapshot["admission_open"] is True and snapshot["effective"] == result.effective_version
        assert snapshot["activating"] is None and snapshot["pinned_runs"] == []
        assert app.state.harness_bootstrap_runtime is not None
        owner = services.get("harness_learning")
        assert owner.configuration_authority is authority
        assert owner.configuration_id == result.effective_version
        assert owner.model_registry is None
        status = await command(owner.process, "host.status")
        identity = owner.process.native_identity()
        assert status["state"] == "ready" and status["configurationId"] == result.effective_version
        assert status["activeSessionIds"] == []
        assert owner.process.domain_status()["active"] == 0
        ordinary.append({"generation": identity.generation, "status": status})

    # Run before every original ordinary producer. Bootstrap must have finished
    # on this loop before the original lifespan invokes even this first callback.
    services.on_startup.insert(0, after_managed_gate)
    async with app.router.lifespan_context(app):
        assert len(ordinary) == 1
        owner = services.get("harness_learning")
        assert owner.process.native_identity().generation == ordinary[0]["generation"]
        snapshot = authority.activation_snapshot()
        spec = authority.configuration(snapshot["effective"])
        launch = [item.sha256 for item in spec.inputs if item.kind == "artifact" and item.name == "launch"]
        assert len(launch) == 1
        lease = app.state.harness_bootstrap.profile_owner
        assert lease.python_identity.pid == os.getpid()
        assert lease.python_identity.creation_filetime > 0
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="http://testserver") as client:
            visible = await client.get("/api/v1/connections")
            assert visible.status_code == 200, (visible.status_code,
                visible.json().get("error", {}).get("code"))
            assert visible.json()["selected_provider"] == "opencode-go"
        result = {"issuer_generation": lease.generation,
            "python_identity": asdict(lease.python_identity),
            "predecessor_generation": lease.predecessor.previous_generation,
            "predecessor_receipt": lease.predecessor.receipt_sha256,
            "native_generation": ordinary[0]["generation"],
            "effective": snapshot["effective"], "requested": snapshot["requested"],
            "grant_epoch": snapshot["grant_epoch"], "registry_hash": spec.registry_hash,
            "launch_hash": launch[0], "admission_open": snapshot["admission_open"],
            "pinned_runs": snapshot["pinned_runs"], "catalogue_requests": len(catalogue_requests),
            "initial_inspection_settled": initial_inspection_settled,
            "ordinary_callback_count": len(ordinary), "same_serving_loop": True,
            "active_sessions": ordinary[0]["status"]["activeSessionIds"],
            "provider_completions": services.get("provider").status()["completed_requests"],
            "model_registry_installed": owner.model_registry is not None}
    result.update(services_shutdown=services.shutdown_status()["state"],
        native_settlement=(await owner.process.settlement(0))["state"],
        domain_active=owner.process.domain_status()["active"])
    return result


if __name__ == "__main__":
    print(json.dumps({"actual_pid": os.getpid()}), flush=True)
    print(json.dumps(asyncio.run(child_main(sys.argv[1], Path(sys.argv[2])))), flush=True)
