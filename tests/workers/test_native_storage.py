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
