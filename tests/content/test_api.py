# SPDX-License-Identifier: MIT
import json

from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app
from .helpers import PACK


@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / "isolated-profile", token="synthetic-test-token")


@pytest.fixture
def client(app):
    with TestClient(app, headers={"x-renulus-token": "synthetic-test-token"}) as client:
        yield client


def test_actual_shared_server_activates_real_original_pack(client, app):
    assert client.get("/api/v1/content/manifest").json()["version"] == "1.1.2"
    assert len(client.get("/api/v1/content/topics").json()) == 27
    assert len(client.get("/api/v1/content/cases").json()) == 38
    assert len(client.get("/api/v1/content/questions").json()) == 178
    assert len(app.state.services.registry["content"].list_questions("T06")) == 10
    assert client.get("/api/v1/content/sources/K10-2012").json()["register_id"] == "K10"
    status = client.get("/api/v1/content/bootstrap").json()
    assert status["status"] == "activated" and status["reason"] == "fresh_profile"
    assert status["active"] == {"id": "renulus-foundations", "version": "1.1.2"}


def test_http_question_catalogue_is_metadata_only(client):
    summaries = client.get("/api/v1/content/questions?topic_id=T21").json()
    assert len(summaries) == 8
    private_fields = {"stem", "answer", "options", "rationale", "explanation", "correct_option_ids"}
    assert all(not private_fields.intersection(q) for q in summaries)


@pytest.mark.parametrize("question_id", ["RN-CKD-001", "RN-TX-002", "RN-K-001", "RN11-T20-003"])
def test_raw_question_http_route_cannot_bypass_exposure_but_private_lookup_survives(client, app, question_id):
    response = client.get(f"/api/v1/content/questions/{question_id}/versions/1")
    assert response.status_code == 404
    repository = app.state.services.registry["content"]
    selected = next(q for q in repository.list_question_summaries() if q["id"] == question_id)
    private = repository.get_question_version(question_id, selected["version"])
    assert private["stem"] and private["options"]
    assert private["correct_option_ids"] == [private["answer"]]
    assert private["source_records"]


def test_routes_reject_unselected_pack_path_and_user_case_save(client, app):
    result = client.post("/api/v1/content/packs/install", json={"path": "../../outside"})
    assert result.status_code == 422 and result.json()["error"]["code"] == "invalid_pack_path"
    marker = "SYNTHETIC_NO_CASE_SAVE_SENTINEL"
    result = client.post("/api/v1/content/cases", json={"summary": marker})
    assert result.status_code == 405
    db = app.state.services.db
    assert all(marker not in r["body_json"] for r in db.fetch_all("SELECT body_json FROM content_case_versions"))
    assert client.get("/api/v1/content/questions/missing/versions/1").status_code == 404


def test_withdrawn_default_pack_is_not_reactivated_on_restart(app):
    repository = app.state.services.registry["content"]
    repository.withdraw_pack("renulus-foundations", "1.1.2", "Synthetic pack hold")
    restarted = create_app(app.state.services.paths.root, token="synthetic-test-token")
    assert restarted.state.services.registry["content"].active_manifest() is None
    assert restarted.state.services.registry["content"].list_questions() == []
    assert restarted.state.services.registry["content"].get_question_version("RN-CKD-001", 1)["answer"] == "A"


def test_source_impact_route_is_metadata_only(client):
    result = client.get("/api/v1/content/sources/K01/references")
    assert result.status_code == 200
    assert any(r["id"] == "RN-CKD-001" for r in result.json())
    assert '"answer"' not in json.dumps(result.json())
