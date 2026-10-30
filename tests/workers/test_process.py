import base64
import hashlib
import json

import pytest

from renulus.worker_contracts import Capacity, payload_digest
from .support import Process, TOKEN, command, config, grant


def test_real_stdio_handshake_chunked_transfer_and_closed_union(tmp_path):
    body = b"Synthetic transplant rejection and AKI teaching note.\n" * 24000
    with Process(tmp_path / "process") as worker:
        ready = worker.start()
        assert ready["protocol"] == "renulus-worker/1"
        assert "memory.extract" in ready["supported_commands"]
        g = worker.upload(body)
        assert worker.read_all(g) == body
        reply = worker.request(command("transport.send", {}))
        assert reply["outcome"] == "rejected_before_admission"
        assert reply["result"]["code"] == "unsupported_command"
        reply = worker.request(command("worker.settle", {"action":"query"}))
        assert reply["result"]["active"] == 0
        assert TOKEN not in json.dumps(ready)
    assert worker.process.returncode == 0
    assert not list(tmp_path.rglob("*.sqlite*"))


@pytest.mark.parametrize("change,code", [
    ({"process_generation":"old_generation"}, "stale_identity"),
    ({"domain_store_id":"old_domain"}, "stale_identity"),
    ({"authority_epoch":3}, "stale_identity"),
    ({"grant_revision":11}, "stale_revision"),
    ({"cancellation_epoch":1}, "stale_revision"),
    ({"retention":"temporary"}, "stale_identity"),
    ({"payload_sha256":"0" * 64}, "digest_mismatch"),
])
def test_identity_epochs_and_digest_refuse_before_effects(tmp_path, change, code):
    with Process(tmp_path / "process") as worker:
        worker.start()
        reply = worker.request(command("worker.settle", {"action":"query"}, **change))
        assert reply["outcome"] == "rejected_before_admission"
        assert reply["result"]["code"] == code


@pytest.mark.parametrize("kind", ["token", "version", "oversized", "unknown", "duplicate", "nonfinite"])
def test_malformed_or_unauthenticated_process_fails_closed_without_payload_logs(tmp_path, kind):
    with Process(tmp_path / "process") as worker:
        if kind in ("token", "version"):
            hello = dict(worker.hello)
            hello["launch_token" if kind == "token" else "protocol"] = "x" * 40
            worker.send(hello)
        else:
            worker.start()
            if kind == "oversized":
                data = b"x" * (1024 * 1024 + 1) + b"\n"
            elif kind == "duplicate":
                data = b'{"kind":"command","kind":"hello"}\n'
            elif kind == "nonfinite":
                data = b'{"sentinel":NaN}\n'
            else:
                data = b'{"unknown":"synthetic private sentinel"}\n'
            try:
                worker.process.stdin.write(data)
                worker.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
        worker.process.wait(timeout=10)
    assert worker.process.returncode == 2


def test_negotiated_bounds_and_artifact_rights_hash_offset_expiry(tmp_path):
    capacity = Capacity(max_frame_bytes=32768, max_chunk_bytes=8192, artifact_bytes=10000)
    with Process(tmp_path / "process", capacity=capacity) as worker:
        ready = worker.start()
        assert ready["capacity"]["max_chunk_bytes"] == 8192
        body = b"synthetic"
        g = grant(body, rights=["extract"])
        reply = worker.request(command("artifact.upload", {"artifact":g,"offset":1,
            "data_base64":base64.b64encode(body).decode(),"final":True}))
        assert reply["result"]["code"] == "artifact_invalid"
        g["artifact_sha256"] = "0"*64
        reply = worker.request(command("artifact.upload", {"artifact":g,"offset":0,
            "data_base64":base64.b64encode(body).decode(),"final":True}))
        assert reply["result"]["code"] == "digest_mismatch"
        g = worker.upload(body, rights=["extract"])
        reply = worker.request(command("artifact.read", {"artifact_handle":g["artifact_handle"],
                "artifact_revision":1,"offset":0,"length":8192}))
        assert reply["result"]["code"] == "artifact_denied"


def test_revocation_drops_artifacts_and_stale_requests_cannot_reuse_handles(tmp_path):
    with Process(tmp_path / "process") as worker:
        worker.start()
        g = worker.upload(b"synthetic")
        from .support import REVISIONS
        revisions = REVISIONS.model_copy(update={"deletion":7})
        reply = worker.request(command("worker.settle", {"action":"revoke","revisions":revisions.model_dump()}))
        assert reply["settlement"]["state"] == "settled"
        read = {"artifact_handle":g["artifact_handle"],"artifact_revision":1,"offset":0,"length":10}
        reply = worker.request(command("artifact.read", read))
        assert reply["result"]["code"] == "stale_revision"
        reply = worker.request(command("artifact.read", read, revisions=revisions))
        assert reply["result"]["code"] == "artifact_denied"


def test_real_handshake_refuses_unrelated_launcher_and_proves_current_creation_times(tmp_path):
    with Process(tmp_path / "refused") as worker:
        worker.hello["expected_launcher_pid"] = 4294967295
        worker.send(worker.hello)
        worker.process.wait(timeout=10)
    assert worker.process.returncode == 2
    with Process(tmp_path / "accepted") as worker:
        ready = worker.start()
        proof = ready["process"]
        assert proof["launcher_pid"] == worker.process.pid
        assert proof["actual_pid"] == ready["pid"]
        assert int(proof["actual_creation_filetime"]) >= int(proof["launcher_creation_filetime"])
        assert proof["ancestry_depth"] >= 1  # The pinned Windows venv redirector.


def test_data_lifetime_budget_does_not_exhaust_control_or_rebind_released_handle(tmp_path):
    launch = config(capacity=Capacity(request_count=2))
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        g = worker.upload(b"synthetic")
        release = command("worker.settle", {"action":"release","artifact_handle":g["artifact_handle"]})
        assert worker.request(release)["settlement"]["state"] == "settled"
        v = command("artifact.upload", {"artifact":g,"offset":0,
                "data_base64":base64.b64encode(b"synthetic").decode(),"final":True})
        assert worker.request(v)["result"]["code"] == "artifact_invalid"
        assert worker.request(command("transport.send", {}))["result"]["code"] == "overloaded"
        assert worker.request(command("worker.settle", {"action":"query"}))["result"]["active"] == 0
        assert worker.request(command("worker.settle", {"action":"close"}))["result"]["closing"] is True
