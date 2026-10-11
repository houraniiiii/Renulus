# SPDX-License-Identifier: MIT
"""Actual Windows issuer and public bootstrap runtime; synthetic profiles only."""
import asyncio
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest

from test_harness_profile_owner import ObservedChild


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows profile ownership")
REPO = Path(__file__).resolve().parents[2]
NODE = Path("C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe")


def run_owned(case, root):
    home = root.parent / "synthetic-home"
    home.mkdir(parents=True, exist_ok=True)
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update(PATH=str(NODE.parent), PYTHONPATH=str(REPO / "runtime"),
                       HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        environment[key] = str(home)
    process = subprocess.Popen([sys.executable, "-B", "-u", str(Path(__file__).resolve()),
        case, str(root)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
    messages = queue.Queue()

    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    actual = None
    try:
        first = messages.get(timeout=15)
        assert first, "The dedicated synthetic Python child did not announce itself"
        actual = ObservedChild(json.loads(first)["actual_pid"])
        line = messages.get(timeout=100)
        assert line, "The dedicated synthetic runtime child returned no result"
        result = json.loads(line)
        assert actual.wait(10000) == 0, "The synthetic runtime child did not settle"
        process.wait(timeout=10)
        assert process.returncode == 0, result
        return result
    finally:
        if actual:
            if actual.wait(0) == 258:
                actual.terminate()
                assert actual.wait(5000) == 0
            actual.close()
        elif process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        reader.join(timeout=2)
        process.stdout.close()
        process.stderr.close()


def test_copied_issuer_refuses_runtime_before_installation_or_native_start(tmp_path):
    result = run_owned("copied-issuer", tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_conflict", "installed": False,
                      "candidate_created": False, "shutdown_changed": False}


@pytest.mark.parametrize("field", ["root", "profile", "runtime-store", "domain-store",
                                   "domain-path", "authority", "provider"])
def test_foreign_runtime_identity_refuses_before_installation(tmp_path, field):
    result = run_owned("foreign-" + field, tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_conflict", "installed": False,
                      "candidate_created": False, "shutdown_changed": False}


@pytest.mark.parametrize("field", ["attempt-zero", "attempt-boolean", "attempt-infinite",
                                   "control-zero", "start-infinite"])
def test_invalid_explicit_observation_or_process_bounds_refuse_before_installation(tmp_path, field):
    result = run_owned("bounds-" + field, tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_bounds_invalid", "installed": False,
                      "candidate_created": False, "shutdown_changed": False}


@pytest.mark.parametrize("field", ["missing", "tampered", "missing-reference", "policy-mismatch",
                                   "snapshot-mismatch"])
def test_unavailable_or_mismatching_launch_refuses_before_installation(tmp_path, field):
    result = run_owned("launch-" + field, tmp_path / "profile")
    assert result == {"code": "harness_launch_invalid", "installed": False,
                      "candidate_created": False, "shutdown_changed": False}


def test_actual_sdk_inspection_and_live_start_share_one_installed_owner_and_drain(tmp_path):
    result = run_owned("sdk", tmp_path / "profile")
    assert result.get("closed_candidate") is True, result
    assert result["native_registry_matches"] is True
    assert result["not_started_before_live"] is True
    assert result["canonical_closed_after_live"] is True
    assert result["same_generation"] is True
    assert result["settings_roles"] == [{"purpose": "explain", "enabled": True, "model_id": None,
        "output_tokens": 64, "dispatch_limit": 1}]
    assert result["exact_boot"] == {"config": {"instructions": ["Synthetic CKD learning"]}}
    assert result["model_denied"] is True
    assert result["registered_native_count"] == 3
    assert result["drain"] == "settled" and result["native_settlement"] == "settled"
    assert result["lease_current_after_close"] is True


def test_rejected_registry_factory_product_is_retained_and_drained(tmp_path):
    result = run_owned("partial-registry", tmp_path / "profile")
    assert result == {"code": "harness_owner_conflict", "installed": False,
        "candidate_created": False, "registry_settlement": "settled", "drain": "settled"}


@pytest.mark.parametrize("field,code", [("unpersisted", "configuration_missing"),
    ("policy", "candidate_authority_stale"), ("epoch", "candidate_authority_stale"),
    ("generation-open", "candidate_authority_stale")])
def test_untrusted_candidate_refuses_before_factory_installation_or_native_start(tmp_path, field, code):
    result = run_owned("candidate-" + field, tmp_path / "profile")
    assert result == {"code": code, "installed": False, "factory_calls": 0,
        "candidate_created": False, "requested_unchanged": True, "drain": "settled"}


def test_unexpected_factory_error_is_safe_and_partial_installation_drains(tmp_path):
    result = run_owned("factory-error", tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_runtime_failed", "status": 503,
        "retryable": True, "safe_diagnostic": True, "installed": False,
        "factory_calls": 1, "candidate_created": False, "drain": "settled"}


def test_close_observer_cancellation_keeps_one_shared_drain_and_issuer_owned(tmp_path):
    result = run_owned("held-close", tmp_path / "profile")
    assert result == {"held_state": "draining", "observers_retained": True,
        "producer_calls": 1, "dependency_after_finalizer": True,
        "drain": "settled", "lease_current_after_close": True}


def context(root):
    from renulus.runtime.harness_configuration import (
        AttemptPolicy, ChildPolicy, ConfigurationAuthority, ConnectionReference, ContextPolicy, RolePolicy,
    )
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec
    from renulus.runtime.harness_process import HarnessProcessConfig
    from renulus.runtime.harness_profile_owner import ProfileOwnerScope, acquire_profile_owner
    from renulus.server import create_app

    scope = ProfileOwnerScope(root, "synthetic-runtime-profile", "synthetic-domain", "synthetic-runtime")
    lease = acquire_profile_owner(scope, initialize_new=True)
    services = create_app(root, source_root=REPO).state.services
    authority = ConfigurationAuthority(services.db)
    store = LaunchArtifactStore(root.parent / "artifacts", live_root=root,
                               candidate_root=root.parent / "candidates")
    frozen = FrozenLaunchInputs(boot_settings={"config": {"instructions": ["Synthetic CKD learning"]}},
        connection=ConnectionReference(provider="opencode-go", credential_reference="synthetic-reference",
            credential_revision=0, selected_model="mimo-v2.6-pro"),
        roles=(RolePolicy(purpose="explain", output_tokens=64, dispatch_limit=1),), inputs=(),
        capabilities=("text", "tools"), context=ContextPolicy(requested_window_tokens=8192),
        attempts=AttemptPolicy(foreground_dispatches=1, retries=0), children=ChildPolicy())
    store.save(frozen)
    config = HarnessProcessConfig(node_executable=NODE, host_entry=REPO / "packages/harness/src/main.mjs",
        profile_root=root, profile_id=scope.profile_id, store_id=scope.runtime_store_id,
        domain_store_id=scope.domain_store_id, domain_path="state/renulus.sqlite3",
        max_inflight=2, max_control_inflight=2, max_domain_inflight=2,
        max_domain_result_records=16, max_domain_result_bytes=1048576, max_frame_bytes=65536,
        max_result_records=16, max_result_bytes=1048576, start_timeout=30,
        boot_settings={"caller_payload": ["Must not become native boot"]})
    return services, authority, store, frozen, finish_spec(frozen, "a" * 64), lease, config


async def registry_evidence(root, lease, config):
    from renulus.runtime.harness_process import ManagedHarnessProcess
    process = ManagedHarnessProcess()
    evidence_config = replace(config, profile_root=root, profile_id="synthetic-registry-evidence",
        store_id="evidence-runtime", domain_store_id="evidence-domain", boot_settings={})
    try:
        await process.start(evidence_config)
        identity = process.native_identity()
        lease.register_native(identity.pid, generation=identity.generation)
        response = await process.request("host.inspect", {}, "registry-evidence", "1", 10)
        while response["outcome"] == "accepted_pending":
            await asyncio.sleep(.02)
            response = await process.query_result(response["request_id"])
        assert response["outcome"] == "committed_reference", response.get("error")
        await process.release_observation(response["request_id"])
        return response["result"]
    finally:
        while (await process.close(1))["state"] != "closed":
            assert (await process.settlement(1))["state"] in {"pending", "settled"}


async def sdk_case(root, services, authority, store, frozen, lease, config):
    from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime
    from renulus.runtime.harness_configuration import Candidate, RestartBoundary
    from renulus.runtime.harness_domain import DomainBinding, DomainRequest
    from renulus.runtime.harness_launch import finish_spec
    observed = await registry_evidence(root.parent / "registry-evidence", lease, config)
    spec = finish_spec(frozen, observed["registry_hash"])
    runtime = ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
        config=config, launch_store=store, candidate_root=root.parent / "candidates", attempt_timeout=10)
    try:
        # Caller aliases cannot alter the sole immutable launch used by native IO.
        config.boot_settings["caller_payload"].append("changed after construction")
        version = authority.stage(spec)
        candidate = Candidate(version, spec, authority.revocation_overlay()["epoch"])
        inspected = await runtime.inspect_candidate(candidate)
        owner = services.get("harness_learning")
        controller = services.get("harness_configuration_controller")
        before = await owner.process.request("host.status", {}, "before-live", "1", 0)
        assert authority.validate(version, lambda actual: inspected if actual == candidate else None)
        authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
            domain_settled=True), expected_effective=None)
        live = await runtime.start_live(candidate)
        identity = owner.process.native_identity()
        again = await runtime.start_live(candidate)
        await owner.start()
        reused = owner.process.native_identity()
        snapshot = await controller.snapshot()
        unknown = DomainBinding("unadmitted-model", "1", "synthetic-session", "synthetic-input", "unadmitted-model")
        denied = await owner.authorize(DomainRequest("synthetic-callback", unknown, "model.prepare", {}))
        registered = json.loads((root / ".renulus-profile-owner.json").read_text())["native_count"]
        result = {"closed_candidate": inspected.healthy and not any((inspected.generation_open,
                inspected.recovery_open, inspected.package_acquisition_open, inspected.mcp_startup_open,
                inspected.live_store_writer)),
            "native_registry_matches": live.registry_hash == inspected.registry_hash == observed["registry_hash"],
            "not_started_before_live": before.get("error", {}).get("code") == "not_started",
            "canonical_closed_after_live": not authority.status()["admission_open"],
            "same_generation": again == live and reused == identity
                and services.get("harness_learning") is owner
                and services.get("harness_configuration_controller") is controller,
            "settings_roles": snapshot["configuration"]["roles"],
            "exact_boot": owner.config.boot_settings, "model_denied": denied is None,
            "registered_native_count": registered}
        await runtime.close()
        result.update(drain=services.shutdown_status()["state"],
            native_settlement=(await owner.process.settlement(0))["state"],
            lease_current_after_close=lease.require_predecessor(lease.predecessor) is None)
        return result
    finally:
        await runtime.close()


async def partial_registry_case(root, services, authority, store, frozen, spec, lease, config):
    from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime
    from renulus.runtime.harness_configuration import Candidate, ConfigurationAuthority
    from renulus.runtime.harness_gateway import GatewayBounds
    from renulus.runtime.harness_model_registry import HarnessModelRegistry, ModelRegistryBounds
    from renulus.storage import Database
    import httpx

    products = []
    foreign = ConfigurationAuthority(Database(root.parent / "foreign-registry.sqlite3"))

    def factory(resolve):
        def no_http(request):
            raise AssertionError("No request is admitted by this synthetic registry")
        registry = HarnessModelRegistry(services.get("provider"), foreign, resolve_run=resolve,
            evidence=lambda route: None, http_transport=lambda route: httpx.MockTransport(no_http),
            gateway_bounds=GatewayBounds(max_request_bytes=65536, max_response_bytes=65536, timeout_seconds=2),
            bounds=ModelRegistryBounds(max_runs=1, max_plans_per_run=1, max_owned=1,
                max_retained_bytes=800000, max_manifest_bytes=65536, max_frame_bytes=65536))
        products.append(registry)
        return registry

    runtime = ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
        config=config, launch_store=store, candidate_root=root.parent / "candidates", attempt_timeout=10,
        model_registry_factory=factory)
    version = authority.stage(spec)
    try:
        await runtime.inspect_candidate(Candidate(version, spec, 0))
        code = None
    except Exception as error:
        code = getattr(error, "code", type(error).__name__)
    await runtime.close()
    return {"code": code, "installed": "harness_learning" in services.registry,
        "candidate_created": (root.parent / "candidates").exists(),
        "registry_settlement": products[0].status().state, "drain": services.shutdown_status()["state"]}


async def candidate_case(case, root, services, authority, store, frozen, spec, lease, config):
    from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime
    from renulus.runtime.harness_configuration import Candidate, RolePolicy

    calls = []

    def factory(resolve):
        calls.append(resolve)
        raise AssertionError("The untrusted candidate must not construct a model registry")

    runtime = ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
        config=config, launch_store=store, candidate_root=root.parent / "candidates", attempt_timeout=10,
        model_registry_factory=factory)
    version = authority.stage(spec)
    candidate = Candidate(version, spec, 0)
    field = case.removeprefix("candidate-")
    if field == "unpersisted":
        candidate = replace(candidate, version="b" * 64)
    elif field == "policy":
        candidate = replace(candidate, spec=spec.model_copy(update={"roles": (
            RolePolicy(purpose="explain", output_tokens=32),)}))
    elif field == "epoch":
        candidate = replace(candidate, grant_epoch=1)
    else:
        candidate = replace(candidate, generation_open=True)
    try:
        await runtime.inspect_candidate(candidate)
        code = None
    except Exception as error:
        code = getattr(error, "code", type(error).__name__)
    await runtime.close()
    return {"code": code, "installed": "harness_learning" in services.registry,
        "factory_calls": len(calls), "candidate_created": (root.parent / "candidates").exists(),
        "requested_unchanged": authority.status()["requested"] == version,
        "drain": services.shutdown_status()["state"]}


async def factory_error_case(root, services, authority, store, frozen, spec, lease, config):
    import traceback
    from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime
    from renulus.runtime.harness_configuration import Candidate

    calls = []
    canary = "SYNTHETIC_BOOTSTRAP_FACTORY_DIAGNOSTIC_CANARY"

    def factory(resolve):
        calls.append(resolve)
        raise RuntimeError(canary)

    runtime = ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
        config=config, launch_store=store, candidate_root=root.parent / "candidates", attempt_timeout=10,
        model_registry_factory=factory)
    version = authority.stage(spec)
    result = {}
    try:
        await runtime.inspect_candidate(Candidate(version, spec, 0))
    except Exception as error:
        result.update(code=getattr(error, "code", type(error).__name__),
            status=getattr(error, "status", None), retryable=getattr(error, "retryable", None),
            safe_diagnostic=canary not in str(error) and canary not in "".join(traceback.format_exception(error)))
    await runtime.close()
    result.update(installed="harness_learning" in services.registry, factory_calls=len(calls),
        candidate_created=(root.parent / "candidates").exists(), drain=services.shutdown_status()["state"])
    return result


async def held_close_case(root, services, authority, store, frozen, spec, lease, config):
    from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime

    entered, release = asyncio.Event(), asyncio.Event()
    calls, order = [], []

    async def producer():
        calls.append("producer")
        entered.set()
        await release.wait()
        order.append("finalizer")

    def dependency():
        order.append("dependency")

    services.on_shutdown.append(producer)
    services.on_shutdown_dependencies.append(dependency)
    runtime = ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
        config=config, launch_store=store, candidate_root=root.parent / "candidates", attempt_timeout=10)
    first = asyncio.create_task(runtime.close())
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 5)
        first.cancel()
        second = asyncio.create_task(runtime.close())
        await asyncio.sleep(0)
        result = {"held_state": services.shutdown_status()["state"],
            "observers_retained": not first.done() and not second.done()}
        assert lease.require_predecessor(lease.predecessor) is None
    finally:
        release.set()
        await asyncio.gather(first, *([second] if second is not None else []))
    result.update(producer_calls=len(calls), dependency_after_finalizer=order == ["finalizer", "dependency"],
        drain=services.shutdown_status()["state"],
        lease_current_after_close=lease.require_predecessor(lease.predecessor) is None)
    return result


async def scenario(case, root):
    services, authority, store, frozen, spec, lease, config = context(root)
    try:
        if case == "sdk":
            return await sdk_case(root, services, authority, store, frozen, lease, config)
        if case == "partial-registry":
            return await partial_registry_case(root, services, authority, store, frozen, spec, lease, config)
        if case.startswith("candidate-"):
            return await candidate_case(case, root, services, authority, store, frozen, spec, lease, config)
        if case == "factory-error":
            return await factory_error_case(root, services, authority, store, frozen, spec, lease, config)
        if case == "held-close":
            return await held_close_case(root, services, authority, store, frozen, spec, lease, config)
        before = tuple(services.on_shutdown_dependencies)
        attempt_timeout = 10
        if case == "copied-issuer":
            lease = copy.copy(lease)
        elif case.startswith("foreign-"):
            field = case.removeprefix("foreign-")
            changes = {"root": {"profile_root": root.parent / "other"},
                "profile": {"profile_id": "other-profile"},
                "runtime-store": {"store_id": "other-runtime"},
                "domain-store": {"domain_store_id": "other-domain"},
                "domain-path": {"domain_path": "state/other.sqlite3"}}
            if field in changes:
                config = replace(config, **changes[field])
            elif field == "authority":
                from renulus.runtime.harness_configuration import ConfigurationAuthority
                from renulus.storage import Database
                authority = ConfigurationAuthority(Database(root.parent / "foreign.sqlite3"))
            else:
                from renulus.runtime.manager import ProviderManager
                from renulus.storage import AppPaths
                services.registry["provider"] = ProviderManager(AppPaths.create(root.parent / "other", REPO))
        elif case.startswith("bounds-"):
            field = case.removeprefix("bounds-")
            if field.startswith("attempt-"):
                attempt_timeout = {"attempt-zero": 0, "attempt-boolean": True,
                                   "attempt-infinite": float("inf")}[field]
            else:
                config = replace(config, **({"max_control_inflight": 0} if field == "control-zero"
                                            else {"start_timeout": float("inf")}))
        elif case.startswith("launch-"):
            from renulus.runtime.harness_configuration import RolePolicy
            from renulus.runtime.harness_launch import FrozenLaunchInputs
            field = case.removeprefix("launch-")
            artifact = root.parent / "artifacts" / (frozen.sha256 + ".json")
            if field == "missing":
                artifact.unlink()
            elif field == "tampered":
                artifact.write_bytes(b"synthetic invalid JSON")
            elif field == "missing-reference":
                spec = spec.model_copy(update={"inputs": ()})
            elif field == "policy-mismatch":
                spec = spec.model_copy(update={"roles": (RolePolicy(purpose="explain", output_tokens=32),)})
            else:
                frozen = FrozenLaunchInputs(boot_settings={"different": True}, connection=spec.connection,
                    roles=spec.roles, inputs=(), capabilities=spec.capabilities, context=spec.context,
                    attempts=spec.attempts, children=spec.children)
        try:
            from renulus.runtime.harness_bootstrap_runtime import ManagedBootstrapRuntime
            ManagedBootstrapRuntime(spec, frozen, lease, services=services, authority=authority,
                config=config, launch_store=store, candidate_root=root.parent / "candidates",
                attempt_timeout=attempt_timeout)
            code = None
        except Exception as error:
            code = getattr(error, "code", type(error).__name__)
        return {"code": code, "installed": "harness_learning" in services.registry,
            "candidate_created": (root.parent / "candidates").exists(),
            "shutdown_changed": tuple(services.on_shutdown_dependencies) != before}
    finally:
        await services.finish_shutdown()


if __name__ == "__main__":
    print(json.dumps({"actual_pid": os.getpid()}), flush=True)
    try:
        print(json.dumps(asyncio.run(scenario(sys.argv[1], Path(sys.argv[2])))), flush=True)
    except Exception as error:
        print(json.dumps({"failure": getattr(error, "code", type(error).__name__)}), flush=True)
