# SPDX-License-Identifier: MIT
"""Real Windows issuers in dedicated children; synthetic runtime observation only."""
import asyncio
import copy
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest

from test_harness_profile_owner import ObservedChild


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Actual Windows profile issuer")
REPO = Path(__file__).resolve().parents[2]


def run_owned(case, root, metadata=None):
    environment = {**os.environ, "PYTHONPATH": str(REPO / "runtime"),
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    process = subprocess.Popen(
        [sys.executable, "-B", "-u", str(Path(__file__).resolve()), case, str(root),
         json.dumps(metadata or {})],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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
        assert first, process.stderr.read()
        actual = ObservedChild(json.loads(first)["actual_pid"])
        line = messages.get(timeout=45)
        assert line, process.stderr.read()
        result = json.loads(line)
        assert actual.wait(10000) == 0, "Owned bootstrap child did not settle"
        process.wait(timeout=10)
        assert process.returncode == 0, result
        assert "failure" not in result, result
        return result
    finally:
        if actual:
            if actual.wait(0) == 258:
                actual.terminate()  # Only this retained, owned synthetic child.
                assert actual.wait(5000) == 0
            actual.close()
        elif process.poll() is None:
            process.terminate()  # Only our owned launcher, before child identification.
        process.wait(timeout=10)
        reader.join(timeout=2)
        process.stdout.close()
        process.stderr.close()


def test_copied_issuer_denies_before_application_mutation(tmp_path):
    result = run_owned("copied-issuer", tmp_path / "profile")
    assert result == {"code": "profile_owner_lease_unbound", "mutated": False}


def test_foreign_scope_denies_before_application_mutation(tmp_path):
    result = run_owned("foreign-scope", tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_conflict", "mutated": False}


def test_application_creation_rechecks_main_thread_before_mutation(tmp_path):
    result = run_owned("worker-create", tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_main_thread_required", "mutated": False}


def test_no_account_remains_null_and_closed_without_runtime_assembly(tmp_path):
    result = run_owned("no-account", tmp_path / "profile")
    assert result == {"effective": None, "requested": None, "admission_open": False,
                      "reason_code": "harness_bootstrap_no_connection"}


@pytest.mark.parametrize("foreign", ["authority", "provider"])
def test_foreign_services_binding_denies_before_reconciliation(tmp_path, foreign):
    result = run_owned("foreign-" + foreign, tmp_path / "profile")
    assert result["code"] == "harness_bootstrap_conflict", result


def test_explicit_initial_policy_opens_only_after_candidate_and_live_observation(tmp_path):
    result = run_owned("initial", tmp_path / "profile")
    assert result["admission_open"] is True
    assert result["effective"] == result["requested"] == result["observed_version"]
    assert result["events"] == ["candidate", "candidate-settled", "live"]


def test_reopen_preserves_effective_requested_and_revocations(tmp_path):
    root = tmp_path / "profile"
    previous = run_owned("seed-existing", root)
    result = run_owned("reopen-existing", root)
    assert result["admission_open"] is True
    assert result["effective"] == previous["effective"]
    assert result["requested"] == previous["requested"] != result["effective"]
    assert result["grant_epoch"] == previous["grant_epoch"] == 1
    assert result["revoked"] == ["tools"]


def test_predecessor_pins_retire_child_first_without_confirming_unknown_results(tmp_path):
    root = tmp_path / "profile"
    previous = run_owned("seed-pins", root)
    result = run_owned("reopen-pins", root, previous)
    assert result["admission_open"] is True
    assert result["run_states"] == ["settled", "settled"]
    assert result["attempt_states"] == ["uncertain", "cancelled_before_send"]
    assert result["pinned_runs"] == []


def test_unexpected_fault_is_sanitized_only_after_runtime_cleanup(tmp_path):
    result = run_owned("initial-fault", tmp_path / "profile")
    assert result["code"] == "harness_bootstrap_failed"
    assert "SYNTHETIC-SECRET" not in result["error_text"]
    assert result["admission_open"] is False
    assert result["events"] == ["candidate", "closing", "closed"]


def test_application_cannot_be_recreated_under_the_same_coordinator(tmp_path):
    result = run_owned("recreate-app", tmp_path / "profile")
    assert result == {"code": "harness_bootstrap_conflict"}


@pytest.mark.parametrize("change, expected", [("arguments", "harness_bootstrap_conflict"),
                                             ("connection", "connection_changed")])
def test_start_observers_cannot_rebind_or_publish_stale_health(tmp_path, change, expected):
    result = run_owned("initial-observe-" + change, tmp_path / "profile")
    assert result["code"] == expected
    assert result["events"] == ["candidate", "candidate-settled", "live"]


def test_initial_policy_is_rejected_when_existing_pointers_are_present(tmp_path):
    root = tmp_path / "profile"
    previous = run_owned("seed-existing", root)
    result = run_owned("reopen-existing-initial", root)
    assert result["code"] == "activation_conflict"
    assert result["admission_open"] is False and result["events"] == []
    assert result["effective"] == previous["effective"]
    assert result["requested"] == previous["requested"]


def test_application_provisioning_fault_is_sanitized_and_cannot_retry(tmp_path):
    result = run_owned("create-fault", tmp_path / "profile")
    assert result["code"] == "harness_bootstrap_failed"
    assert "SYNTHETIC-SECRET" not in result["error_text"]
    assert result["retry_code"] == "harness_bootstrap_conflict"
    assert result["path_leaked"] is False


@pytest.mark.parametrize("phase", ["candidate", "cleanup"])
def test_observer_cancellation_preserves_start_and_cleanup_ownership(tmp_path, phase):
    result = run_owned("initial-cancel-" + phase, tmp_path / "profile")
    assert result["observer_cancelled"] is True
    assert result["early_publication"] is False
    assert result["second_observer_pending"] is True
    if phase == "candidate":
        assert result["admission_open"] is True and result["code"] is None
        assert result["events"] == ["candidate", "candidate-settled", "live"]
    else:
        assert result["admission_open"] is False and result["code"] == "harness_bootstrap_failed"
        assert result["events"] == ["candidate", "closing", "closed"]


def test_close_seals_cancelled_start_and_drains_held_inspection_and_finalizer(tmp_path):
    result = run_owned("initial-close-held", tmp_path / "profile")
    assert result == {"observer_cancelled": True, "new_start_code": "runtime_stopping",
        "repeat_start_code": "runtime_stopping", "drain_pending_candidate": True,
        "drain_pending_finalizer": True, "effective_after_candidate": None,
        "admission_open": False, "events": ["candidate", "candidate-settled", "closing", "closed"]}


def test_close_seals_held_live_start_before_canonical_admission(tmp_path):
    result = run_owned("initial-close-live", tmp_path / "profile")
    assert result["new_start_code"] == result["repeat_start_code"] == "runtime_stopping"
    assert result["drain_pending_candidate"] and result["drain_pending_finalizer"]
    assert result["effective_after_candidate"] is not None and not result["admission_open"]
    assert result["events"] == ["candidate", "candidate-settled", "live", "closing", "closed"]


def test_close_observer_cancellation_keeps_one_shared_runtime_drain(tmp_path):
    result = run_owned("initial-close-observer", tmp_path / "profile")
    assert result["close_observer_cancelled"] is True
    assert result["drain_pending_candidate"] and result["drain_pending_finalizer"]
    assert result["admission_open"] is False
    assert result["events"] == ["candidate", "candidate-settled", "closing", "closed"]


def test_pending_start_observer_reports_stopping_after_owned_settlement(tmp_path):
    result = run_owned("initial-close-pending", tmp_path / "profile")
    assert result["observer_cancelled"] is False
    assert result["pending_start_code"] == "runtime_stopping"
    assert result["admission_open"] is False
    assert result["events"] == ["candidate", "candidate-settled", "closing", "closed"]


def test_successful_start_close_drains_runtime_before_services_dependencies_once(tmp_path):
    result = run_owned("initial-close-success", tmp_path / "profile")
    assert result["start_code"] == "runtime_stopping"
    assert result["shutdown_state"] == "settled"
    assert result["events"] == ["candidate", "candidate-settled", "live", "closing",
        "dependencies-closed", "closed"]


@pytest.mark.parametrize("phase", ["settled", "queued"])
def test_ordinary_services_shutdown_seals_start_before_external_coordinator_drain(tmp_path, phase):
    result = run_owned("initial-services-stop-" + phase, tmp_path / "profile")
    assert result == {"start_code": "runtime_stopping", "stale_health": False,
        "shutdown_state": "settled", "events": ["candidate", "candidate-settled", "live",
            "dependencies-closed", "closing", "closed"]}


def test_close_before_application_creation_seals_provisioning(tmp_path):
    result = run_owned("close-before-app", tmp_path / "profile")
    assert result == {"code": "runtime_stopping", "mutated": False}


def test_close_reuses_classified_pending_finalizer_without_retry_or_healthy_result(tmp_path):
    result = run_owned("initial-close-failed", tmp_path / "profile")
    assert result["start_error"] == "harness_configuration_settlement_pending"
    assert result["close_errors"] == ["harness_configuration_settlement_pending"] * 2
    assert result["repeat_start_code"] == "runtime_stopping"
    assert result["admission_open"] is False
    assert "SYNTHETIC-SECRET" not in result["error_text"]
    assert result["events"] == ["candidate", "candidate-settled", "live", "closing", "cleanup-pending"]


@pytest.mark.parametrize("phase", ["candidate", "live"])
@pytest.mark.parametrize("change, expected", [("connection", "connection_changed"),
    ("requested", "activation_conflict"), ("epoch", "activation_conflict"),
    ("artifact", "harness_launch_invalid")])
def test_current_evidence_is_rechecked_after_native_await(tmp_path, phase, change, expected):
    result = run_owned("initial-race-" + phase + "-" + change, tmp_path / "profile")
    assert result["code"] == expected
    assert result["admission_open"] is False
    assert result["events"][-2:] == ["closing", "closed"]
    if phase == "candidate":
        assert "live" not in result["events"]


@pytest.mark.parametrize("flag", ["generation_open", "recovery_open",
    "package_acquisition_open", "mcp_startup_open", "live_store_writer", "unknown"])
def test_candidate_requires_actual_closed_typed_observation(tmp_path, flag):
    result = run_owned("initial-candidate-deny-" + flag, tmp_path / "profile")
    assert result["code"] == "candidate_unhealthy"
    assert result["admission_open"] is False and "live" not in result["events"]
    assert result["events"][-2:] == ["closing", "closed"]


@pytest.mark.parametrize("evidence", ["hash", "epoch", "version", "unhealthy", "unknown"])
def test_live_requires_exact_healthy_typed_registry_evidence(tmp_path, evidence):
    result = run_owned("initial-live-deny-" + evidence, tmp_path / "profile")
    assert result["code"] == "registry_mismatch"
    assert result["admission_open"] is False
    assert result["events"][-2:] == ["closing", "closed"]


@pytest.mark.parametrize("cleanup_pending", [False, True])
def test_native_held_work_denies_without_releasing_recovery_claims(tmp_path, cleanup_pending):
    result = run_owned("initial-native-held" + ("-cleanup-pending" if cleanup_pending else ""),
                       tmp_path / "profile")
    expected = "harness_configuration_settlement_pending" if cleanup_pending else "harness_native_recovery_pending"
    assert result["code"] == expected and result["admission_open"] is False
    assert "SYNTHETIC-SECRET" not in result["error_text"]
    assert result["events"][-1] == ("cleanup-pending" if cleanup_pending else "closed")


def test_reopen_without_account_preserves_existing_pointers_without_runtime(tmp_path):
    root = tmp_path / "profile"
    previous = run_owned("seed-existing", root)
    result = run_owned("reopen-no-account", root)
    assert result["admission_open"] is False and result["events"] == []
    assert result["effective"] == previous["effective"]
    assert result["requested"] == previous["requested"]
    assert result["grant_epoch"] == 1 and result["revoked"] == ["tools"]


@pytest.mark.parametrize("evidence, expected", [("artifact", "harness_launch_invalid"),
    ("connection", "connection_changed"), ("requested", "activation_conflict")])
def test_initial_unknown_or_changed_evidence_denies_before_runtime(tmp_path, evidence, expected):
    result = run_owned("initial-pre-deny-" + evidence, tmp_path / "profile")
    assert result["code"] == expected and result["admission_open"] is False
    assert result["events"] == [] and result["effective"] is None


def test_current_process_pins_are_not_mistaken_for_a_settled_predecessor(tmp_path):
    result = run_owned("initial-current-pins", tmp_path / "profile")
    assert result["code"] == "harness_bootstrap_recovery_pending"
    assert result["run_state"] == "active"
    assert result["attempt_state"] == "dispatched"


def test_reopened_lease_cannot_reconcile_current_pins_through_a_second_coordinator(tmp_path):
    root = tmp_path / "profile"
    run_owned("seed-existing", root)
    result = run_owned("reopen-current-pins", root)
    assert result["code"] == "harness_bootstrap_conflict"
    assert result["run_state"] == "active"
    assert result["attempt_state"] == "dispatched"


def selected_context(scope, lease):
    import httpx
    from uuid import uuid4
    from renulus.runtime.harness_bootstrap import HarnessBootstrap
    from renulus.runtime.harness_configuration import (
        AttemptPolicy, ChildPolicy, ConfigurationAuthority, ContextPolicy, InputHash, RolePolicy,
    )
    from renulus.runtime.harness_launch import FrozenLaunchInputs, LaunchArtifactStore, finish_spec
    from renulus.runtime.manager import ProviderManager
    from renulus.runtime.protected import ConnectionStore
    bootstrap = HarnessBootstrap(scope, profile_owner=lease)
    app = bootstrap.create_app(source_root=REPO)
    services = app.state.services
    authority = ConfigurationAuthority(services.db)
    if not (services.paths.state / "runtime/connections.dpapi").exists():
        ConnectionStore(services.paths.root, services.paths.state).save({
            "version": 1, "host_id": uuid4().urn, "selected_provider": "opencode-go",
            "selected_models": {"opencode-go": None},
            "connections": {"opencode-go": {"access_token": "synthetic-never-sent"}},
            "credential_metadata": {"opencode-go": {"reference": str(uuid4()),
                "epoch": 0, "authentication_required": False}},
        })
    def no_network(request):
        raise AssertionError("Bootstrap must not use any provider IO")
    provider = ProviderManager(services.paths, http_transport=httpx.MockTransport(no_network))
    store = LaunchArtifactStore(scope.root.parent / "artifacts", live_root=scope.root,
                               candidate_root=scope.root.parent / "candidates")
    inputs = FrozenLaunchInputs(boot_settings={"config": {"instructions": ["Synthetic CKD"]}},
        connection=provider.configuration_connection(),
        roles=(RolePolicy(purpose="explain", output_tokens=128),
               RolePolicy(purpose="evidence-review", output_tokens=128)),
        inputs=(InputHash(kind="build", name="synthetic-cohort", sha256="b" * 64),),
        capabilities=("text", "tools"), context=ContextPolicy(requested_window_tokens=8192),
        attempts=AttemptPolicy(), children=ChildPolicy())
    store.save(inputs)
    return bootstrap, authority, provider, store, inputs, finish_spec(inputs, "a" * 64), services


class SyntheticRuntime:
    """The external native lifecycle port is synthetic, with explicit closed observations."""
    def __init__(self, authority, mode=None, hook=None, shutdown=None):
        self.authority = authority
        self.events = []
        self.candidate = None
        self.mode = mode or ""
        self.hook = hook
        self.shutdown = shutdown
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.close_entered, self.close_release = asyncio.Event(), asyncio.Event()

    async def inspect_candidate(self, candidate):
        from renulus.runtime.harness_configuration import CandidateHealth
        assert not self.authority.status()["admission_open"]
        self.candidate = candidate
        self.events.append("candidate")
        await asyncio.sleep(0)
        if self.mode in {"cancel-candidate", "close-held-candidate"}:
            self.entered.set()
            await self.release.wait()
        if self.mode in {"fault", "cancel-cleanup"}:
            raise ValueError("SYNTHETIC-SECRET private path must not escape bootstrap")
        self.events.append("candidate-settled")
        if self.hook:
            await self.hook("candidate")
        health = CandidateHealth(configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
            registry_hash="a" * 64, healthy=True, generation_open=False, recovery_open=False,
            package_acquisition_open=False, mcp_startup_open=False, live_store_writer=False)
        if self.mode.startswith("candidate-deny-"):
            flag = self.mode.removeprefix("candidate-deny-")
            return None if flag == "unknown" else health.model_copy(update={flag: True})
        return health

    async def start_live(self, candidate):
        from renulus.runtime.harness_configuration_controller import RegistryHealth
        snapshot = self.authority.activation_snapshot()
        assert snapshot["effective"] == candidate.version and not snapshot["admission_open"]
        assert snapshot["grant_epoch"] == candidate.grant_epoch
        self.events.append("live")
        await asyncio.sleep(0)
        if self.mode == "close-held-live":
            self.entered.set()
            await self.release.wait()
        if self.hook:
            await self.hook("live")
        if self.mode.startswith("native-held"):
            from renulus.contracts import ApiError
            raise ApiError("harness_native_recovery_pending", "SYNTHETIC-SECRET retained native claim", 409, True)
        health = RegistryHealth(configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
                                registry_hash="a" * 64, healthy=True)
        if self.mode.startswith("live-deny-"):
            evidence = self.mode.removeprefix("live-deny-")
            if evidence == "unknown":
                return {"healthy": True}
            changes = {"hash": {"registry_hash": "f" * 64},
                "epoch": {"grant_epoch": candidate.grant_epoch + 1},
                "version": {"configuration_version": "f" * 64}, "unhealthy": {"healthy": False}}
            return health.model_copy(update=changes[evidence])
        return health

    async def close(self):
        self.events.append("closing")
        await asyncio.sleep(0)
        if self.mode == "cancel-cleanup":
            self.entered.set()
            await self.release.wait()
        if self.mode in {"close-held-candidate", "close-held-live"}:
            self.close_entered.set()
            await self.close_release.wait()
        if self.shutdown is not None:
            await self.shutdown()
        if self.mode == "native-held-cleanup-pending":
            from renulus.contracts import ApiError
            self.events.append("cleanup-pending")
            raise ApiError("harness_configuration_settlement_pending", "SYNTHETIC-SECRET pending cleanup", 503, True)
        self.events.append("closed")


async def scenario(case, root, metadata=None):
    from renulus.runtime.harness_bootstrap import HarnessBootstrap
    from renulus.runtime.harness_profile_owner import (
        ProfileOwnerScope, acquire_profile_owner,
    )
    scope = ProfileOwnerScope(root, "synthetic-profile", "synthetic-domain", "synthetic-runtime")
    lease = acquire_profile_owner(scope, initialize_new=not case.startswith("reopen-"))
    if case == "close-before-app":
        bootstrap = HarnessBootstrap(scope, profile_owner=lease)
        await bootstrap.close()
        await bootstrap.close()
        try:
            bootstrap.create_app(source_root=REPO)
            code = None
        except Exception as error:
            code = getattr(error, "code", type(error).__name__)
        return {"code": code, "mutated": (root / "state").exists()}
    if case == "create-fault":
        import traceback
        bootstrap = HarnessBootstrap(scope, profile_owner=lease)
        code, text, retry_code = None, "", None
        (root / "state").write_text("synthetic blocker", encoding="utf-8")
        try:
            bootstrap.create_app(source_root=REPO)
        except Exception as error:
            code, text = getattr(error, "code", type(error).__name__), "".join(traceback.format_exception(error))
        try:
            bootstrap.create_app(source_root=REPO)
        except Exception as error:
            retry_code = getattr(error, "code", type(error).__name__)
        return {"code": code, "error_text": text, "retry_code": retry_code,
                "path_leaked": str(root) in text}
    if case == "copied-issuer":
        code = None
        try:
            bootstrap = HarnessBootstrap(scope, profile_owner=copy.copy(lease))
            bootstrap.create_app(source_root=REPO)
        except Exception as error:
            code = getattr(error, "code", type(error).__name__)
        return {"code": code, "mutated": (root / "state").exists()}
    if case == "foreign-scope":
        foreign = ProfileOwnerScope(root / "foreign", scope.profile_id,
            scope.domain_store_id, scope.runtime_store_id)
        code = None
        try:
            HarnessBootstrap(foreign, profile_owner=lease).create_app(source_root=REPO)
        except Exception as error:
            code = getattr(error, "code", type(error).__name__)
        return {"code": code, "mutated": (foreign.root / "state").exists()}
    if case == "worker-create":
        bootstrap = HarnessBootstrap(scope, profile_owner=lease)
        codes = []
        def create():
            try:
                bootstrap.create_app(source_root=REPO)
                codes.append(None)
            except Exception as error:
                codes.append(getattr(error, "code", type(error).__name__))
        worker = threading.Thread(target=create)
        worker.start()
        worker.join()
        return {"code": codes[0], "mutated": (root / "state").exists()}
    if case == "no-account" or case in {"foreign-authority", "foreign-provider", "recreate-app"}:
        from renulus.runtime.harness_configuration import ConfigurationAuthority
        from renulus.runtime.harness_launch import LaunchArtifactStore
        from renulus.runtime.manager import ProviderManager
        bootstrap = HarnessBootstrap(scope, profile_owner=lease)
        app = bootstrap.create_app(source_root=REPO)
        if case == "recreate-app":
            try:
                bootstrap.create_app(source_root=REPO)
                return {"code": None}
            except Exception as error:
                return {"code": getattr(error, "code", type(error).__name__)}
        services = app.state.services
        authority = ConfigurationAuthority(services.db)
        provider = ProviderManager(services.paths)
        store = LaunchArtifactStore(root.parent / "artifacts", live_root=root,
                                  candidate_root=root.parent / "candidates")
        def no_runtime(*args):
            raise AssertionError("No selected account may assemble a runtime")
        if case.startswith("foreign-"):
            from renulus.storage import AppPaths, Database
            other = AppPaths.create(root.parent / "other", REPO)
            if case == "foreign-authority":
                authority = ConfigurationAuthority(Database(other.database))
            else:
                provider = ProviderManager(other)
            try:
                await bootstrap.start(authority=authority, provider=provider,
                    launch_store=store, assemble_runtime=no_runtime)
                return {"code": None}
            except Exception as error:
                return {"code": getattr(error, "code", type(error).__name__)}
        result = await bootstrap.start(authority=authority, provider=provider,
            launch_store=store, assemble_runtime=no_runtime)
        status = authority.status()
        return {"effective": status["effective"], "requested": status["requested"],
                "admission_open": result.admission_open, "reason_code": result.reason_code}
    if case.startswith("initial") or case in {"seed-existing", "reopen-existing", "seed-pins",
                                             "reopen-pins", "reopen-existing-initial", "reopen-no-account",
                                             "reopen-current-pins"}:
        bootstrap, authority, provider, store, inputs, spec, services = selected_context(scope, lease)
        mode = "fault" if case == "initial-fault" else case.removeprefix("initial-")
        if case in {"initial-close-held", "initial-close-observer", "initial-close-pending"}:
            mode = "close-held-candidate"
        elif case == "initial-close-live":
            mode = "close-held-live"
        elif case == "initial-close-failed":
            mode = "native-held-cleanup-pending"
        async def interleave(phase):
            if not case.startswith("initial-race-"):
                return
            chosen_phase, change = case.removeprefix("initial-race-").split("-")
            if chosen_phase != phase:
                return
            if change == "connection":
                provider.select("opencode-go", "deepseek-v4.1-flash")
            elif change == "requested":
                from renulus.runtime.harness_configuration import RolePolicy
                authority.stage(spec.model_copy(update={"roles": (RolePolicy(purpose="explain", output_tokens=64),)}))
            elif change == "epoch":
                authority.revoke("text")
            elif change == "artifact":
                (root.parent / "artifacts" / (inputs.sha256 + ".json")).write_bytes(b"synthetic tampering")
        runtime = SyntheticRuntime(authority, mode=mode, hook=interleave,
            shutdown=services.finish_shutdown if case == "initial-close-success" or case.startswith("initial-services-stop-") else None)
        if case == "initial-close-success" or case.startswith("initial-services-stop-"):
            services.on_shutdown_dependencies.append(lambda: runtime.events.append("dependencies-closed"))
        if case == "reopen-no-account":
            await provider.disconnect("opencode-go")
        if case.startswith("initial-pre-deny-"):
            evidence = case.removeprefix("initial-pre-deny-")
            if evidence == "artifact":
                (root.parent / "artifacts" / (inputs.sha256 + ".json")).unlink()
            elif evidence == "connection":
                provider.select("opencode-go", "deepseek-v4.1-flash")
            elif evidence == "requested":
                authority.stage(spec)
        def assemble(given_spec, given_inputs, given_lease):
            assert given_spec == spec and given_inputs == inputs and given_lease is lease
            return runtime
        arguments = dict(authority=authority, provider=provider, launch_store=store,
            assemble_runtime=assemble, initial_spec=None if case in {"reopen-existing",
                "reopen-pins", "reopen-no-account", "reopen-current-pins"} else spec)
        if case in {"initial-close-held", "initial-close-live", "initial-close-observer", "initial-close-pending"}:
            observer = asyncio.create_task(bootstrap.start(**arguments))
            await runtime.entered.wait()
            cancelled = False
            if case != "initial-close-pending":
                observer.cancel()
                try:
                    await observer
                except asyncio.CancelledError:
                    cancelled = True
            try:
                draining = asyncio.create_task(bootstrap.close())
                await asyncio.sleep(0)
                close_cancelled = False
                if case == "initial-close-observer":
                    draining.cancel()
                    try:
                        await draining
                    except asyncio.CancelledError:
                        close_cancelled = True
                    draining = asyncio.create_task(bootstrap.close())
                    await asyncio.sleep(0)
                async def start_code():
                    try:
                        await asyncio.wait_for(bootstrap.start(**arguments), timeout=0.2)
                    except Exception as error:
                        return getattr(error, "code", type(error).__name__)
                    return None
                new_code = await start_code()
                candidate_pending = not draining.done()
                runtime.release.set()
                await asyncio.wait_for(runtime.close_entered.wait(), timeout=5)
                finalizer_pending = not draining.done()
                effective = authority.status()["effective"]
                pending_code = None
                if case == "initial-close-pending":
                    try:
                        await asyncio.wait_for(observer, timeout=0.2)
                    except Exception as error:
                        pending_code = getattr(error, "code", type(error).__name__)
                runtime.close_release.set()
                await draining
                await bootstrap.close()
                projected = {"observer_cancelled": cancelled, "new_start_code": new_code,
                    "repeat_start_code": await start_code(), "drain_pending_candidate": candidate_pending,
                    "drain_pending_finalizer": finalizer_pending, "effective_after_candidate": effective,
                    "admission_open": authority.status()["admission_open"], "events": runtime.events}
                if case == "initial-close-observer":
                    projected["close_observer_cancelled"] = close_cancelled
                if case == "initial-close-pending":
                    projected["pending_start_code"] = pending_code
                return projected
            finally:
                runtime.release.set()
                runtime.close_release.set()
        if case.startswith("initial-cancel-"):
            observer = asyncio.create_task(bootstrap.start(**arguments))
            await runtime.entered.wait()
            observer.cancel()
            cancelled = False
            try:
                await observer
            except asyncio.CancelledError:
                cancelled = True
            early = authority.status()["admission_open"]
            second = asyncio.create_task(bootstrap.start(**arguments))
            await asyncio.sleep(0)
            pending = not second.done()
            runtime.release.set()
            code = None
            try:
                await second
            except Exception as error:
                code = getattr(error, "code", type(error).__name__)
            return {"observer_cancelled": cancelled, "early_publication": early,
                "second_observer_pending": pending, "code": code,
                "admission_open": authority.status()["admission_open"], "events": runtime.events}
        try:
            result = await bootstrap.start(**arguments)
        except Exception as error:
            import traceback
            if case == "initial-close-failed":
                start_error = getattr(error, "code", type(error).__name__)
                close_errors, errors = [], []
                for _ in range(2):
                    try:
                        await bootstrap.close()
                    except Exception as closing_error:
                        close_errors.append(getattr(closing_error, "code", type(closing_error).__name__))
                        errors.extend(traceback.format_exception(closing_error))
                try:
                    await bootstrap.start(**arguments)
                    repeat_code = None
                except Exception as stopped:
                    repeat_code = getattr(stopped, "code", type(stopped).__name__)
                return {"start_error": start_error, "close_errors": close_errors,
                    "repeat_start_code": repeat_code, "error_text": "".join(errors),
                    "admission_open": authority.status()["admission_open"], "events": runtime.events}
            return {"code": getattr(error, "code", type(error).__name__),
                "error_text": "".join(traceback.format_exception(error)),
                "admission_open": authority.status()["admission_open"], "events": runtime.events,
                "effective": authority.status()["effective"], "requested": authority.status()["requested"]}
        if case.startswith("initial-observe-"):
            if case.endswith("connection"):
                provider.select("opencode-go", "deepseek-v4.1-flash")
            try:
                await bootstrap.start(authority=authority, provider=provider, launch_store=store,
                    assemble_runtime=assemble, initial_spec=None if case.endswith("arguments") else spec)
                return {"code": None, "events": runtime.events}
            except Exception as error:
                return {"code": getattr(error, "code", type(error).__name__), "events": runtime.events}
        if case == "initial-close-success" or case.startswith("initial-services-stop-"):
            stale_health = False
            if case.startswith("initial-services-stop-"):
                shutdown = asyncio.create_task(services.finish_shutdown())
                if case.endswith("queued"):
                    await asyncio.sleep(0)
                    assert services.stopping
                else:
                    await shutdown
                try:
                    stale_health = (await bootstrap.start(**arguments)).admission_open
                    ordinary_code = None
                except Exception as error:
                    ordinary_code = getattr(error, "code", type(error).__name__)
                await shutdown
            await bootstrap.close()
            await bootstrap.close()
            try:
                await bootstrap.start(**arguments)
                code = None
            except Exception as error:
                code = getattr(error, "code", type(error).__name__)
            projected = {"start_code": code, "shutdown_state": services.shutdown_status()["state"],
                "events": runtime.events}
            if case.startswith("initial-services-stop-"):
                projected.update(start_code=ordinary_code, stale_health=stale_health)
            return projected
        if case in {"initial-current-pins", "reopen-current-pins"}:
            from renulus.runtime.harness_configuration import ConfigurationAuthority, RouteLimits
            from renulus.runtime.manager import ProviderManager
            authority.begin_run("current-root", "explain", capability_scope=("text",))
            limits = RouteLimits(input_tokens=8192, output_tokens=1024, window_tokens=8192)
            permit = authority.admit("current-root", "current-step", payload_hash="c" * 64,
                request_kind="primary", connection=spec.connection, limits=limits, input_tokens=64)
            authority.mark_dispatched(permit["permit_id"], connection=spec.connection, limits=limits,
                input_tokens=64, payload_hash="c" * 64)  # Recorded only; no transport.
            other_bootstrap = HarnessBootstrap(scope, profile_owner=lease)
            def denied_factory(*args):
                raise AssertionError("Current-process pins must deny before assembly")
            code = None
            try:
                if case == "initial-current-pins":
                    await bootstrap.start(**arguments)
                other_app = other_bootstrap.create_app(source_root=REPO)
                other_authority = ConfigurationAuthority(other_app.state.services.db)
                other_provider = ProviderManager(other_app.state.services.paths)
                await other_bootstrap.start(authority=other_authority, provider=other_provider,
                    launch_store=store, assemble_runtime=denied_factory)
            except Exception as error:
                code = getattr(error, "code", type(error).__name__)
            return {"code": code, "run_state": authority.run("current-root")["state"],
                    "attempt_state": authority.permit(permit["permit_id"])["state"]}
        permits = []
        if case == "seed-pins":
            from renulus.runtime.harness_configuration import RouteLimits
            authority.begin_run("a-root", "explain", capability_scope=("text",))
            authority.begin_child("z-child", "a-root", "evidence-review", capability_scope=("text",))
            limits = RouteLimits(input_tokens=8192, output_tokens=1024, window_tokens=8192)
            for run_id, kind in (("a-root", "primary"), ("z-child", "child")):
                permit = authority.admit(run_id, "synthetic-step", payload_hash="c" * 64,
                    request_kind=kind, connection=spec.connection, limits=limits, input_tokens=64)
                permits.append(permit["permit_id"])
            authority.mark_dispatched(permits[0], connection=spec.connection, limits=limits,
                input_tokens=64, payload_hash="c" * 64)  # No transport call is made.
        if case in {"seed-existing", "seed-pins"}:
            from renulus.runtime.harness_configuration import RolePolicy
            from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
            requested = FrozenLaunchInputs(boot_settings=inputs.boot_settings, connection=spec.connection,
                roles=(RolePolicy(purpose="explain", output_tokens=64),), inputs=spec.inputs[:-1],
                capabilities=spec.capabilities, context=spec.context, attempts=spec.attempts,
                children=spec.children)
            store.save(requested)
            authority.stage(finish_spec(requested, spec.registry_hash))
            authority.revoke("tools")
        status = authority.activation_snapshot()
        projected = {"effective": status["effective"], "requested": status["requested"],
                "admission_open": result.admission_open, "events": runtime.events,
                "grant_epoch": status["grant_epoch"], "revoked": status["revoked"],
                "observed_version": runtime.candidate.version if runtime.candidate else None}
        if case == "seed-pins":
            projected["permits"] = permits
        if case == "reopen-pins":
            projected.update(run_states=[authority.run(run_id)["state"] for run_id in ("a-root", "z-child")],
                attempt_states=[authority.permit(permit_id)["state"] for permit_id in metadata["permits"]],
                pinned_runs=status["pinned_runs"])
        return projected
    raise AssertionError("Unknown owned synthetic scenario")


if __name__ == "__main__":
    print(json.dumps({"actual_pid": os.getpid()}), flush=True)
    try:
        print(json.dumps(asyncio.run(scenario(sys.argv[1], Path(sys.argv[2]),
            json.loads(sys.argv[3])))), flush=True)
    except BaseException as error:
        print(json.dumps({"failure": type(error).__name__, "message": str(error)}), flush=True)
        raise
