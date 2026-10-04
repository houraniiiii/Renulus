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
    assert client.get("/api/v1/content/manifest").json()["version"] == "1.0.0"
    assert len(client.get("/api/v1/content/topics").json()) == 27
    assert len(client.get("/api/v1/content/cases").json()) == 14
    assert len(client.get("/api/v1/content/questions").json()) == 52
    assert len(app.state.services.registry["content"].list_questions("T06")) == 6
    assert client.get("/api/v1/content/sources/K10-2012").json()["register_id"] == "K10"


def test_http_question_never_returns_keys_or_option_explanations(client):
    summaries = client.get("/api/v1/content/questions?topic_id=T21").json()
    assert len(summaries) == 4
    assert all("answer" not in q and "options" not in q for q in summaries)
    q = client.get("/api/v1/content/questions/RN-TX-002/versions/1").json()
    assert "correct_option_ids" not in q and "answer" not in q
    assert "rationale" not in q and "explanation" not in q
    assert all(set(o) == {"id", "text"} for o in q["options"])


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
    repository.withdraw_pack("renulus-foundations", "1.0.0", "Synthetic pack hold")
    restarted = create_app(app.state.services.paths.root, token="synthetic-test-token")
    assert restarted.state.services.registry["content"].active_manifest() is None
    assert restarted.state.services.registry["content"].list_questions() == []
    assert restarted.state.services.registry["content"].get_question_version("RN-CKD-001", 1)["answer"] == "A"


def test_source_impact_route_is_metadata_only(client):
    result = client.get("/api/v1/content/sources/K01/references")
    assert result.status_code == 200
    assert any(r["id"] == "RN-CKD-001" for r in result.json())
    assert '"answer"' not in json.dumps(result.json())
