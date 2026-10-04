"""Pinned source annotations never change the original case or retention state."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from renulus.cases.currency import MAX_CURRENCY_ANNOTATIONS
from renulus.cases.models import HandoffCase, StartCase
from renulus.cases.repository import CaseRepository
from renulus.server import create_app

from .conftest import ContentFixture, HIDDEN_SENTINEL, SENTINEL, TEACHING, assert_absent_from_profile


def impact(version=1, *, state="needs-re-review", count=1):
    return {"kind": "case", "id": TEACHING["id"], "version": version,
            "needs_re_review": state == "needs-re-review" and count > 0,
            "annotations": [{"entry_id": f"synthetic-change-{index}", "kind": "case",
                "entity_id": TEACHING["id"], "version": version, "title": "Synthetic source correction",
                "detected_at": "2026-10-04T18:00:00+00:00", "state": state, "review_state": "pending",
                "locators": [HIDDEN_SENTINEL], "future_payload": SENTINEL} for index in range(count)]}


class CurrencyFixture:
    def __init__(self, result=None, error=None):
        self.result = impact() if result is None else result
        self.error, self.calls = error, []

    def needs_re_review(self, kind, identifier, version):
        self.calls.append((kind, identifier, version))
        if self.error:
            raise self.error
        return deepcopy(self.result)


def install(services, fixture):
    services.registry["updates"] = SimpleNamespace(affected=fixture)


def test_live_currency_refresh_keeps_pin_stages_history_revision_and_handoff_valid(repository, services):
    reader = CurrencyFixture(result=impact(count=0))
    install(services, reader)
    started = repository.start(StartCase(kind="teaching", teaching_case_id=TEACHING["id"]))
    session = repository._sessions[started["id"]]
    session.messages.append({"id": "synthetic-history", "role": "user", "content": SENTINEL,
                             "created_at": started["created_at"]})
    before = deepcopy(session)
    context = repository._context(session)
    ticket = repository.handoff(session.id, HandoffCase(revision=session.revision, target="explain"))
    reader.result = impact()
    services.registry["content"].item["version"] = 2
    services.registry["content"].item["stages"][0]["narrative"] = "A later pack narrative"
    view = repository.get(session.id)
    assert view["teaching"]["currency"]["status"] == "needs-re-review"
    assert view["teaching"]["version"] == 1 and view["revision"] == before.revision
    assert view["messages"] == before.messages and view["teaching"]["stages"] == started["teaching"]["stages"]
    assert session.teaching == before.teaching and session.updated_at == before.updated_at
    assert view["scope"]["kind"] == "temporary-case" and not view["saved"]
    assert HIDDEN_SENTINEL not in json.dumps(view)
    assert repository._context(session) == context
    assert repository.resolve_handoff(ticket["id"], "explain")["scope"].kind == "temporary-case"
    assert set(reader.calls) == {("case", TEACHING["id"], 1)}
    assert_absent_from_profile(services, SENTINEL)


def test_saved_snapshot_annotation_is_live_metadata_and_never_saved_in_teaching_json(repository, services):
    reader = CurrencyFixture()
    install(services, reader)
    started = repository.start(StartCase(kind="teaching", teaching_case_id=TEACHING["id"]))
    saved = repository.save(started["id"], 1)
    row = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (started["id"],))
    assert "currency" not in json.loads(row["teaching_json"])
    reader.result = impact(state="dismissed")
    reopened = CaseRepository(services).get(started["id"])
    summary = repository.list_saved()[0]
    assert reopened["teaching"]["currency"]["status"] == summary["currency"]["status"] == "no-known-impact"
    assert summary["currency"]["id"] == TEACHING["id"] and summary["currency"]["version"] == 1
    assert "teaching_id" not in summary and "teaching_version" not in summary
    assert reopened["scope"] == saved["scope"] and not reopened["dirty"] and reopened["saved"]
    assert reopened["teaching"]["stages"] == saved["teaching"]["stages"]
    assert services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (started["id"],)) == row
    assert services.db.fetch_all("SELECT * FROM learning_evidence") == []


def test_daily_case_and_snapshot_never_enter_updates_projection(repository, services):
    reader = CurrencyFixture(error=AssertionError("Daily input cannot cross this seam"))
    install(services, reader)
    started = repository.start(StartCase(text=SENTINEL))
    assert repository.get(started["id"])["teaching"] is None
    assert_absent_from_profile(services, SENTINEL)
    saved = repository.save(started["id"], 1)
    assert "currency" not in repository.list_saved()[0]
    assert reader.calls == []
    repository.delete(started["id"], saved["revision"])
    assert_absent_from_profile(services, SENTINEL)


@pytest.mark.parametrize("condition", ["missing", "reader-missing", "error", "wrong-id", "wrong-version", "not-bool", "wrong-row"])
def test_unavailable_or_invalid_updates_never_claim_no_impact(repository, services, condition, caplog):
    reader = CurrencyFixture(error=RuntimeError(SENTINEL) if condition == "error" else None)
    if condition == "reader-missing":
        install(services, object())
    elif condition != "missing":
        install(services, reader)
    if condition == "wrong-id":
        reader.result["id"] = "another-original-case"
    elif condition == "wrong-version":
        reader.result["version"] = 2
    elif condition == "not-bool":
        reader.result["needs_re_review"] = 0
    elif condition == "wrong-row":
        reader.result["annotations"][0]["version"] = 99
    case = repository.start(StartCase(kind="teaching", teaching_case_id=TEACHING["id"]))
    assert case["teaching"]["currency"]["status"] == "unavailable"
    assert case["teaching"]["currency"]["needs_re_review"] is None
    assert SENTINEL not in json.dumps(case) and SENTINEL not in caplog.text
    assert case["revision"] == 1 and not case["saved"]


def test_annotation_count_is_bounded_and_hidden_stage_locators_are_not_disclosed(repository, services):
    reader = CurrencyFixture(result=impact(count=MAX_CURRENCY_ANNOTATIONS + 5))
    for row in reader.result["annotations"]:
        row["title"] = "A" * 800
    install(services, reader)
    summary = repository.list_teaching()[0]
    assert "stages" not in summary
    currency = summary["currency"]
    assert currency["annotation_count"] == MAX_CURRENCY_ANNOTATIONS + 5 and currency["truncated"]
    assert len(currency["annotations"]) == MAX_CURRENCY_ANNOTATIONS
    assert all(len(row["title"]) == 500 for row in currency["annotations"])
    assert HIDDEN_SENTINEL not in json.dumps(summary) and SENTINEL not in json.dumps(summary)
    assert_absent_from_profile(services, SENTINEL)


def test_currency_projection_is_in_actual_cases_api_and_rechecked_on_get(tmp_path):
    app = create_app(tmp_path / "currency-api")
    services = app.state.services
    services.registry["content"] = ContentFixture()
    reader = CurrencyFixture(result=impact(count=0))
    install(services, reader)
    with TestClient(app) as client:
        catalogue = client.get("/api/v1/cases/teaching")
        assert catalogue.headers["cache-control"] == "no-store"
        assert catalogue.json()["cases"][0]["currency"]["status"] == "no-known-impact"
        case = client.post("/api/v1/cases/sessions", json={"kind": "teaching", "teaching_case_id": TEACHING["id"]}).json()
        reader.result = impact()
        view = client.get(f"/api/v1/cases/sessions/{case['id']}")
        assert view.status_code == 200 and view.json()["teaching"]["currency"]["needs_re_review"] is True
        assert client.get("/api/v1/cases/saved").json()["cases"] == []
        assert HIDDEN_SENTINEL not in view.text and SENTINEL not in view.text


@pytest.fixture
def actual_affected(services, monkeypatch):
    # In integration this imports the installed producer. This lane can run the
    # same read interface from an explicitly configured clean parent worktree.
    source = os.environ.get("RENULUS_CASES_UPDATES_SOURCE")
    import renulus
    if source:
        monkeypatch.setattr(renulus, "__path__", [*renulus.__path__, str(Path(source).resolve() / "runtime/renulus")])
    if importlib.util.find_spec("renulus.updates") is None:
        pytest.skip("The actual Updates producer or explicit parent source is required")
    from renulus.updates.impact import AffectedVersions
    import renulus.updates.impact as producer
    root = Path(producer.__file__).parent
    if source and not root.resolve().is_relative_to(Path(source).resolve()):
        pytest.skip("Run the configured actual producer check in a fresh process")
    services.db.apply_migration("cases-check-updates-base", (root / "schema.sql").read_text(encoding="utf-8"))
    services.db.apply_migration("cases-check-updates-review", (root / "migrations/003-reviewed-source-status.sql").read_text(encoding="utf-8"))
    reader = AffectedVersions(services.db)
    install(services, reader)
    return reader


def test_actual_source_impact_marks_only_the_pinned_version_and_preserves_snapshot(repository, services, actual_affected):
    old_source = {"id": "synthetic-old-source", "register_id": "K03", "url": "https://example.invalid/synthetic-v1.pdf"}
    services.db.execute("CREATE TABLE content_case_versions(case_id TEXT,version INTEGER,body_json TEXT,PRIMARY KEY(case_id,version))")
    for version in (1, 2):
        item = deepcopy(TEACHING)
        source = old_source if version == 1 else {**old_source, "id": "synthetic-new-source", "url": "https://example.invalid/synthetic-v2.pdf"}
        item.update({"version": version, "source_records": [source], "sources": []})
        item["stages"][1]["sources"] = [{"source_id": source["id"], "locator": HIDDEN_SENTINEL}]
        services.db.execute("INSERT INTO content_case_versions VALUES(?,?,?)", (item["id"], version, json.dumps(item)))
    started = repository.start(StartCase(kind="teaching", teaching_case_id=TEACHING["id"]))
    assert started["teaching"]["currency"]["status"] == "no-known-impact"
    repository._sessions[started["id"]].messages.append({"id": "synthetic-discussion", "role": "user",
        "content": SENTINEL, "created_at": started["created_at"]})
    assert_absent_from_profile(services, SENTINEL)
    snapshot = repository.save(started["id"], 1)
    canonical = services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (started["id"],))
    originals = services.db.fetch_all("SELECT * FROM content_case_versions ORDER BY version")
    context = repository._context(repository._sessions[started["id"]])
    services.db.execute("INSERT INTO update_entries(id,source_id,external_id,title,url,kind,discovered_at,review_state,summary,source_metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("synthetic-change", "K03", "synthetic-change", "Synthetic source correction", "https://example.invalid/synthetic-correction.pdf",
         "correction", "2026-10-04T18:00:00+00:00", "pending", "Synthetic change for source review", "{}"))
    with services.db.transaction() as conn:
        assert actual_affected.record(conn, "synthetic-change", {"register_id": "K03", "pinned_source_id": old_source["id"]},
            "2026-10-04T18:00:00+00:00", "synthetic-source-correction") == 1
    services.registry["content"].item["version"] = 2
    reopened = CaseRepository(services).get(started["id"])
    assert reopened["teaching"]["currency"]["status"] == "needs-re-review"
    assert reopened["teaching"]["version"] == 1 and reopened["scope"] == snapshot["scope"]
    assert reopened["revision"] == snapshot["revision"] and reopened["messages"] == snapshot["messages"]
    assert reopened["teaching"]["stages"] == snapshot["teaching"]["stages"]
    assert HIDDEN_SENTINEL not in json.dumps(reopened["teaching"]["currency"])
    assert repository.list_saved()[0]["currency"]["version"] == 1
    assert repository.list_teaching()[0]["currency"]["needs_re_review"] is False
    assert repository._context(repository._sessions[started["id"]]) == context
    services.db.execute("UPDATE update_affected_versions SET state='dismissed' WHERE entry_id=?", ("synthetic-change",))
    assert repository.get(started["id"])["teaching"]["currency"]["status"] == "no-known-impact"
    assert services.db.fetch_one("SELECT * FROM case_sessions WHERE id=?", (started["id"],)) == canonical
    assert services.db.fetch_all("SELECT * FROM content_case_versions ORDER BY version") == originals
    repository.delete(started["id"], 1)
    assert_absent_from_profile(services, SENTINEL)
