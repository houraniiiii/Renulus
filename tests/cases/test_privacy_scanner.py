"""Windows index leases must not prevent or weaken synthetic privacy scans."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest
from qdrant_client import QdrantClient

from renulus.contracts import ContextScope, Scope
from renulus.memory.models import ManualFact
from renulus.server import create_app

from .conftest import SENTINEL, assert_absent_from_profile


@pytest.fixture
def leased_profile(tmp_path, monkeypatch):
    app = create_app(tmp_path / "lease-proof")
    services = app.state.services
    memory = services.registry["memory"]
    config = {"fingerprint": "synthetic-scanner-embedding"}

    class LeasedIndex:
        """Real Qdrant file lease; controlled recall, without model inference."""
        def __init__(self, services, path, embedding):
            self.path = path
            self.client = QdrantClient(path=str(path / "qdrant"))
            self.records = []

        def add(self, row):
            self.records.append(row)
            (self.path / "records.json").write_text(json.dumps(self.records), encoding="utf-8")
            return row["id"]

        def search(self, query, limit):
            return [{"id": row["id"]} for row in self.records[:limit]]

        def purge_history(self):
            pass

        def close(self):
            self.client.close()

    memory.index_factory = LeasedIndex
    monkeypatch.setattr(memory, "_get_embedding", lambda: SimpleNamespace(config=config))
    monkeypatch.setattr("renulus.memory.service.embedding_config", lambda services: config)
    note = memory.add(ManualFact(text="Synthetic general learning preference",
        scope=ContextScope(kind=Scope.STUDY), idempotency_key="scanner-note"))
    assert memory.reindex()["count"] == 1
    try:
        yield app, services, memory, note
    finally:
        asyncio.run(memory.close())


def test_privacy_scan_releases_index_retains_case_and_allows_lazy_recall(leased_profile):
    app, services, memory, note = leased_profile
    controller = services.registry["cases"]
    index = memory._engine
    with TestClient(app) as client:
        case = client.post("/api/v1/cases/sessions", json={"text": SENTINEL}).json()
        # The lifespan's memory worker may replace the prepared empty index.
        index = memory._engine or index
        assert_absent_from_profile(services, SENTINEL)
        assert index.client._client.closed
        assert memory._engine is None
        assert services.registry["cases"] is controller
        assert client.get(f"/api/v1/cases/sessions/{case['id']}").json() == case
        assert not case["saved"]
        recalled = memory.retrieve("learning preference", scope=ContextScope(kind=Scope.STUDY))
        assert recalled["records"][0]["id"] == note["id"]
        assert memory._engine is not None
        assert_absent_from_profile(services, SENTINEL)
        assert client.get(f"/api/v1/cases/sessions/{case['id']}").json() == case


def test_privacy_scan_reads_retained_index_payload_and_lock_marker(leased_profile):
    _, services, memory, _ = leased_profile
    index = memory._engine
    marker = (index.path / "qdrant/.lock").stat().st_size
    assert marker == len(b"tmp lock file")
    with pytest.raises(AssertionError, match="Synthetic content leaked into .lock"):
        assert_absent_from_profile(services, "tmp lock file")
    assert index.client._client.closed
    assert index.path.is_dir()
    (index.path / "records.json").write_text(SENTINEL, encoding="utf-8")
    with pytest.raises(AssertionError, match="Synthetic content leaked into records.json"):
        assert_absent_from_profile(services, SENTINEL)


def test_privacy_scan_propagates_unrelated_read_errors(leased_profile, monkeypatch):
    _, services, _, _ = leased_profile
    unreadable = services.paths.cache / "unreadable.bin"
    unreadable.write_bytes(b"SYNTHETIC")
    original = Path.read_bytes
    def checked(path):
        if path == unreadable:
            raise PermissionError(13, "synthetic unrelated read failure")
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", checked)
    with pytest.raises(PermissionError, match="synthetic unrelated read failure"):
        assert_absent_from_profile(services, SENTINEL)
