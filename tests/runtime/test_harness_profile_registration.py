"""Real process-fence assembly in dedicated synthetic Python children only."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading

import pytest

from test_harness_profile_owner import ObservedChild


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows profile fence")
SOURCE = Path(__file__).resolve().parents[2]
NODE = Path(os.environ.get("RENULUS_HARNESS_NODE",
    "C:/Renulus/scratch/ocf/tools/node-v26.4.0-win-x64/node.exe"))

CHILD = r'''
import asyncio, json, os, pathlib, sys
print(json.dumps({"actual_pid": os.getpid()}), flush=True)
boot = json.loads(sys.stdin.readline())
sys.path.insert(0, str(pathlib.Path(boot["source"]) / "runtime"))
from renulus.runtime.harness_profile_owner import ProfileOwnerScope, acquire_profile_owner
root = pathlib.Path(boot["root"])
scope = ProfileOwnerScope(root, "synthetic-registration", "synthetic-domain", "synthetic-runtime")
stage = "acquire"
try:
    lease = acquire_profile_owner(scope, initialize_new=True)
    stage = "assemble"
    from renulus.server import create_app
    from renulus.runtime.harness_learning import HarnessLearningOwner
    from renulus.runtime.harness_process import HarnessProcessConfig
    services = create_app(root, source_root=boot["source"]).state.services
    config = HarnessProcessConfig(node_executable=pathlib.Path(boot["node"]),
        host_entry=pathlib.Path(boot["source"]) / "packages/harness/src/main.mjs",
        profile_root=root, profile_id=scope.profile_id, store_id=scope.runtime_store_id,
        domain_store_id=scope.domain_store_id, domain_path="state/renulus.sqlite3",
        start_timeout=30)
    owner = None
    async def run():
        global owner, stage
        try:
            stage = "owner"
            owner = HarnessLearningOwner(services, config, configuration_id="a" * 64,
                profile_owner=lease)
            await owner.start()
            identity = owner.process.native_identity()
            receipt = json.loads((root / ".renulus-profile-owner.json").read_text())
            response = await owner.process.request("host.status", {}, "registration-check", "1", 5)
            registered = receipt["native_count"] == 1 and receipt["native"][0]["generation"] == identity.generation
            registered = registered and receipt["native"][0]["process"]["pid"] == identity.pid
            result = {"registered": registered, "native_pid": identity.pid,
                "profile_id": identity.profile_id, "store_id": identity.store_id,
                "outcome": response["outcome"], "native_count": receipt["native_count"]}
            if boot["mode"] == "restart":
                from renulus.runtime.harness_configuration import Candidate, ConfigurationSpec, ConnectionReference
                from renulus.runtime.harness_configuration_lifecycle import ManagedConfigurationLifecycle
                lifecycle = ManagedConfigurationLifecycle(owner, candidate_root=root.parent / "candidates")
                candidate_spec = ConfigurationSpec(connection=ConnectionReference(provider="opencode-go",
                    credential_reference="synthetic-reference", credential_revision=0), registry_hash="c" * 64)
                candidate = Candidate("b" * 64, candidate_spec, 0)
                try:
                    health = await lifecycle.inspect_candidate(candidate)
                    candidate = Candidate(candidate.version, candidate_spec.model_copy(update={
                        "registry_hash": health.registry_hash}), 0)
                    after_inspection = json.loads((root / ".renulus-profile-owner.json").read_text())
                    seal = await lifecycle.seal_new_runs(expected_effective=owner.configuration_id)
                    boundary = await lifecycle.stop_and_settle(seal)
                    final = await lifecycle.start_gated(candidate, seal=seal)
                    after_restart = json.loads((root / ".renulus-profile-owner.json").read_text())
                    result.update(candidate_count=after_inspection["native_count"],
                        replacement_count=after_restart["native_count"],
                        distinct_generations=len({item["generation"] for item in after_restart["native"]}),
                        registry_matches=health.registry_hash == final.registry_hash,
                        old_stopped=boundary.runtime_stopped and boundary.domain_settled)
                    seal.release()
                finally:
                    await lifecycle.close()
            await owner.close()
            result["settlement"] = (await owner.process.settlement(5))["state"]
            return result
        finally:
            if owner is not None:
                await owner.close()
            services.get("helpers").startup.close()
    print(json.dumps(asyncio.run(run())), flush=True)
except Exception as error:
    print(json.dumps({"error": getattr(error, "code", type(error).__name__),
        "stage": stage}), flush=True)
'''


def registration_result(tmp_path, *, mode):
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment["PATH"] = str(NODE.parent)
    home = tmp_path / "synthetic-home"
    home.mkdir()
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
        environment[key] = str(home)
    process = subprocess.Popen([sys.executable, "-B", "-u", "-c", CHILD],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
    messages = queue.Queue()

    def read():
        for line in process.stdout:
            messages.put(line)
        messages.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    actual = None
    try:
        started = json.loads(messages.get(timeout=10))
        actual = ObservedChild(started["actual_pid"])
        process.stdin.write(json.dumps({"root": str(tmp_path / "profile"),
            "source": str(SOURCE), "node": str(NODE), "mode": mode}) + "\n")
        process.stdin.flush()
        response = json.loads(messages.get(timeout=100))
        return started, response
    finally:
        if actual is not None:
            if actual.wait(10000) != 0:
                actual.terminate()
                assert actual.wait(5000) == 0
            actual.close()
        elif process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        process.stdin.close()
        process.stdout.close()
        reader.join(timeout=2)


def test_saved_owner_registers_actual_native_process_before_activation(tmp_path):
    started, response = registration_result(tmp_path, mode="initial")
    assert response.get("registered") is True, response
    assert response["profile_id"] == "synthetic-registration"
    assert response["store_id"] == "synthetic-runtime"
    assert response["outcome"] == "committed_reference"
    assert response["settlement"] == "settled"
    assert response["native_count"] == 1
    assert response["native_pid"] != started["actual_pid"]


def test_configuration_candidate_and_replacement_are_registered_under_same_profile_job(tmp_path):
    _, response = registration_result(tmp_path, mode="restart")
    assert response.get("registered") is True, response
    assert response["candidate_count"] == 2
    assert response["replacement_count"] == 3
    assert response["distinct_generations"] == 3
    assert response["registry_matches"] is True
    assert response["old_stopped"] is True
    assert response["settlement"] == "settled"
