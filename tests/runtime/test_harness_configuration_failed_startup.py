# SPDX-License-Identifier: MIT
"""Real H04 candidate rejection preserves the live owner and survives reopen.

Only expected registry metadata is adversarial. Inspection, candidate exit,
root sealing, authority, original managed lifespan and native runtime are real.
Catalogue IO is synthetic; no inference or model registry is installed.
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


def run_owned_child(phase, root):
    from test_harness_profile_owner import ObservedChild

    environment = {key: value for key, value in os.environ.items() if key.upper() in {
        "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "COMSPEC",
        "SYSTEMDRIVE", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "PROGRAMDATA",
        "RENULUS_LIBRARY_HELPERS", "RENULUS_HARNESS_NODE", "HF_HOME", "HF_HUB_CACHE"}}
    environment.update(PYTHONPATH=str(SOURCE / "runtime"), PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
        OPENCODE_DISABLE_UPDATE_CHECK="true")
    process = subprocess.Popen([sys.executable, "-B", "-u", str(Path(__file__).resolve()),
        phase, str(root)], cwd=SOURCE, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True,
        creationflags=subprocess.CREATE_NO_WINDOW)
    messages, errors = queue.Queue(), []

    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    def read_errors():
        for line in process.stderr:
            errors.append(line)

    reader = threading.Thread(target=read, daemon=True)
    error_reader = threading.Thread(target=read_errors, daemon=True)
    reader.start()
    error_reader.start()
    actual = None
    try:
        line = messages.get(timeout=15)
        assert line, "Owned child ended before identity: " + "".join(errors)
        identity = json.loads(line)
        assert set(identity) == {"actual_pid"}
        assert type(identity["actual_pid"]) is int and identity["actual_pid"] > 0
        assert identity["actual_pid"] != os.getpid()
        actual = ObservedChild(identity["actual_pid"])
        line = messages.get(timeout=120)
        assert line, "Owned child ended before result: " + "".join(errors)
        result = json.loads(line)
        assert "failure" not in result, result
        assert actual.wait(10000) == 0, "Owned issuer did not settle"
        process.wait(timeout=10)
        assert process.returncode == 0, "".join(errors)
        reader.join(timeout=10)
        error_reader.join(timeout=10)
        assert not reader.is_alive() and not error_reader.is_alive()
        assert messages.get(timeout=1) is None, "Owned stdout must reach EOF"
        return {**result, "issuer_exit_observed": True, "owned_pipe_eof_observed": True}
    finally:
        try:
            if actual is not None and actual.wait(0) == 258:
                actual.terminate()  # Failure cleanup of this independently retained issuer only.
                assert actual.wait(10000) == 0
            elif actual is None and process.poll() is None:
                process.terminate()  # Only our Popen child, before its identity reply.
            process.wait(timeout=10)
        finally:
            reader.join(timeout=10)
            error_reader.join(timeout=10)
            process.stdout.close()
            process.stderr.close()
            if actual is not None:
                actual.close()


def test_failed_actual_candidate_preserves_live_configuration_and_reopens(tmp_path):
    root = tmp_path / "profile"
    failed = run_owned_child("fail", root)
    reopened = run_owned_child("reopen", root)
    healthy = failed["healthy"]
    candidate = failed["inspection"]
    assert failed["error"] == {"code": "registry_mismatch", "status": 409, "retryable": True}
    assert failed["effective"] == healthy["effective"]
    assert failed["requested"] == failed["failed"] != healthy["effective"]
    assert failed["failure_code"] == "registry_mismatch"
    assert failed["admission_open"] is True and failed["activating"] is None
    assert failed["native"] == healthy["native"]
    assert failed["native_configuration"] == healthy["effective"]
    assert failed["registry_hash"] == candidate["health"]["registry_hash"] == healthy["registry_hash"]
    assert candidate["health"]["configuration_version"] == failed["failed"]
    assert candidate["health"]["grant_epoch"] == 1
    assert candidate["health"]["registry_hash"] != failed["expected_registry_hash"]
    assert candidate["health"]["healthy"] is True
    assert all(candidate["health"][key] is False for key in ("generation_open", "recovery_open",
        "package_acquisition_open", "mcp_startup_open", "live_store_writer"))
    assert candidate["exit_observed"] is True and candidate["settlement"] == "settled"
    assert candidate["domain_active"] == 0
    assert candidate["native"]["generation"] != healthy["native"]["generation"]
    assert failed["inspection_calls"] == 1 and failed["root_gate_reacquired"] is True
    assert failed["live_owner_retained"] is True
    assert failed["launch_hash"] == failed["candidate_launch_hash"] == healthy["launch_hash"]
    for key in ("effective", "requested", "failed", "failure_code", "grant_epoch",
                "revoked", "registry_hash", "launch_hash"):
        assert reopened[key] == failed[key]
    assert reopened["before"]["effective"] == failed["effective"]
    assert reopened["before"]["requested"] == reopened["before"]["failed"] == failed["failed"]
    assert reopened["before"]["failure_code"] == "registry_mismatch"
    assert reopened["admission_open"] is True and reopened["activating"] is None
    assert reopened["native"]["generation"] != failed["native"]["generation"]
    assert reopened["issuer_generation"] != failed["issuer_generation"]
    assert reopened["predecessor_kind"] == "settled_predecessor"
    assert reopened["predecessor_generation"] == failed["issuer_generation"]
    assert len(reopened["predecessor_receipt"]) == 64
    assert failed["catalogue_requests"] == 1 and reopened["catalogue_requests"] == 0
    for observation in (failed, reopened):
        assert observation["grant_epoch"] == 1 and observation["revoked"] == ["tools"]
        assert observation["pinned_count"] == observation["domain_active"] == 0
        assert observation["active_sessions"] == observation["provider_completions"] == []
        assert observation["model_registry_installed"] is False
        assert observation["ordinary_callback_count"] == 1
        assert observation["native_exit_observed"] is True
        assert observation["services_shutdown"] == observation["native_settlement"] == "settled"
        assert observation["issuer_exit_observed"] is observation["owned_pipe_eof_observed"] is True
    (tmp_path / "observations.json").write_text(json.dumps({"failed": failed,
        "reopened": reopened}, indent=2), encoding="utf-8")


def public_state(authority):
    snapshot = authority.activation_snapshot()
    return {**{key: snapshot[key] for key in ("effective", "requested", "activating", "failed",
        "failure_code", "admission_open", "grant_epoch", "revoked")},
        "pinned_count": len(snapshot["pinned_runs"])}


async def child_main(phase, root):
    import httpx
    from renulus.contracts import ApiError
    from renulus.runtime.harness_configuration import (AttemptPolicy, Candidate, CandidateHealth,
        ChildPolicy, ContextPolicy, RolePolicy)
    from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
    from renulus.runtime.harness_process import ManagedHarnessProcess
    from renulus.runtime.harness_profile_owner import ProfileOwnerScope
    from renulus.runtime.harness_startup import HarnessStartupOptions, create_managed_app
    from test_harness_learning_models import command, process_config
    from test_harness_managed_startup import SYNTHETIC_ACCOUNT_KEY
    from test_harness_profile_owner import ObservedChild

    assert phase in {"fail", "reopen"}
    loop = asyncio.get_running_loop()
    catalogue_requests, ordinary, before, stores = [], [], {}, []
    boot = {"ipc": {"max_inflight": 1, "max_domain_inflight": 1, "max_frame_bytes": 65536}}
    config = replace(process_config(root, "synthetic-failed-startup"), boot_settings={})
    scope = ProfileOwnerScope(root, config.profile_id, config.domain_store_id, config.store_id)
    candidates = root.parent / "candidates"
    options = HarnessStartupOptions(scope, config, root.parent / "artifacts", candidates,
        30, initialize_new=phase == "fail")

    def catalogue(request):
        assert request.method == "GET" and request.url.path.endswith("/models")
        catalogue_requests.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    async def prepare(app, lease, authority, store):
        assert asyncio.get_running_loop() is loop
        lease.require_predecessor(lease.predecessor)
        provider = app.state.services.get("provider")
        assert provider.paths is app.state.services.paths and authority.db is app.state.services.db
        stores.append(store)
        before.update(public_state(authority))
        if phase == "reopen":
            assert provider.configuration_connection() is not None
            assert before["effective"] != before["requested"] == before["failed"]
            assert before["failure_code"] == "registry_mismatch" and before["activating"] is None
            return None
        assert before["effective"] is None and before["requested"] is None
        await provider.connect_go(SYNTHETIC_ACCOUNT_KEY, select=True)
        provider.select("opencode-go", "mimo-v2.6-pro")
        route = await provider.prepare_harness_route()
        connection = provider.configuration_connection()
        assert (route.credential_ref, route.credential_epoch) == (
            connection.credential_reference, connection.credential_revision)
        inspector = ManagedHarnessProcess()
        try:
            await inspector.start(replace(config, profile_root=candidates / "initial-hash", boot_settings=boot))
            native = inspector.native_identity()
            lease.register_native(native.pid, generation=native.generation)
            inspection = await command(inspector, "host.inspect")
            assert inspection["state"] == "policy_blocked"
            assert all(inspection[key] is False for key in ("generation_open", "recovery_open",
                "package_acquisition_open", "mcp_startup_open", "live_store_writer"))
        finally:
            assert (await inspector.close(10))["state"] == "closed"
            assert (await inspector.settlement(10))["state"] == "settled"
            assert inspector.domain_status()["active"] == 0
        inputs = FrozenLaunchInputs(boot_settings=boot, connection=connection,
            roles=(RolePolicy(purpose="explain", model_id="mimo-v2.6-pro", output_tokens=32, dispatch_limit=1),),
            inputs=(), capabilities=("text", "tools"), context=ContextPolicy(requested_window_tokens=640,
                reserve_tokens=8), attempts=AttemptPolicy(foreground_dispatches=1, standalone_dispatches=0,
                title_dispatches=0, retries=0), children=ChildPolicy(max_depth=0, concurrency=0))
        assert store.save(inputs) == inputs.launch_hash
        return finish_spec(inputs, inspection["registry_hash"])

    app = create_managed_app(options, source_root=SOURCE, prepare_startup=prepare,
        provider_http_transport=httpx.MockTransport(catalogue))
    services, authority = app.state.services, app.state.harness_configuration_authority
    provider = services.get("provider")
    lease = app.state.harness_bootstrap.profile_owner
    handles, registered_candidates, inspections = [], [], []

    async def observe():
        owner = services.get("harness_learning")
        snapshot = public_state(authority)
        spec = authority.configuration(snapshot["effective"])
        assert owner.configuration_authority is authority and owner.configuration_id == snapshot["effective"]
        assert services.get("provider") is provider and provider.configuration_connection() == spec.connection
        identity = owner.process.native_identity()
        registered = lease.register_native(identity.pid, generation=identity.generation)
        status = await command(owner.process, "host.status")
        assert status["state"] == "ready" and status["configurationId"] == snapshot["effective"]
        launch = [item.sha256 for item in spec.inputs if item.kind == "artifact" and item.name == "launch"]
        assert len(launch) == 1
        return {**snapshot, "issuer_generation": lease.generation,
            "native": {**asdict(identity), "creation_filetime": registered.creation_filetime},
            "native_configuration": status["configurationId"], "registry_hash": spec.registry_hash,
            "launch_hash": launch[0], "catalogue_requests": len(catalogue_requests),
            "ordinary_callback_count": len(ordinary), "active_sessions": status["activeSessionIds"],
            "domain_active": owner.process.domain_status()["active"],
            "provider_completions": provider.status()["completed_requests"],
            "model_registry_installed": owner.model_registry is not None}

    async def first_ordinary_callback():
        assert asyncio.get_running_loop() is loop
        assert app.state.harness_bootstrap_result.admission_open is True
        assert authority.status()["admission_open"] is True
        ordinary.append(True)

    services.on_startup.insert(0, first_ordinary_callback)
    try:
        async with app.router.lifespan_context(app):
            owner = services.get("harness_learning")
            live = owner.process
            healthy = await observe()
            native_handle = ObservedChild(healthy["native"]["pid"],
                creation=healthy["native"]["creation_filetime"])
            handles.append(native_handle)
            assert native_handle.wait(0) == 258
            if phase == "fail":
                assert authority.revoke("tools") == 1
                spec = authority.configuration(healthy["effective"])
                old = stores[0].load(healthy["launch_hash"])
                frozen = FrozenLaunchInputs(boot_settings=old.boot_settings, connection=spec.connection,
                    roles=spec.roles, inputs=tuple(item for item in spec.inputs
                        if not (item.kind == "artifact" and item.name == "launch")),
                    capabilities=spec.capabilities, context=spec.context, attempts=spec.attempts, children=spec.children)
                assert stores[0].save(frozen) == old.launch_hash
                expected_hash = "0" * 64 if spec.registry_hash != "0" * 64 else "f" * 64
                adversarial = finish_spec(frozen, expected_hash)
                assert adversarial.model_copy(update={"registry_hash": spec.registry_hash}) == spec
                version = authority.stage(adversarial)
                controller = services.get("harness_configuration_controller")
                lifecycle = services.get("harness_configuration_lifecycle")
                assert controller.authority is authority and controller.provider is provider
                assert controller.lifecycle is lifecycle
                real_register, real_inspect = owner.register_process, lifecycle.inspect_candidate

                def observe_registration(process, native_config):
                    returned = real_register(process, native_config)
                    identity = process.native_identity()
                    reference = lease.register_native(identity.pid, generation=identity.generation)
                    handle = ObservedChild(identity.pid, creation=reference.creation_filetime)
                    handles.append(handle)
                    assert native_config.profile_root.is_relative_to(candidates)
                    assert handle.wait(0) == 258
                    registered_candidates.append((process, identity, reference, handle))
                    return returned

                async def observe_inspection(candidate: Candidate) -> CandidateHealth:
                    assert candidate.version == version and candidate.spec == adversarial
                    health = await real_inspect(candidate)
                    assert len(registered_candidates) == 1
                    process, identity, reference, handle = registered_candidates[0]
                    settlement = await process.settlement(0)
                    assert settlement["state"] == "settled" and handle.wait(0) == 0
                    assert process.domain_status()["active"] == 0
                    assert isinstance(health, CandidateHealth) and health.registry_hash == spec.registry_hash
                    assert owner.process is live and live.native_identity() == identity_before
                    inspections.append({"health": health.model_dump(mode="json"),
                        "native": {**asdict(identity), "creation_filetime": reference.creation_filetime},
                        "exit_observed": True, "settlement": settlement["state"],
                        "domain_active": process.domain_status()["active"]})
                    return health  # The original result is passed through unchanged.

                identity_before = live.native_identity()
                owner.register_process = observe_registration
                lifecycle.inspect_candidate = observe_inspection
                try:
                    with pytest.raises(ApiError) as denied:
                        await controller.activate(version)
                finally:
                    owner.register_process = real_register
                    lifecycle.inspect_candidate = real_inspect
                assert (denied.value.code, denied.value.status, denied.value.retryable) == (
                    "registry_mismatch", 409, True)
                assert native_handle.wait(0) == 258 and owner.process is live
                assert live.native_identity() == identity_before
                seal = owner.seal_new_runs(expected_effective=healthy["effective"])
                seal.release()  # Successful reacquisition proves the failed change released ingress.
                result = {**await observe(), "healthy": healthy, "inspection": inspections[0],
                    "inspection_calls": len(inspections), "expected_registry_hash": expected_hash,
                    "candidate_launch_hash": frozen.sha256, "root_gate_reacquired": True,
                    "live_owner_retained": owner.process is live, "error": {"code": denied.value.code,
                        "status": denied.value.status, "retryable": denied.value.retryable}}
            else:
                lease.require_predecessor(lease.predecessor)
                result = {**healthy, "before": before, "predecessor_kind": lease.predecessor.kind,
                    "predecessor_generation": lease.predecessor.previous_generation,
                    "predecessor_receipt": lease.predecessor.receipt_sha256}
        assert native_handle.wait(0) == 0
        result.update(services_shutdown=services.shutdown_status()["state"],
            native_settlement=(await live.settlement(0))["state"],
            domain_active=live.domain_status()["active"], native_exit_observed=True)
        return result
    finally:
        for handle in handles:
            handle.close()


if __name__ == "__main__":
    print(json.dumps({"actual_pid": os.getpid()}), flush=True)
    try:
        print(json.dumps(asyncio.run(child_main(sys.argv[1], Path(sys.argv[2])))), flush=True)
    except BaseException as error:
        print(json.dumps({"failure": type(error).__name__, "code": getattr(error, "code", None)}), flush=True)
        raise
