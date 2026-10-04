import json

from fastapi.testclient import TestClient

from renulus.server import create_app

from .conftest import SENTINEL, ProviderFixture, assert_absent_from_profile


def decode_sse(body):
    return [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]


def test_real_router_direct_json_save_reopen_and_delete(tmp_path):
    profile = tmp_path / "case-api"
    app = create_app(profile)
    services = app.state.services
    provider = ProviderFixture(["Synthetic response from a test fixture"])
    services.registry["provider"] = provider
    with TestClient(app) as client:
        response = client.post("/api/v1/cases/sessions", json={"text": SENTINEL})
        assert response.status_code == 201
        case = response.json()
        assert case["id"] and "result" not in case
        response = client.post(f"/api/v1/cases/sessions/{case['id']}/discuss",
                               json={"revision": case["revision"],
                                     "request_id": "api-request", "message": "Discuss"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        frames = decode_sse(response.text)
        assert [e["type"] for e in frames] == ["started", "answer.delta", "completed"]
        assert [e["sequence"] for e in frames] == [1, 2, 3]
        assert_absent_from_profile(services, SENTINEL)
        current = client.get(f"/api/v1/cases/sessions/{case['id']}").json()
        saved = client.post(f"/api/v1/cases/sessions/{case['id']}/save",
                            json={"revision": current["revision"]}).json()
        assert saved["saved"] and saved["scope"]["kind"] == "saved-case"
        assert client.get("/api/v1/cases/saved").json()["cases"][0]["id"] == case["id"]
    with TestClient(create_app(profile)) as restarted:
        reopened = restarted.get(f"/api/v1/cases/sessions/{case['id']}").json()
        assert reopened == saved
        response = restarted.delete(f"/api/v1/cases/sessions/{case['id']}",
                                    params={"revision": reopened["revision"]})
        assert response.json()["deleted"] and not response.json()["purge_pending"]
        assert restarted.get(f"/api/v1/cases/sessions/{case['id']}").status_code == 410
        assert restarted.get("/api/v1/cases/saved").json() == {"cases": []}
    assert_absent_from_profile(services, SENTINEL)


def test_payload_cannot_set_scope_or_supply_unsafe_attachment_path(tmp_path):
    app = create_app(tmp_path / "case-validation")
    with TestClient(app) as client:
        response = client.post("/api/v1/cases/sessions",
                               json={"text": SENTINEL, "scope": {"kind": "study"}})
        assert response.status_code == 422
        assert SENTINEL not in response.text
        case = client.post("/api/v1/cases/sessions", json={"text": SENTINEL}).json()
        capabilities = client.get("/api/v1/cases/capabilities").json()
        assert capabilities["inputs"]["text"]["supported"]
        assert not capabilities["inputs"]["image"]["supported"]
        for kind in ("image", "pdf"):
            url = f"/api/v1/cases/sessions/{case['id']}/attachments"
            response = client.post(url, json={"kind": kind, "revision": 1, "path": SENTINEL})
            assert response.status_code == 422
            assert SENTINEL not in response.text
            response = client.post(url, json={"kind": kind, "revision": 1})
            assert response.status_code == 409
            assert response.json()["error"]["code"] == f"volatile_{kind}_unavailable"
    assert_absent_from_profile(app.state.services, SENTINEL)
