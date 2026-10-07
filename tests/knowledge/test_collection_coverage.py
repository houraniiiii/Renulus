"""Synthetic policy/canonical/API proof; no native index, helpers or providers."""
import hashlib
from io import BytesIO
import ipaddress
import json
from pathlib import Path
import socket
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
import pytest

from renulus.contracts import ApiError
from renulus.knowledge import api as knowledge_api
from renulus.knowledge.acquired import (AcquiredLiterature, EVIDENCE_PREFIX,
    MARKER, SELECTION, SELECTION_REVIEW)
from renulus.knowledge.collection import CollectionCatalogue, MANIFEST
from renulus.knowledge.repository import KnowledgeRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database
from test_acquired import jats


@pytest.fixture(autouse=True)
def no_engines_or_external_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Policy proof must not initialize an engine/helper or worker")
    for name in ("DoclingExtractor", "FastEmbedEngine", "LanceIndex"):
        monkeypatch.setattr("renulus.knowledge.repository." + name, forbidden)
    monkeypatch.setattr(knowledge_api.IngestionWorker, "start", forbidden)
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guard(sock, address, original=original):
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                return original(sock, address)  # Windows event-loop self-pipe only.
            pytest.fail("No external network in policy proof")
        monkeypatch.setattr(socket.socket, name, guard)


@pytest.fixture
def repository(tmp_path):
    paths = AppPaths.create(tmp_path / "profile")
    db = Database(paths.database)
    schema = Path(__file__).parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    class FakeEngine:
        def __getattr__(self, name):
            pytest.fail("An enqueue policy test called an engine: " + name)
    return KnowledgeRepository(Services(paths, db), extractor=FakeEngine(),
        embedder=FakeEngine(), index=SimpleNamespace(path=paths.indexes / "unused"))


def frozen(root, selected=("PMC90001", "PMC90002"), excluded=(), **patch):
    record = {"frozen": True, "query_scope_frozen": True,
        "status": "frozen_final_automated_snapshot", "pmcids": list(selected),
        "records": [{"pmcid": value, "pmid": value[3:]} for value in selected],
        "excluded_pmcids": list(excluded), "excluded_records": []}
    record.update(patch)
    path = root / SELECTION
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


def project_review(root, item, decision="include", **patch):
    entry = {"source_id": item["source_id"], "pmcid": item["pmcid"],
        "original_sha256": item["sha256"], "decision": decision,
        "reason": "Project scope review admits this synthetic research candidate",
        "reviewed_at": "2026-10-05T05:10:00Z"}
    entry.update(patch)
    (root / SELECTION_REVIEW).write_text(json.dumps({"schema_version": 1,
        "entries": [entry]}), encoding="utf-8")
    return entry


def manifest(root, items):
    target = root / MANIFEST
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")


def article(root, pmcid, *, statement="Creative Commons Attribution licence"):
    name = pmcid + ".1"
    xml = root / "raw/L02" / name / (name + ".xml")
    xml.parent.mkdir(parents=True, exist_ok=True)
    raw = jats(pmcid=pmcid, statement=statement).replace(b"90001</article-id>",
        (pmcid[3:] + "</article-id>").encode()).replace(b"10.1234/synthetic", ("10.1234/" + pmcid).encode())
    xml.write_bytes(raw)
    record = {"pmcid": pmcid, "pmid": pmcid[3:], "doi": "10.1234/" + pmcid, "version": 1,
        "is_pmc_openaccess": True, "is_manuscript": False, "is_historical_ocr": False,
        "is_retracted": False, "license_code": "CC BY",
        "xml_url": "s3://pmc-oa-opendata/" + name + "/" + name + ".xml?md5=" + hashlib.md5(raw).hexdigest()}
    meta = xml.with_suffix(".json")
    meta.write_text(json.dumps(record), encoding="utf-8")
    items = []
    for path, role in ((xml, "fulltext-jats"), (meta, "article-version-metadata")):
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        origin = ("https://pmc-oa-opendata.s3.amazonaws.com/metadata/" + name + ".json") if path == meta else record["xml_url"].replace("s3://pmc-oa-opendata/", "https://pmc-oa-opendata.s3.amazonaws.com/")
        items.append({"source_id": "L02", "pmcid": pmcid, "pmid": pmcid[3:],
            "doi": record["doi"], "article_version": 1, "artifact_type": role,
            "local_path": path.relative_to(root).as_posix(), "sha256": digest, "bytes": len(body),
            "origin_url": origin, "status": "acquired-unreviewed", "licence": "CC BY",
            "acquisition_provenance": [{"source_id": "L02", "artifact_type": role,
                "sha256": digest, "status": "acquired-unreviewed", "manifest": "synthetic.jsonl", "line": 1}]})
    return items


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "collection"
    items = article(root, "PMC90001") + article(root, "PMC90002")
    frozen(root)
    manifest(root, items)
    return root, items


def registered(repository, bundle):
    root, _ = bundle
    catalogue = CollectionCatalogue(repository, root)
    catalogue.register(source_id="L02")
    return catalogue, {entry["metadata"]["pmcid"]: entry["id"] for entry in
        catalogue.list()["entries"] if MARKER in entry["metadata"]["asset_role"]}


def assert_no_jobs(repository):
    assert repository.db.fetch_all("SELECT * FROM knowledge_jobs") == []
    assert repository.list_documents()["documents"] == []


def forbid_bodies(monkeypatch, root, admitted=()):
    original = Path.open
    admitted = {Path(path).resolve() for path in admitted}
    opened = []
    def guarded(path, *args, **kwargs):
        if path.resolve().is_relative_to((root / "raw").resolve()):
            assert path.resolve() in admitted, "Excluded original must not be opened"
            opened.append(path.resolve())
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", guarded)
    return opened


def test_baseline_exclusions_preview_register_explicit_and_next_are_not_retractions(repository, bundle, monkeypatch):
    root, items = bundle
    frozen(root, excluded=("PMC90002",))
    items[2]["frozen_selection_state"] = "excluded_from_default_learning_candidate_set"
    manifest(root, items)
    admitted = [root / item["local_path"] for item in items[:2]]
    forbid_bodies(monkeypatch, root, admitted)
    catalogue, ids = registered(repository, bundle)
    blocked = next(entry for entry in catalogue.preview()["entries"] if entry["id"] == ids["PMC90002"])
    assert blocked["eligibility"] == "literature_selection_excluded"
    assert not blocked["metadata"]["retracted"] and not blocked["metadata"]["superseded"]
    assert not blocked["rights"]["index"]
    assert catalogue.import_selected([ids["PMC90002"]])["queued"] == 0
    result = catalogue.import_next()
    assert result["newly_queued"] == 1 and result["rejected"] == 1
    assert result["rejections"] == {"literature_selection_excluded": 1}
    assert result["done"]


def test_explicit_mixed_batch_rechecks_changed_baseline_without_refresh(repository, bundle, monkeypatch):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    frozen(root, excluded=("PMC90002",))
    forbid_bodies(monkeypatch, root, [root / item["local_path"] for item in items[:2]])
    result = catalogue.import_selected(list(ids.values()))
    assert result["queued"] == 1
    assert any(entry.get("code") == "literature_selection_excluded" for entry in result["results"])
    revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions")
    metadata = json.loads(revision["metadata_json"])
    assert metadata["publication_status"] == "unknown"
    assert not metadata["latest_final_verified"] and not metadata["content_reviewed"]


def test_pmid_exclusion_blocks_receipt_without_pmid_by_recorded_alias(repository, bundle, monkeypatch):
    root, items = bundle
    for item in items:
        item.pop("pmid")
    manifest(root, items)
    frozen(root, excluded_pmids=["90002"])
    forbid_bodies(monkeypatch, root)
    catalogue, ids = registered(repository, bundle)
    result = catalogue.import_selected([ids["PMC90002"]])
    assert result["results"][0]["code"] == "literature_selection_excluded"
    assert_no_jobs(repository)


@pytest.mark.parametrize("bad", ["missing", "{", "[]", "duplicate", "not-frozen",
    "not-scope-frozen", "bad-list", "bad-id", "missing-records"])
def test_missing_corrupt_or_unfrozen_baseline_fails_truthfully_before_bodies(repository, bundle, monkeypatch, bad):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    project_review(root, items[0])  # A valid include cannot hide unavailable baseline evidence.
    path = root / SELECTION
    if bad == "missing":
        path.unlink()
    elif bad in ("{", "[]"):
        path.write_text(bad)
    elif bad == "duplicate":
        path.write_text('{"frozen":false,"frozen":true}')
    else:
        record = frozen(root)
        if bad == "not-frozen": record["frozen"] = False
        if bad == "not-scope-frozen": record["query_scope_frozen"] = False
        if bad == "bad-list": record["excluded_pmcids"] = {}
        if bad == "bad-id": record["excluded_pmcids"] = ["not-a-PMCID"]
        if bad == "missing-records": record.pop("excluded_records")
        path.write_text(json.dumps(record))
    forbid_bodies(monkeypatch, root)
    expected = "literature_selection_unavailable" if bad == "missing" else "literature_selection_invalid"
    assert catalogue.import_selected([ids["PMC90001"]])["results"][0]["code"] == expected
    assert catalogue.preview()["entries"][0]["eligibility"] == expected
    assert_no_jobs(repository)


def test_changed_baseline_blocks_existing_job_replay_without_opening_original(repository, bundle, monkeypatch):
    root, _ = bundle
    catalogue, ids = registered(repository, bundle)
    first = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    frozen(root, excluded=("PMC90001",))
    forbid_bodies(monkeypatch, root)
    result = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    assert result["code"] == "literature_selection_excluded" and "job" not in result
    assert repository.get_job(first["job"]["id"])["state"] == "queued"
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 1


def test_review_include_recovers_registered_exclusion_and_records_reason_without_currency_claim(repository, bundle):
    root, items = bundle
    frozen(root, excluded=("PMC90001", "PMC90002"))
    items[0]["frozen_selection_state"] = "excluded_from_default_learning_candidate_set"
    manifest(root, items)
    catalogue, ids = registered(repository, bundle)
    review = project_review(root, items[0])
    # No register refresh: a new project decision can recover an excluded row.
    result = catalogue.import_next()
    assert result["newly_queued"] == 1 and result["rejected"] == 1
    revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions")
    metadata = json.loads(revision["metadata_json"])
    evidence = json.loads(next(note[len(EVIDENCE_PREFIX):] for note in metadata["notes"] if note.startswith(EVIDENCE_PREFIX)))
    assert evidence["selection"]["baseline_decision"] == "excluded"
    assert evidence["selection"]["project_review"] == review
    assert metadata["publication_status"] == "unknown"
    assert not any(metadata[key] for key in ("latest_final_verified", "content_reviewed", "retracted", "superseded"))
    assert catalogue.import_selected([ids["PMC90001"]])["results"][0]["document_id"] == revision["document_id"]


@pytest.mark.parametrize("patch", [{"source_id": "L03"}, {"pmcid": "PMC90002"}, {"original_sha256": "a" * 64}])
def test_valid_review_for_other_identity_or_bytes_cannot_include_this_file(repository, bundle, monkeypatch, patch):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    project_review(root, items[0], **patch)
    forbid_bodies(monkeypatch, root)
    catalogue, ids = registered(repository, bundle)
    assert catalogue.import_selected([ids["PMC90001"]])["results"][0]["code"] == "literature_selection_excluded"
    assert_no_jobs(repository)


@pytest.mark.parametrize("bad", ["json", "duplicate-key", "duplicate-entry", "version", "hash",
    "date", "naive-date", "reason", "decision", "rights", "retraction"])
def test_invalid_review_never_overrides_selection_rights_or_status(repository, bundle, monkeypatch, bad):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    entry = project_review(root, items[0])
    path = root / SELECTION_REVIEW
    record = {"schema_version": 1, "entries": [entry]}
    if bad == "json": path.write_text("{")
    elif bad == "duplicate-key": path.write_text('{"schema_version":1,"schema_version":1,"entries":[]}')
    else:
        if bad == "duplicate-entry": record["entries"].append(dict(entry))
        if bad == "version": record["schema_version"] = True
        if bad == "hash": entry["original_sha256"] = "unknown"
        if bad == "date": entry["reviewed_at"] = "yesterday"
        if bad == "naive-date": entry["reviewed_at"] = "2026-10-05T05:00:00"
        if bad == "reason": entry["reason"] = " "
        if bad == "decision": entry["decision"] = "current-guidance"
        if bad == "rights": entry["rights"] = {"index": True}
        if bad == "retraction": entry["retracted"] = False
        path.write_text(json.dumps(record))
    forbid_bodies(monkeypatch, root)
    catalogue, ids = registered(repository, bundle)
    assert catalogue.import_selected([ids["PMC90001"]])["results"][0]["code"] == "literature_selection_review_invalid"
    assert_no_jobs(repository)


@pytest.mark.parametrize("change", ["exclude", "delete", "corrupt"])
def test_changed_review_revokes_inclusion_before_body_or_replay(repository, bundle, monkeypatch, change):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    project_review(root, items[0])
    catalogue, ids = registered(repository, bundle)
    first = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    if change == "exclude": project_review(root, items[0], decision="exclude")
    if change == "delete": (root / SELECTION_REVIEW).unlink()
    if change == "corrupt": (root / SELECTION_REVIEW).write_text("{")
    forbid_bodies(monkeypatch, root)
    result = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    assert "job" not in result and result["code"] in {"literature_project_selection_excluded",
        "literature_selection_excluded", "literature_selection_review_invalid"}
    assert repository.get_job(first["job"]["id"])["state"] == "queued"


def test_review_change_after_inspection_blocks_direct_adoption_and_replay(repository, bundle):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    adapter = AcquiredLiterature(root, catalogue._literature_selection())
    entry = repository.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (ids["PMC90001"],))
    _, metadata = adapter.selections([entry])
    inspected = adapter.inspect(items[0], metadata[("PMC90001", 1)])
    catalogue._import_acquired(entry, inspected)
    project_review(root, items[0], decision="exclude")
    with pytest.raises(ApiError) as caught:
        catalogue._import_acquired(entry, inspected)
    assert caught.value.code == "literature_project_selection_excluded"
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 1


@pytest.mark.parametrize("point", ["metadata", "body", "adoption"])
def test_review_change_during_inspection_cannot_commit(repository, bundle, monkeypatch, point):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    project_review(root, items[0])
    catalogue, ids = registered(repository, bundle)
    original_open = Path.open
    target = root / items[1 if point == "metadata" else 0]["local_path"]
    def changing_open(path, *args, **kwargs):
        if point != "adoption" and path == target and args and args[0] == "rb":
            with original_open(path, "rb") as stream:
                raw = stream.read()
            project_review(root, items[0], decision="exclude")
            return BytesIO(raw)
        return original_open(path, *args, **kwargs)
    if point == "adoption":
        original_adopt = catalogue._import_acquired
        def changed_adopt(entry, inspected):
            project_review(root, items[0], decision="exclude")
            return original_adopt(entry, inspected)
        monkeypatch.setattr(catalogue, "_import_acquired", changed_adopt)
    monkeypatch.setattr(Path, "open", changing_open)
    result = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    assert result["code"] == "literature_project_selection_excluded"
    assert_no_jobs(repository)


def test_include_review_never_bypasses_strict_jats_component_exceptions(repository, tmp_path):
    root = tmp_path / "collection"
    items = article(root, "PMC90001", statement="CC BY except third-party material")
    frozen(root, excluded=("PMC90001",))
    manifest(root, items)
    project_review(root, items[0])
    catalogue, ids = registered(repository, (root, items))
    assert catalogue.import_selected([ids["PMC90001"]])["results"][0]["code"] == "article_permission_required"
    assert_no_jobs(repository)


@pytest.mark.parametrize("restriction", ["licence", "operation", "retraction"])
def test_include_review_cannot_clear_independent_restrictions(repository, bundle, restriction):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    if restriction == "licence": items[0]["licence"] = "CC BY-NC"
    if restriction == "operation": items[0]["processing_scope"] = {"index": False, "indexing_embedding": True}
    if restriction == "retraction":
        repository.update_source_status({"contract_version": 1, "event_id": "synthetic-retraction",
            "source_id": "L02", "identity": {"pmcid": "PMC90001"},
            "changes": {"retracted": True}, "evidence": [{"inspected": True}]})
    manifest(root, items)
    project_review(root, items[0])
    catalogue, ids = registered(repository, bundle)
    result = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    assert result["code"] in {"article_permission_required", "article_status_unavailable"}
    assert_no_jobs(repository)


def supported_file(root, sid="E07", **patch):
    path = root / ("raw/E07/image.png" if sid == "E07" else "raw/L03/paper.pdf")
    path.parent.mkdir(parents=True, exist_ok=True)
    body = b"SYNTHETIC_IMAGE_POLICY_ONLY" if sid == "E07" else b"%PDF-1.4 SYNTHETIC_POLICY_ONLY"
    path.write_bytes(body)
    item = {"source_id": sid, "local_path": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
        "artifact_type": "illustration_original_png" if sid == "E07" else "fulltext_original_PDF",
        "status": "obtained" if sid == "E07" else "obtained_verified_CC_BY_article_body",
        "processing_scope": {"human_reading": "permitted", "display": "CC BY 4.0 attribution required",
            "caching": "permitted", "indexing_embedding": "eligible under CC BY 4.0 subject to attribution and exclusions",
            "model_input": "licence allows reuse; no model calls performed", "derivation": "permitted; indicate changes"},
        "licence": {"identifier" if sid == "E07" else "code": "CC-BY-4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/", "evidence_url": "https://example.org/recorded-terms",
            "attribution": {"title": "Synthetic file", "author": "Synthetic author"}}}
    if sid == "L03": item["pmcid"] = "PMC90001"
    item.update(patch)
    return item


@pytest.mark.parametrize("sid", ["E07", "L03"])
def test_exact_supported_schema_aliases_enqueue_with_evidence_but_no_currentness(repository, tmp_path, sid):
    root = tmp_path / "collection"
    item = supported_file(root, sid)
    frozen(root)
    manifest(root, [item])
    catalogue = CollectionCatalogue(repository, root)
    preview = catalogue.preview(source_id=sid)["entries"][0]
    assert preview["eligibility"] == "eligible"
    assert all(preview["rights"][key] for key in ("display", "cache", "index", "embedding", "model_input", "derivation"))
    assert not preview["rights"]["evaluation"] and not preview["rights"]["redistribution"]
    catalogue.register(source_id=sid)
    result = catalogue.import_selected([preview["id"]])
    assert result["queued"] == 1
    revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions")
    metadata = json.loads(revision["metadata_json"])
    assert metadata["original_sha256"] == item["sha256"]
    assert not metadata["latest_final_verified"] and not metadata["content_reviewed"]
    assert item["licence"]["evidence_url"] in revision["rights_json"]
    assert "recorded-terms" in " ".join(metadata["notes"])
    assert (root / item["local_path"]).read_bytes() == (b"SYNTHETIC_IMAGE_POLICY_ONLY" if sid == "E07" else b"%PDF-1.4 SYNTHETIC_POLICY_ONLY")


@pytest.mark.parametrize("denial", [False, None, "not permitted under licence", "not authorised",
    "licence unknown", "eligible after review", "not cleared under licence"])
def test_operation_alias_denials_or_unknown_terms_override_positive_alias(tmp_path, denial):
    item = supported_file(tmp_path / "collection")
    item["processing_scope"]["index"] = denial
    rights = CollectionCatalogue._rights(item)
    assert not rights.index
    assert rights.embedding  # The denial's operation remains separate.


@pytest.mark.parametrize("identifier,code", [("CC-BY-NC-4.0", "CC-BY-4.0"),
    ("unknown", "CC-BY-4.0"), (False, "CC-BY-4.0"), (None, {})])
def test_licence_code_cannot_override_conflicting_or_unknown_identifier(tmp_path, identifier, code):
    item = supported_file(tmp_path / "collection", "L03")
    item["licence"].update(identifier=identifier, code=code)
    rights = CollectionCatalogue._rights(item)
    assert rights.licence == "unverified" and not rights.index


@pytest.mark.parametrize("field", ["third_party_notice_excerpts", "third_party_notice_count",
    "component_exceptions", "exclusions"])
def test_l03_component_notices_cannot_be_overridden_by_whole_file_booleans(repository, tmp_path, field):
    root = tmp_path / "collection"
    item = supported_file(root, "L03")
    item["processing_scope"] = {key: True for key in ("display", "cache", "index", "embedding", "model_input", "derivation")}
    item["licence"][field] = [{"pdf_page": 2, "text": "Synthetic third-party notice retained"}]
    frozen(root)
    manifest(root, [item])
    catalogue = CollectionCatalogue(repository, root)
    entry = catalogue.preview(source_id="L03")["entries"][0]
    assert entry["eligibility"] == "article_component_permission_required"
    assert "Synthetic third-party notice" in " ".join(entry["metadata"]["notes"])
    assert not CollectionCatalogue._rights(item).index
    catalogue.register(source_id="L03")
    assert catalogue.import_selected([entry["id"]])["queued"] == 0
    assert_no_jobs(repository)


def test_recorded_l03_reading_scope_and_e07_incidental_assets_remain_unavailable(repository, tmp_path):
    root = tmp_path / "collection"
    pdf = supported_file(root, "L03", processing_scope="Local original reading; CC BY notice recorded. AI, distribution and training not activated.")
    image = supported_file(root, status="obtained_excluded_outside_assigned_topic")
    frozen(root)
    manifest(root, [pdf, image])
    catalogue = CollectionCatalogue(repository, root)
    catalogue.register()
    entries = catalogue.list()["entries"]
    assert all(entry["eligibility"] != "eligible" for entry in entries)
    assert catalogue.import_selected([entry["id"] for entry in entries])["queued"] == 0
    assert_no_jobs(repository)


def test_changed_recorded_operation_denial_blocks_existing_job_replay(repository, tmp_path, monkeypatch):
    root = tmp_path / "collection"
    item = supported_file(root)
    manifest(root, [item])
    catalogue = CollectionCatalogue(repository, root)
    catalogue.register()
    identifier = catalogue.list()["entries"][0]["id"]
    assert catalogue.import_selected([identifier])["queued"] == 1
    item["processing_scope"]["index"] = False
    manifest(root, [item])
    forbid_bodies(monkeypatch, root)
    result = catalogue.import_selected([identifier])["results"][0]
    assert result["code"] == "source_permission_required" and "job" not in result
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 1


def test_collection_api_mixed_override_batch_and_revoked_replay(repository, bundle, monkeypatch):
    root, items = bundle
    frozen(root, excluded=("PMC90001", "PMC90002"))
    monkeypatch.setattr(knowledge_api, "KnowledgeRepository", lambda services: repository)
    app = FastAPI()
    @app.exception_handler(ApiError)
    async def error_handler(request, error):
        return JSONResponse({"error": {"code": error.code}}, status_code=error.status)
    app.include_router(knowledge_api.create_router(repository.services), prefix="/api/v1")
    repository.services.registry["knowledge_catalogue"].root = root.resolve()
    # No TestClient context: app/worker lifespans are deliberately not started.
    api = TestClient(app)
    preview = api.get("/api/v1/library/collection/preview?source_id=L02").json()
    assert all(entry["eligibility"] == "literature_selection_excluded" for entry in preview["entries"]), [(entry["metadata"]["pmcid"], entry["eligibility"]) for entry in preview["entries"]]
    assert api.post("/api/v1/library/collection/catalogue?source_id=L02").status_code == 200
    ids = [entry["id"] for entry in preview["entries"] if MARKER in entry["metadata"]["asset_role"]]
    body = {"entry_ids": ids, "scope": {"kind": "personal-library"}}
    assert api.post("/api/v1/library/collection/import", json=body).json()["queued"] == 0
    project_review(root, items[0])
    next_page = api.post("/api/v1/library/collection/import-next", json={"scope": body["scope"]})
    assert next_page.status_code == 202 and next_page.json()["newly_queued"] == 1
    assert next_page.json()["rejections"] == {"literature_selection_excluded": 1}
    project_review(root, items[0], decision="exclude")
    forbid_bodies(monkeypatch, root)
    replay = api.post("/api/v1/library/collection/import", json=body).json()
    assert replay["queued"] == 0 and all("job" not in result for result in replay["results"])
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 1
    api.close()


def test_selection_changed_but_still_admitted_requires_fresh_inspection(repository, bundle):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    entry = repository.db.fetch_one("SELECT * FROM knowledge_catalogue WHERE id=?", (ids["PMC90001"],))
    adapter = AcquiredLiterature(root, catalogue._literature_selection())
    _, matched = adapter.selections([entry])
    inspected = adapter.inspect(items[0], matched[("PMC90001", 1)])
    frozen(root, selected=("PMC90001", "PMC90002", "PMC90003"))
    with pytest.raises(ApiError) as caught:
        catalogue._import_acquired(entry, inspected)
    assert caught.value.code == "literature_selection_changed"
    assert_no_jobs(repository)


def test_new_include_review_preserves_document_identity_with_selection_provenance_revision(repository, bundle):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    first = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    frozen(root, excluded=("PMC90001",))
    review = project_review(root, items[0])
    second = catalogue.import_selected([ids["PMC90001"]])["results"][0]
    assert second["document_id"] == first["document_id"]
    assert second["revision_id"] != first["revision_id"]
    revision = repository.db.fetch_one("SELECT metadata_json FROM knowledge_revisions WHERE id=?", (second["revision_id"],))
    assert review["reason"] in revision["metadata_json"]
    assert repository.get_job(first["job"]["id"])["state"] == "cancelled"
    assert len(repository.list_documents()["documents"]) == 1


def test_baseline_change_between_admitted_batch_entries_prevents_second_body_read(repository, bundle, monkeypatch):
    root, items = bundle
    catalogue, ids = registered(repository, bundle)
    original = catalogue._import_acquired
    def changing(entry, inspected):
        result = original(entry, inspected)
        frozen(root, excluded=("PMC90002",))
        return result
    monkeypatch.setattr(catalogue, "_import_acquired", changing)
    forbid_bodies(monkeypatch, root, [root / item["local_path"] for item in items[:2]])
    result = catalogue.import_selected([ids["PMC90001"], ids["PMC90002"]])
    assert result["queued"] == 1 and result["results"][1]["code"] == "literature_selection_excluded"
    assert len(repository.db.fetch_all("SELECT * FROM knowledge_jobs")) == 1


def test_registration_rechecks_review_after_preview_before_catalogue_commit(repository, bundle, monkeypatch):
    root, items = bundle
    frozen(root, excluded=("PMC90001",))
    project_review(root, items[0])
    catalogue = CollectionCatalogue(repository, root)
    original = catalogue.preview
    def changing(**kwargs):
        preview = original(**kwargs)
        project_review(root, items[0], decision="exclude")
        return preview
    monkeypatch.setattr(catalogue, "preview", changing)
    catalogue.register(source_id="L02")
    entry = next(entry for entry in catalogue.list()["entries"] if MARKER in entry["metadata"]["asset_role"] and entry["metadata"]["pmcid"] == "PMC90001")
    assert entry["eligibility"] == "literature_project_selection_excluded"
    assert not entry["rights"]["index"]
    assert_no_jobs(repository)


def test_direct_inspection_of_review_excluded_file_never_opens_body(bundle, monkeypatch):
    root, items = bundle
    project_review(root, items[0], decision="exclude")
    forbid_bodies(monkeypatch, root)
    with pytest.raises(ApiError) as caught:
        AcquiredLiterature(root).inspect(items[0], {})
    assert caught.value.code == "literature_project_selection_excluded"


@pytest.mark.parametrize("restriction", ["retracted", "superseded", "repository_removed", "access_changed"])
def test_l03_review_include_does_not_override_recorded_or_journal_status(repository, tmp_path, restriction):
    root = tmp_path / "collection"
    item = supported_file(root, "L03")
    frozen(root, excluded=("PMC90001",))
    project_review(root, item)
    manifest(root, [item])
    catalogue = CollectionCatalogue(repository, root)
    catalogue.register(source_id="L03")
    identifier = catalogue.list()["entries"][0]["id"]
    repository.update_source_status({"contract_version": 1, "event_id": "synthetic-" + restriction,
        "source_id": "L03", "identity": {"pmcid": "PMC90001"},
        "changes": {restriction: True}, "evidence": [{"inspected": True}]})
    result = catalogue.import_selected([identifier])["results"][0]
    assert result["code"] == "article_status_unavailable"
    assert_no_jobs(repository)


def test_l03_review_changed_after_original_read_blocks_canonical_commit(repository, tmp_path, monkeypatch):
    root = tmp_path / "collection"
    item = supported_file(root, "L03")
    frozen(root, excluded=("PMC90001",))
    project_review(root, item)
    manifest(root, [item])
    catalogue = CollectionCatalogue(repository, root)
    catalogue.register(source_id="L03")
    identifier = catalogue.list()["entries"][0]["id"]
    original = Path.open
    def changing(path, *args, **kwargs):
        if path == root / item["local_path"] and args and args[0] == "rb":
            with original(path, "rb") as stream:
                raw = stream.read()
            project_review(root, item, decision="exclude")
            return BytesIO(raw)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", changing)
    result = catalogue.import_selected([identifier])["results"][0]
    assert result["code"] == "literature_project_selection_excluded"
    assert_no_jobs(repository)


def test_e07_other_formats_keep_parent_owned_generic_file_route(tmp_path, monkeypatch):
    root = tmp_path / "collection"
    path = root / "raw/E07/slides.pptx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"SYNTHETIC_DISPATCH_ONLY_NOT_AN_OFFICE_FORMAT_PROOF")
    entry = {"id": "asset_synthetic_dispatch", "source_id": "E07",
        "collection_path": path.relative_to(root).as_posix(), "title": "Synthetic dispatch",
        "reserved": False, "eligibility": "eligible", "metadata_json": '{}',
        "rights_json": '{}', "job_id": None, "document_id": None, "expected_sha256": 'a' * 64}
    calls = []
    def import_file(selected, **options):
        calls.append(selected)
        return {"status": "queued", "document_id": "synthetic", "job": {"id": "synthetic"}}
    db = SimpleNamespace(fetch_one=lambda *args: entry, execute=lambda *args: None)
    catalogue = CollectionCatalogue(SimpleNamespace(db=db, import_file=import_file), root)
    monkeypatch.setattr(catalogue, "_import_recorded", lambda *args: pytest.fail("PNG/PDF coverage must not capture office-file dispatch"))
    result = catalogue.import_selected([entry["id"]])
    assert result["queued"] == 1 and calls == [path.resolve()]
