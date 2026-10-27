"""Selected-engine proofs, with synthetic data and no inference transport."""
import hashlib
import json
import os
from pathlib import Path
import time

import pytest

from renulus.worker_contracts import DerivedPaths, HelperPaths
from .support import Process, ROOT, command, config, output, target, REVISIONS


@pytest.fixture
def launch(tmp_path):
    helpers = os.environ.get("RENULUS_WORKER_TEST_HELPERS")
    if not helpers:
        pytest.skip("Explicit pre-provisioned public helpers required")
    return config(helpers=HelperPaths(helpers_root=str(Path(helpers)),
        cache_root=str(tmp_path / "cache"), source_root=str(ROOT)),
        derived=DerivedPaths(root=str(tmp_path / "derived"), namespace="synthetic",
            library_tombstones=[], memory_tombstones=[]))


def staged(worker, name, body, **fields):
    g = worker.upload(body)
    return command(name, dict(artifact_handle=g["artifact_handle"], artifact_revision=1,
        offset=0, length=len(body), output=output(), **fields), retention=worker.launch.retention)


def result(worker, value):
    reply = worker.request(value, timeout=120)
    assert reply["outcome"] == "committed_reference", reply
    return json.loads(worker.read_all(reply["result"]))


def library_stage(worker, revision="revision_aki", text="AKI requires evaluation of volume status."):
    return staged(worker, "library.stage", json.dumps({"passages": [
        {"passage_id": "passage_" + revision, "text": text}]}).encode(),
        revision_id=revision, document_id="document_synthetic")


def query(worker, revisions):
    return command("library.query", dict(query="AKI volume", allowed_revision_ids=revisions,
        limit=10, output=output()))


def test_real_lance_prefilter_immutable_stage_remove_maintenance_and_reopen(tmp_path, launch):
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        stage = result(worker, library_stage(worker))
        assert stage["eligible"] is False
        result(worker, library_stage(worker))  # Idempotent, no duplicate append.
        result(worker, library_stage(worker, "revision_transplant", "Transplant rejection biopsy assessment."))
        assert result(worker, query(worker, []))["rows"] == []
        rows = result(worker, query(worker, ["revision_aki"]))["rows"]
        assert len(rows) == 1 and rows[0]["revision_id"] == "revision_aki"
        conflict = worker.request(library_stage(worker, text="A changed immutable revision."))
        assert conflict["result"]["code"] == "stale_revision"
        too_long = worker.request(library_stage(worker, "revision_long", "dialysis " * 600))
        assert too_long["result"]["code"] == "artifact_limit"
        removed = result(worker, command("library.remove", dict(revision_ids=["revision_aki"], output=output())))
        assert removed["tombstones_applied"]
        assert result(worker, query(worker, ["revision_aki"]))["rows"] == []
        assert worker.request(library_stage(worker))["result"]["code"] == "stale_revision"
        result(worker, command("library.maintain", dict(revision_ids=[], optimize=True, output=output())))
    # Tombstones from canonical host input apply before any derived readiness.
    launch = launch.model_copy(update={"derived": launch.derived.model_copy(update={
        "library_tombstones": ["revision_transplant"]})})
    with Process(tmp_path / "reopen", launch=launch) as worker:
        worker.start()
        assert result(worker, query(worker, ["revision_transplant"]))["rows"] == []


def record(cid="fact_aki", revision=1, text="AKI study should review volume status."):
    return dict(id=cid, revision=revision, text=text, scope="study", kind="learning-point", topic_id="aki")


def reconcile(worker, records):
    return staged(worker, "memory.reconcile", json.dumps({"records": records}).encode())


def recall(worker, accepted):
    return command("memory.recall", dict(query="AKI volume status", accepted=accepted, limit=10, output=output()))


def test_real_mem0_hermes_qdrant_reconcile_recall_correction_purge_tombstones(tmp_path, launch):
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        indexed = result(worker, reconcile(worker, [record(), record("fact_ckd", text="CKD albuminuria study.")]))
        refs = indexed["references"]
        assert indexed["eligible"] is False
        replay = result(worker, reconcile(worker, [record()]))
        assert replay["references"] == refs[:1]
        changed = record()
        changed["kind"] = "goal"
        assert worker.request(reconcile(worker, [changed]))["result"]["code"] == "stale_revision"
        assert result(worker, recall(worker, []))["rows"] == []
        rows = result(worker, recall(worker, refs[:1]))["rows"]
        assert len(rows) == 1 and rows[0]["canonical_id"] == "fact_aki"
        # A fabricated canonical revision or engine ID is never accepted.
        wrong = [{**refs[0], "canonical_revision": 2}]
        assert result(worker, recall(worker, wrong))["rows"] == []
        wrong = [{**refs[0], "engine_id": "engine_not_accepted"}]
        assert result(worker, recall(worker, wrong))["rows"] == []
        corrected = result(worker, reconcile(worker, [record(revision=2, text="AKI study revisits volume assessment.")]))
        # Staging preserves the previous usable generation; the host now supplies
        # only revision 2 in its current accepted mapping.
        assert result(worker, recall(worker, corrected["references"]))["rows"][0]["canonical_revision"] == 2
        purged = result(worker, command("memory.purge", dict(canonical_ids=["fact_aki"], output=output())))
        assert purged["removed"] == 2 and purged["tombstones_applied"]
        assert result(worker, recall(worker, corrected["references"]))["rows"] == []
        assert worker.request(reconcile(worker, [record()]))["result"]["code"] == "stale_revision"
    launch = launch.model_copy(update={"derived": launch.derived.model_copy(update={
        "memory_tombstones": ["fact_ckd"]})})
    with Process(tmp_path / "reopen", launch=launch) as worker:
        worker.start()
        assert result(worker, recall(worker, refs))["rows"] == []


def capture(worker):
    body = b"Synthetic educational learning: AKI volume assessment and transplant rejection biopsy."
    plan = dict(plan_id="plan_synthetic", evidence_receipt="receipt_synthetic", support_sha256="a" * 64,
        source_sha256=hashlib.sha256(body).hexdigest(), expires_at_ms=int(time.time() * 1000) + 60000, max_calls=1)
    return staged(worker, "memory.extract", body, capture_plan=plan)


def receive_callback(worker, value):
    worker.send(value)
    pending = callback = None
    while callback is None:
        frame = worker.receive(timeout=120)
        if frame["kind"] == "generation_request":
            callback = frame
        else:
            assert frame["outcome"] == "accepted_pending", frame
            pending = frame
    assert pending is not None
    return pending, callback


def generation(callback, *, status="completed", revisions=REVISIONS, wrong=False):
    return command("worker.settle", dict(action="generation", target=callback["target"],
        generation=dict(callback_id=callback["callback_id"], plan_id=callback["capture_plan"]["plan_id"],
            generation_sha256="0" * 64 if wrong else callback["generation_sha256"], status=status,
            # This deterministic response is an INFERENCE FIXTURE, never a product fallback.
            output=json.dumps({"memory": [{"text": "Review volume status when studying AKI."},
                {"text": "Study biopsy findings in transplant rejection."}]}) if status == "completed" else None)),
        revisions=revisions, retention=callback["retention"])


def test_real_mem0_extraction_reverse_stdio_binding_and_disposable_graph(tmp_path, launch):
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        value = capture(worker)
        pending, callback = receive_callback(worker, value)
        assert callback["target"] == target(pending)
        assert callback["action"] == "generate"
        assert "Synthetic educational learning" in str(callback["messages"])
        invalid = worker.request(generation(callback, wrong=True))
        assert invalid["result"]["code"] == "stale_target"
        worker.send(generation(callback))
        while True:
            reply = worker.receive(timeout=120)
            if reply["identity"]["request_id"] == value["request_id"]:
                break
        assert reply["outcome"] == "committed_reference", reply
        extracted = json.loads(worker.read_all(reply["result"]))
        assert len(extracted["facts"]) == 2 and extracted["eligible"] is False
        assert extracted["capture_plan"] == value["input"]["capture_plan"]
        assert worker.request(generation(callback))["result"]["code"] == "stale_target"
    assert not (Path(launch.derived.root) / "synthetic/indexes/learner-memory/capture").exists()
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"Synthetic educational learning" not in path.read_bytes(), path


@pytest.mark.parametrize("mode", ["cancel", "revoke", "deadline"])
def test_reverse_cancel_or_revoke_holds_memory_lane_until_generation_settlement(tmp_path, launch, mode):
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        first = capture(worker)
        if mode == "deadline":
            first["limits"]["cpu_seconds"] = 2
        pending, callback = receive_callback(worker, first)
        rev = REVISIONS.model_copy(update={"deletion": 7}) if mode == "revoke" else REVISIONS
        control = command("worker.settle", dict(action="revoke", revisions=rev.model_dump()) if mode == "revoke"
            else dict(action="cancel", target=target(pending)))
        if mode != "deadline":
            worker.send(control)
        ack, cancelled = (True if mode == "deadline" else None), None
        while ack is None or cancelled is None:
            frame = worker.receive()
            if frame["kind"] == "generation_request":
                cancelled = frame
            else:
                ack = frame
        if mode != "deadline":
            assert ack["settlement"]["state"] == "pending"
        assert cancelled["action"] == "cancel" and cancelled["messages"] == []
        assert cancelled["callback_id"] == callback["callback_id"]
        query = worker.request(command("worker.settle", dict(action="query", target=target(pending)), revisions=rev), terminal=False)
        assert query["settlement"]["state"] == "pending"
        worker.send(generation(callback, status="cancelled", revisions=rev))
        while True:
            terminal = worker.receive(timeout=120)
            if terminal["identity"]["request_id"] == first["request_id"]:
                break
        assert terminal["outcome"] == "cancelled_settled"
        assert terminal["settlement"]["worker_lease"] == pending["settlement"]["worker_lease"]
        assert terminal["revisions"] == REVISIONS.model_dump()


def test_host_eof_during_generation_remains_uncertain(tmp_path, launch):
    worker = Process(tmp_path / "process", launch=launch)
    try:
        worker.start()
        value = capture(worker)
        pending, _ = receive_callback(worker, value)
    finally:
        worker.close()
    terminal = worker.receive()
    assert terminal["outcome"] == "uncertain_after_disconnect"
    assert terminal["settlement"] == {"worker_lease": pending["settlement"]["worker_lease"], "state": "uncertain"}


def test_temporary_mem0_capture_is_ram_only_and_lance_is_refused(tmp_path, launch):
    launch = launch.model_copy(update={"retention": "temporary"})
    with Process(tmp_path / "process", launch=launch) as worker:
        worker.start()
        value = capture(worker)
        _, callback = receive_callback(worker, value)
        worker.send(generation(callback))
        while True:
            reply = worker.receive(timeout=120)
            if reply["identity"]["request_id"] == value["request_id"]:
                break
        assert reply["outcome"] == "committed_reference", reply
        assert len(json.loads(worker.read_all(reply["result"]))["facts"]) == 2
        denied = worker.request(command("library.query", dict(query="AKI", allowed_revision_ids=[],
            limit=1, output=output()), retention="temporary"))
        assert denied["result"]["code"] == "artifact_denied"
    assert not Path(launch.derived.root).exists()
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"Synthetic educational learning" not in path.read_bytes(), path


def test_exact_native_namespace_owners_exclude_a_second_process(tmp_path, launch):
    from renulus.knowledge.ownership import NativeOwnership
    base = Path(launch.derived.root) / launch.derived.namespace
    library = base / "library"
    memory = base / "indexes/learner-memory/facts"
    library_owner = NativeOwnership(library.parent / "library.native-owner")
    memory_owner = NativeOwnership(memory.parent / "facts.native-owner")
    library_owner.acquire_for_path(library)
    memory_owner.acquire_for_path(memory)
    try:
        with Process(tmp_path / "process", launch=launch) as worker:
            worker.start()
            denied = worker.request(library_stage(worker))
            assert denied["result"]["code"] == "engine_failed"
            denied = worker.request(recall(worker, []))
            assert denied["result"]["code"] == "engine_failed"
            library_owner.require()
            memory_owner.require()
            library_owner.close()
            memory_owner.close()
            assert result(worker, library_stage(worker))["tag"] == "library_staged"
            assert result(worker, recall(worker, []))["rows"] == []
    finally:
        library_owner.close()
        memory_owner.close()
