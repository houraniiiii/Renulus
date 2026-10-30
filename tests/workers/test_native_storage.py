# SPDX-License-Identifier: MIT
import pytest

from renulus.storage import filesystem as fs
from renulus.workers.native_storage import FREE_FLOOR, NativeStorage


def test_low_space_preserves_reservations_and_settlement_charges_cleanup_debt(tmp_path, monkeypatch):
    storage = NativeStorage([tmp_path], tmp_path)
    monkeypatch.setattr(fs, "available_bytes", lambda _: FREE_FLOOR + 1000)
    storage.reserve("first", "intent-first", 100)
    before = storage.status()
    monkeypatch.setattr(fs, "available_bytes", lambda _: FREE_FLOOR + 150)
    with pytest.raises(ValueError, match="^storage_waiting_space$"):
        storage.reserve("second", "intent-second", 100)
    assert storage.status() == before
    assert storage.settle("first", "intent-first", settled=False) == before
    assert storage.settle("first", "intent-first", cleanup_debt_bytes=125) == {
        "reserved_bytes": 0, "cleanup_debt_bytes": 125, "reservations": 0}
    with pytest.raises(ValueError, match="^storage_waiting_space$"):
        storage.reserve("third", "intent-third", 100)
    assert storage.status()["cleanup_debt_bytes"] == 125


def _owned_io(tmp_path):
    from pydantic import TypeAdapter
    from renulus.workers.knowledge_io import KnowledgeIO
    from renulus.workers.native_contracts import NativeInput, NativePaths
    root = tmp_path / "managed"
    (root / "generations/g1").mkdir(parents=True)
    (root / "generations/g2").mkdir()
    (root / "generations/g2/member.bin").write_bytes(b"x" * 5000)
    (root / ".renulus-backend-selector.json").write_text('{"generationPath":"generations/g1"}')
    (tmp_path / "grants").mkdir()
    config = NativePaths(originals_root=str(root / "originals"), budget_root=str(root), grants_root=str(tmp_path / "grants"),
                         grant_token_sha256="0" * 64)
    out = dict(artifact_handle="output_synthetic", artifact_revision=1, max_bytes=1024, expires_at_ms=9007199254740991,
               reservation_id="output_reservation", intent_id="output_intent")
    return KnowledgeIO(config), lambda action, **v: TypeAdapter(NativeInput).validate_python(dict(action=action, output=out, **v))


def test_native_measure_reports_budget_without_a_path(tmp_path):
    from threading import RLock
    io, op = _owned_io(tmp_path)
    try:
        value = io.execute(op("measure"), None, lambda: True, RLock())
        assert value["allocated_bytes"] >= 5000 and value["ceiling_bytes"] == 100_000_000_000
        assert value["reserved_bytes"] == 0 and value["cleanup_debt_bytes"] == 0 and value["free_bytes"] > 0
    finally:
        io.close()


def test_native_retire_retains_discarded_candidate_as_debt_and_refuses_current_or_unknown(tmp_path):
    from threading import RLock
    from renulus.workers.artifacts import Refused
    io, op = _owned_io(tmp_path)
    try:
        first = io.execute(op("retire", candidate_id="g2"), None, lambda: True, RLock())
        assert first["result"] == "retained_as_debt" and first["debt_bytes"] >= 5000
        assert io.execute(op("retire", candidate_id="g2"), None, lambda: True, RLock()) == first
        assert (tmp_path / "managed/generations/g2/member.bin").exists()
        for candidate in ("g1", "g9"):
            with pytest.raises(Refused) as error:
                io.execute(op("retire", candidate_id=candidate), None, lambda: True, RLock())
            assert error.value.code == "invalid_command"
        assert io.execute(op("measure"), None, lambda: True, RLock())["cleanup_debt_bytes"] == first["debt_bytes"]
    finally:
        io.close()
