# SPDX-License-Identifier: MIT
"""Connected conversations use the real legacy owners and additive sidecars."""
from fastapi.testclient import TestClient
import pytest

from renulus.server import create_app
from renulus.learn.conversation_api import create_router


def app_at(profile):
    app = create_app(profile)
    if "conversations" not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix="/api/v1")
    return app


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_saved_default_chat_and_draft_survive_restart_using_original_owner(tmp_path, kind):
    profile = tmp_path / "saved-chat"
    with TestClient(app_at(profile)) as client:
        created = client.post("/api/v1/conversations", json={"kind": kind, "title": "Fictional CKD study"})
        assert created.status_code == 201, created.text
        chat = created.json()
        assert chat["retention"] == "saved" and chat["project_id"] is None
        identifier = chat["identity"]["id"]
        route = f"/api/v1/conversations/{kind}/{identifier}"
        written = client.put(route + "/draft", json={"expected_revision": chat["revision"],
            "text": "Explain this fictional nephrology topic.", "content_refs": []})
        assert written.status_code == 200, written.text
    with TestClient(app_at(profile)) as restarted:
        result = restarted.get(route).json()
        assert result["identity"] == chat["identity"]
        assert restarted.get(route + "/draft").json()["text"] == "Explain this fictional nephrology topic."
        owner_route = f"/api/v1/learn/threads/{identifier}" if kind == "learning" else f"/api/v1/cases/sessions/{identifier}"
        assert restarted.get(owner_route).status_code == 200
