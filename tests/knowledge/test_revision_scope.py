# SPDX-License-Identifier: MIT
"""Actual SQLite eligibility and Lance ranking; synthetic extraction/embeddings.

These checks establish scoped Library retrieval, not embedding-model quality or
the project owner's membership/publication flow.
"""
import json

from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.server import create_app
from test_repository import STUDY, SyntheticEmbedder, SyntheticExtractor, import_note, repository


def test_revision_filter_limits_real_ranking_and_keeps_canonical_permissions(repository, monkeypatch):
    linked = import_note(repository, "SYNTHETIC dialysis linked study")
    global_note = import_note(repository, "SYNTHETIC dialysis global study")
    denied = import_note(repository, "SYNTHETIC dialysis denied study")
    reserved = import_note(repository, "SYNTHETIC dialysis reserved study", reserved=True)
    retracted = import_note(repository, "SYNTHETIC dialysis retracted study", metadata=SourceMetadata(retracted=True))
    queued = import_note(repository, "SYNTHETIC dialysis queued study", process=False)
    rights = own_text_rights().model_dump(); rights["model_input"] = False
    repository.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
        (json.dumps(rights), denied["revision_id"]))
    search = repository.index.search
    ranked_candidates = []

    def record(query, vector, revision_ids, limit):
        ranked_candidates.append(set(revision_ids))
        return search(query, vector, revision_ids, limit)

    monkeypatch.setattr(repository.index, "search", record)
    result = repository.retrieve("dialysis", scope=STUDY, revision_ids=[
        item["revision_id"] for item in (linked, denied, reserved, retracted, queued)] + ["SYNTHETIC_missing"])
    assert ranked_candidates == [{linked["revision_id"]}]
    assert [row["document_revision"] for row in result["passages"]] == [linked["revision_id"]]
    global_result = repository.retrieve("dialysis", scope=STUDY, revision_ids=None)
    assert {row["document_revision"] for row in global_result["passages"]} == {
        linked["revision_id"], global_note["revision_id"]}


def test_empty_revision_scope_returns_before_any_embedding_or_ranking(repository, monkeypatch):
    import_note(repository, "SYNTHETIC transplant global source")
    def forbidden(*args, **kwargs):
        raise AssertionError("An empty linked scope must not invoke derived engines")
    monkeypatch.setattr(repository.embedder, "embed", forbidden)
    monkeypatch.setattr(repository.index, "search", forbidden)
    result = repository.retrieve("transplant", scope=STUDY, revision_ids=[])
    assert result["status"] == "no_eligible_documents" and result["passages"] == []


def test_revision_pin_cannot_widen_during_ranking_or_accept_outside_native_hits(repository, monkeypatch):
    linked = import_note(repository, "SYNTHETIC CKD linked source")
    global_note = import_note(repository, "SYNTHETIC CKD outside source")
    pin = [linked["revision_id"]]
    search = repository.index.search

    def stale_index(query, vector, revision_ids, limit):
        assert revision_ids == [linked["revision_id"]]
        hits = search(query, vector, revision_ids, limit)
        pin.append(global_note["revision_id"])
        # Fault injection uses an actual native hit outside the captured filter.
        return hits + search(query, vector, [global_note["revision_id"]], limit)

    monkeypatch.setattr(repository.index, "search", stale_index)
    result = repository.retrieve("CKD", scope=STUDY, revision_ids=pin)
    assert [row["document_revision"] for row in result["passages"]] == [linked["revision_id"]]


def test_scoped_real_ranked_hit_is_refused_after_permission_revocation(repository, monkeypatch):
    linked = import_note(repository, "SYNTHETIC glomerular source")
    search = repository.index.search
    def revoke(query, vector, revision_ids, limit):
        hits = search(query, vector, revision_ids, limit)
        assert hits
        rights = own_text_rights().model_dump(); rights["display"] = False
        repository.db.execute("UPDATE knowledge_revisions SET rights_json=? WHERE id=?",
            (json.dumps(rights), linked["revision_id"]))
        return hits
    monkeypatch.setattr(repository.index, "search", revoke)
    assert repository.retrieve("glomerular", scope=STUDY, revision_ids=[linked["revision_id"]])["passages"] == []


def test_pinned_old_revision_does_not_follow_replacement_during_embedding(repository, monkeypatch):
    linked = import_note(repository, "SYNTHETIC transplant previous edition")
    embed = repository.embedder.embed
    replacements = []
    def replace(texts, *, query=False):
        if query:
            replacements.append(import_note(repository, "SYNTHETIC transplant replacement edition",
                document_id=linked["document_id"]))
        return embed(texts, query=query)
    monkeypatch.setattr(repository.embedder, "embed", replace)
    result = repository.retrieve("transplant", scope=STUDY, revision_ids=[linked["revision_id"]])
    assert replacements[0]["status"] == "ready"
    assert result["status"] == "no_eligible_documents" and not result["passages"]


@pytest.mark.parametrize("revision_ids", ["all", [None], [""], ["x" * 257], ["id"] * 1001])
def test_revision_scope_validation_is_bounded_and_does_not_become_global(repository, revision_ids):
    with pytest.raises(ApiError) as caught:
        repository.retrieve("SYNTHETIC", scope=STUDY, revision_ids=revision_ids)
    assert caught.value.code == "revision_scope_invalid"


def test_revision_id_length_accepts_shared_contract_boundary(repository):
    from renulus.design_c_contracts import Identity
    target = Identity(type="library_revision", id="x" * 256)
    result = repository.retrieve("SYNTHETIC", scope=STUDY, revision_ids=[target.id])
    assert result["status"] == "no_eligible_documents" and not result["passages"]


def test_actual_router_preserves_none_empty_and_explicit_revision_scope(tmp_path):
    app = create_app(tmp_path / "synthetic-revision-scope")
    library = app.state.services.get("knowledge")
    library.extractor, library.embedder = SyntheticExtractor(), SyntheticEmbedder()
    linked = import_note(library, "SYNTHETIC dialysis linked API source")
    other = import_note(library, "SYNTHETIC dialysis other API source")
    client = TestClient(app)  # No lifespan; no background ingestion/model jobs.
    query = {"query": "dialysis", "scope": {"kind": "study"}}
    try:
        empty = client.post("/api/v1/library/retrieve", json={**query, "revision_ids": []})
        assert empty.status_code == 200 and not empty.json()["passages"]
        scoped = client.post("/api/v1/library/retrieve", json={**query, "revision_ids": [linked["revision_id"]]})
        assert scoped.status_code == 200
        assert [row["document_revision"] for row in scoped.json()["passages"]] == [linked["revision_id"]]
        legacy = client.post("/api/v1/library/retrieve", json=query)
        assert {row["document_revision"] for row in legacy.json()["passages"]} == {
            linked["revision_id"], other["revision_id"]}
    finally:
        library.close()
