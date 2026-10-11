# SPDX-License-Identifier: MIT
"""Actual interrupted H04 selection/reopen; only cached catalogue IO is synthetic.

The real lifecycle's completed gated-start observation is held before admission.
Only the retained, independently observed Python child is terminated; Windows
job closure must terminate its actual native child before the successor starts.
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


class OwnedStartupChild:
    """Retain only the dedicated child launched for this one public tracer."""
    def __init__(self, phase, root):
        self.observed = None
        self.messages, self.stderr = queue.Queue(), []
        environment = {key: value for key, value in os.environ.items() if key.upper() in {
            "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "PATHEXT", "COMSPEC",
            "SYSTEMDRIVE", "APPDATA", "LOCALAPPDATA", "USERPROFILE", "PROGRAMDATA",
            "RENULUS_LIBRARY_HELPERS", "RENULUS_HARNESS_NODE", "HF_HOME", "HF_HUB_CACHE"}}
        environment.update(PYTHONPATH=str(SOURCE / "runtime"), PYTHONDONTWRITEBYTECODE="1",
            HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1",
            OPENCODE_DISABLE_UPDATE_CHECK="true")
        self.process = subprocess.Popen([sys.executable, "-B", "-u", str(Path(__file__).resolve()),
            phase, str(root)], cwd=SOURCE, env=environment, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, close_fds=True,
            creationflags=subprocess.CREATE_NO_WINDOW)

        def read():
            for line in self.process.stdout:
                self.messages.put(line)
            self.messages.put(None)

        def read_errors():
            for line in self.process.stderr:
                self.stderr.append(line)

        self.reader = threading.Thread(target=read, daemon=True)
        self.error_reader = threading.Thread(target=read_errors, daemon=True)
        self.reader.start()
        self.error_reader.start()

    def __enter__(self):
        from test_harness_profile_owner import ObservedChild
        try:
            identity = self.next(timeout=15)
            assert set(identity) == {"actual_pid"}
            assert identity["actual_pid"] != os.getpid()
            self.observed = ObservedChild(identity["actual_pid"])
            return self
        except BaseException:
            self.close()
            raise

    def next(self, *, timeout=120):
        line = self.messages.get(timeout=timeout)
        assert line, "Owned startup child ended before its public observation: " + "".join(self.stderr)
        result = json.loads(line)
        assert "failure" not in result, result
        return result

    def activate(self):
        self.process.stdin.write("activate\n")
        self.process.stdin.flush()

    def crash(self):
        assert self.observed.wait(0) == 258, "Only a live retained issuer may be crashed"
        self.observed.terminate()
        assert self.observed.wait(10000) == 0
        self.process.wait(timeout=10)
        assert self.process.returncode != 0

    def finish(self):
        assert self.observed.wait(10000) == 0, "Owned successor did not settle"
        self.process.wait(timeout=10)
        assert self.process.returncode == 0, "".join(self.stderr)

    def pipes_settled(self):
        self.reader.join(timeout=10)
        self.error_reader.join(timeout=10)
        assert not self.reader.is_alive() and not self.error_reader.is_alive()
        assert self.messages.get(timeout=1) is None, "Owned stdout must reach EOF"

    def close(self):
        if self.observed is not None:
            if self.observed.wait(0) == 258:
                self.observed.terminate()  # Failure cleanup of this retained issuer only.
                assert self.observed.wait(10000) == 0
        elif self.process.poll() is None:
            self.process.terminate()  # Only the Popen child, before its identity reply.
        self.process.wait(timeout=10)
        self.reader.join(timeout=10)
        self.error_reader.join(timeout=10)
        for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
            pipe.close()
        if self.observed is not None:
            self.observed.close()

    def __exit__(self, *_):
        self.close()


def test_interrupted_selected_configuration_reopens_actual_healthy_predecessor(tmp_path):
    from test_harness_profile_owner import ObservedChild

    root, native_handles = tmp_path / "profile", []
    try:
        with OwnedStartupChild("crash", root) as issuer:
            healthy = issuer.next()
            assert healthy["phase"] == "healthy"
            assert healthy["effective"] == healthy["requested"]
            assert healthy["admission_open"] is True and healthy["activating"] is None
            assert healthy["failed"] is None and healthy["failure_code"] is None
            assert healthy["grant_epoch"] == 0 and healthy["revoked"] == []
            assert healthy["catalogue_requests"] == healthy["ordinary_callback_count"] == 1
            original = ObservedChild(healthy["native"]["pid"],
                creation=healthy["native"]["creation_filetime"])
            native_handles.append(original)
            assert original.wait(0) == 258
            issuer.activate()
            held = issuer.next()
            assert held["phase"] == "selected_before_admission"
            assert held["effective"] == held["requested"] == held["activating"] != healthy["effective"]
            assert held["admission_open"] is False
            assert held["failed"] is None and held["failure_code"] is None
            assert held["grant_epoch"] == 1 and held["revoked"] == ["tools"]
            assert held["native_configuration"] == held["effective"]
            assert held["registry_hash"] == healthy["registry_hash"]
            assert held["launch_hash"] != healthy["launch_hash"]
            assert held["old_native_settlement"] == "settled" and held["old_domain_active"] == 0
            assert original.wait(0) == 0, "The old live child must exit before fresh selection"
            selected = ObservedChild(held["native"]["pid"], creation=held["native"]["creation_filetime"])
            native_handles.append(selected)
            assert selected.wait(0) == 258, "The real selected B child must still be alive"
            issuer.crash()
            assert selected.wait(10000) == 0, "Issuer job closure must terminate selected B"
            issuer.pipes_settled()

        with OwnedStartupChild("reopen", root) as successor:
            reopened = successor.next()
            assert reopened["phase"] == "reopened"
            successor.finish()
            successor.pipes_settled()

        assert reopened["before"]["effective"] == reopened["before"]["activating"] == held["effective"]
        assert reopened["before"]["requested"] == held["requested"]
        assert reopened["before"]["admission_open"] is False
        assert reopened["effective"] == healthy["effective"]
        assert reopened["requested"] == reopened["failed"] == held["requested"]
        assert reopened["failure_code"] == "activation_interrupted"
        assert reopened["admission_open"] is True and reopened["activating"] is None
        assert reopened["grant_epoch"] == 1 and reopened["revoked"] == ["tools"]
        assert reopened["registry_hash"] == healthy["registry_hash"]
        assert reopened["launch_hash"] == healthy["launch_hash"]
        assert reopened["issuer_generation"] != healthy["issuer_generation"]
        assert reopened["predecessor_kind"] == "settled_predecessor"
        assert reopened["predecessor_generation"] == healthy["issuer_generation"]
        assert len(reopened["predecessor_receipt"]) == 64
        assert len({healthy["native"]["generation"], held["native"]["generation"],
                    reopened["native"]["generation"]}) == 3
        assert reopened["catalogue_requests"] == 0
        for observation in (healthy, held, reopened):
            assert observation["pinned_count"] == observation["domain_active"] == 0
            assert observation["active_sessions"] == []
            assert observation["provider_completions"] == []
            assert observation["model_registry_installed"] is False
        assert reopened["ordinary_callback_count"] == 1
        assert reopened["services_shutdown"] == reopened["native_settlement"] == "settled"
        (tmp_path / "observations.json").write_text(json.dumps({"healthy": healthy,
            "held": held, "reopened": reopened, "issuer_exit_observed": True,
            "native_job_exit_observed": True, "owned_pipe_eof_observed": True}, indent=2), encoding="utf-8")
    finally:
        for handle in native_handles:
            try:
                if handle.wait(5000) == 258:
                    handle.terminate()  # Failure cleanup of our independently retained native child only.
                    assert handle.wait(5000) == 0
            finally:
                handle.close()


def public_state(authority):
    snapshot = authority.activation_snapshot()
    return {**{key: snapshot[key] for key in ("effective", "requested", "activating", "failed",
        "failure_code", "admission_open", "grant_epoch", "revoked")},
        "pinned_count": len(snapshot["pinned_runs"])}


async def child_main(phase, root):
    import httpx
    from renulus.runtime.harness_configuration import (AttemptPolicy, Candidate, ChildPolicy, ContextPolicy, RolePolicy)
    from renulus.runtime.harness_configuration_controller import NewRunSeal, RegistryHealth
    from renulus.runtime.harness_launch import FrozenLaunchInputs, finish_spec
    from renulus.runtime.harness_process import ManagedHarnessProcess
    from renulus.runtime.harness_profile_owner import ProfileOwnerScope
    from renulus.runtime.harness_startup import HarnessStartupOptions, create_managed_app
    from test_harness_learning_models import command, process_config
    from test_harness_managed_startup import SYNTHETIC_ACCOUNT_KEY

    assert phase in {"crash", "reopen"}
    loop = asyncio.get_running_loop()
    catalogue_requests, ordinary, before = [], [], {}
    boot = {"ipc": {"max_inflight": 1, "max_domain_inflight": 1, "max_frame_bytes": 65536}}
    config = replace(process_config(root, "synthetic-interrupted-startup"), boot_settings={})
    scope = ProfileOwnerScope(root, config.profile_id, config.domain_store_id, config.store_id)
    candidates = root.parent / "candidates"
    options = HarnessStartupOptions(scope, config, root.parent / "artifacts", candidates,
        30, initialize_new=phase == "crash")

    def catalogue(request):
        assert request.method == "GET" and request.url.path.endswith("/models")
        catalogue_requests.append(request.url.path)
        return httpx.Response(200, json={"data": [{"id": "mimo-v2.6-pro"}]})

    async def prepare(app, lease, authority, store):
        assert asyncio.get_running_loop() is loop
        lease.require_predecessor(lease.predecessor)
        provider = app.state.services.get("provider")
        assert provider.paths is app.state.services.paths and authority.db is app.state.services.db
        before.update(public_state(authority))
        if phase == "reopen":
            assert provider.configuration_connection() is not None
            assert before["effective"] == before["requested"] == before["activating"]
            assert before["admission_open"] is False
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
        store.save(inputs)
        assert store.load(inputs.sha256) == inputs
        return finish_spec(inputs, inspection["registry_hash"])

    app = create_managed_app(options, source_root=SOURCE, prepare_startup=prepare,
        provider_http_transport=httpx.MockTransport(catalogue))
    services, authority = app.state.services, app.state.harness_configuration_authority
    provider = services.get("provider")
    lease = app.state.harness_bootstrap.profile_owner

    async def observe():
        owner = services.get("harness_learning")
        snapshot = public_state(authority)
        spec = authority.configuration(snapshot["effective"])
        assert owner.configuration_authority is authority and owner.configuration_id == snapshot["effective"]
        assert services.get("provider") is provider
        assert provider.configuration_connection() == spec.connection
        identity = owner.process.native_identity()
        registered = lease.register_native(identity.pid, generation=identity.generation)
        status = await command(owner.process, "host.status")
        assert status["state"] == "ready" and status["configurationId"] == snapshot["effective"]
        launch = [item.sha256 for item in spec.inputs if item.kind == "artifact" and item.name == "launch"]
        assert len(launch) == 1
        return {**snapshot, "issuer_generation": lease.generation, "python_identity": asdict(lease.python_identity),
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
    async with app.router.lifespan_context(app):
        assert len(ordinary) == 1
        if phase == "crash":
            print(json.dumps({"phase": "healthy", **await observe()}), flush=True)
            assert await asyncio.to_thread(sys.stdin.readline) == "activate\n"
            assert authority.revoke("tools") == 1
            controller = services.get("harness_configuration_controller")
            assert controller.authority is authority and controller.provider is provider
            staged = await controller.stage_roles((RolePolicy(purpose="explain", model_id="mimo-v2.6-pro",
                output_tokens=64, dispatch_limit=1),))
            old_process = services.get("harness_learning").process
            real_start_gated = controller.lifecycle.start_gated
            hold = asyncio.Event()

            async def hold_after_live_registry(candidate: Candidate, *, seal: NewRunSeal) -> RegistryHealth:
                health = await real_start_gated(candidate, seal=seal)
                assert isinstance(health, RegistryHealth) and health.healthy
                snapshot = authority.activation_snapshot()
                assert snapshot["effective"] == snapshot["requested"] == snapshot["activating"] == candidate.version
                assert snapshot["admission_open"] is False
                assert health.configuration_version == candidate.version and health.grant_epoch == snapshot["grant_epoch"]
                assert health.registry_hash == candidate.spec.registry_hash
                print(json.dumps({"phase": "selected_before_admission", **await observe(),
                    "old_native_settlement": (await old_process.settlement(0))["state"],
                    "old_domain_active": old_process.domain_status()["active"]}), flush=True)
                await hold.wait()  # The external retained issuer handle ends this lifetime.
                return health

            controller.lifecycle.start_gated = hold_after_live_registry
            await controller.activate(staged["version"])
            raise AssertionError("The held activation must not reach admission")
        lease.require_predecessor(lease.predecessor)
        result = {"phase": "reopened", **await observe(), "before": before,
            "predecessor_kind": lease.predecessor.kind,
            "predecessor_generation": lease.predecessor.previous_generation,
            "predecessor_receipt": lease.predecessor.receipt_sha256}
        owner = services.get("harness_learning")
    result.update(services_shutdown=services.shutdown_status()["state"],
        native_settlement=(await owner.process.settlement(0))["state"],
        domain_active=owner.process.domain_status()["active"])
    return result


if __name__ == "__main__":
    print(json.dumps({"actual_pid": os.getpid()}), flush=True)
    try:
        print(json.dumps(asyncio.run(child_main(sys.argv[1], Path(sys.argv[2])))), flush=True)
    except BaseException as error:
        print(json.dumps({"failure": type(error).__name__, "code": getattr(error, "code", None)}), flush=True)
        raise
