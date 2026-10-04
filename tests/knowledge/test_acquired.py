"""Synthetic receipts/JATS only. No live provider or source requests."""
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import time

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.acquired import EVIDENCE_PREFIX, collection_path
from renulus.knowledge.collection import CollectionCatalogue, MANIFEST
from renulus.knowledge.worker import IngestionWorker
from test_repository import repository, SyntheticExtractor


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    # LanceDB's Windows self-pipe uses loopback; external sockets are forbidden.
    for name in ("connect", "connect_ex"):
        original = getattr(socket.socket, name)
        def guard(sock, address, original=original):
            if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                return original(sock, address)
            raise AssertionError("No external network in acquired-literature tests")
        monkeypatch.setattr(socket.socket, name, guard)


def jats(*, url="https://creativecommons.org/licenses/by/4.0/", pmcid="PMC90001", article_type="research-article", statement="Creative Commons Attribution licence", extra_license=""):
    return f'''<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="{article_type}">
      <front><journal-meta><publisher><publisher-name>Synthetic publisher</publisher-name></publisher></journal-meta>
      <article-meta><article-id pub-id-type="pmcid">{pmcid}</article-id>
      <article-id pub-id-type="doi">10.1234/synthetic</article-id><article-id pub-id-type="pmid">90001</article-id>
      <title-group><article-title>Synthetic transplant rejection study</article-title></title-group>
      <contrib-group><contrib contrib-type="author"><name><surname>Learner</surname><given-names>Alex</given-names></name></contrib></contrib-group>
      <pub-date><year>2025</year><month>4</month><day>2</day></pub-date>
      <permissions><copyright-statement>Copyright Alex Learner</copyright-statement>
      <license><license-p>{statement}<ext-link xlink:href="{url}">Licence</ext-link></license-p></license>{extra_license}</permissions>
      <abstract><p>Transplant rejection surveillance education.</p></abstract></article-meta></front>
      <body><sec><title>Immune response</title><p>Review renal transplantation and immune rejection.</p>
      <fig><caption><p>FIGURE_SENTINEL</p></caption><graphic xlink:href="private.jpg"/></fig>
      <table-wrap><table><tr><td>TABLE_SENTINEL</td></tr></table></table-wrap>
      <supplementary-material><p>SUPPLEMENT_SENTINEL</p></supplementary-material>
      <media><p>MEDIA_SENTINEL</p></media><disp-quote><p>QUOTE_SENTINEL</p></disp-quote>
      <boxed-text><p>BOX_SENTINEL</p></boxed-text><p specific-use="third-party">THIRD_PARTY_SENTINEL</p>
      <p>Paragraph containing <inline-formula specific-use="third-party">INLINE_SENTINEL</inline-formula> also omitted.</p>
      </sec></body></article>'''.encode()


class Case:
    def __init__(self, root, raw=None, *, version=1):
        self.root, self.name = root, f"PMC90001.{version}"
        self.xml = root / "raw/L02-pmc-oa/articles" / self.name / (self.name + ".xml")
        self.xml.parent.mkdir(parents=True)
        self.xml.write_bytes(raw or jats())
        self.record = {"pmcid": "PMC90001", "version": version, "pmid": 90001, "doi": "10.1234/synthetic",
            "is_pmc_openaccess": True, "is_manuscript": False, "is_historical_ocr": False, "is_retracted": False,
            "license_code": "CC BY", "xml_url": "s3://pmc-oa-opendata/" + self.name + "/" + self.name + ".xml?md5=" + hashlib.md5(self.xml.read_bytes()).hexdigest()}
        self.meta = self.xml.with_suffix(".json")
        self.meta.write_text(json.dumps(self.record), encoding="utf-8")
        self.items = [self.receipt(self.xml, "fulltext-jats", version), self.receipt(self.meta, "article-version-metadata", version)]
        self.write()

    def receipt(self, path, role, version):
        raw = path.read_bytes()
        origin = ("https://pmc-oa-opendata.s3.amazonaws.com/metadata/" + self.name + ".json") if role == "article-version-metadata" else self.record["xml_url"].replace("s3://pmc-oa-opendata/", "https://pmc-oa-opendata.s3.amazonaws.com/")
        digest = hashlib.sha256(raw).hexdigest()
        return {"source_id": "L02", "artifact_type": role, "title": "Synthetic article",
            "pmcid": "PMC90001", "article_version": version, "doi": "10.1234/synthetic", "licence": "CC BY",
            "local_path": path.relative_to(self.root).as_posix(), "sha256": digest, "bytes": len(raw),
            "origin_url": origin, "final_url": origin, "retrieved_utc": "2026-10-04T12:00:00Z",
            "status": "acquired-unreviewed", "processing_scope": "OA licence recorded; operation-specific eligibility pending",
            "topics": [{"topic_id": "transplant"}],
            "acquisition_provenance": [{"source_id": "L02", "artifact_type": role, "sha256": digest,
                "manifest": "synthetic-manifest.jsonl", "line": 1, "status": "acquired-unreviewed"}]}

    def write(self):
        path = self.root / MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(x) for x in self.items) + "\n", encoding="utf-8")

    def change_record(self, **patch):
        self.record.update(patch)
        self.meta.write_text(json.dumps(self.record), encoding="utf-8")
        self.items[1] = self.receipt(self.meta, "article-version-metadata", 1)
        self.write()

    def register(self, repository):
        self.write()
        collection = CollectionCatalogue(repository, self.root)
        collection.register(source_id="L02")
        entries = collection.list()["entries"]
        self.selected = [e["id"] for e in entries if "acquired-jats" in e["metadata"]["asset_role"]]
        return collection


@pytest.fixture
def case(tmp_path):
    return Case(tmp_path / "collection")


@pytest.mark.parametrize("licence", ["CC BY-NC", "CC BY-ND", "CC BY-SA", "CC BY-NC-ND", "TDM", "unknown"])
def test_manifest_negative_licences_never_promote_even_with_booleans(repository, case, licence):
    case.items[0]["licence"] = licence
    case.items[0]["processing_scope"] = {x: True for x in ("display", "cache", "index", "embedding", "model_input")}
    collection = case.register(repository)
    result = collection.import_selected(case.selected)
    assert result["queued"] == 0
    assert repository.list_documents()["documents"] == []
    assert not any(e["rights"]["index"] for e in collection.list()["entries"])


@pytest.mark.parametrize("url", ["https://creativecommons.org/licenses/by-nc/4.0/",
    "https://creativecommons.org/licenses/by-nd/4.0/", "https://creativecommons.org/licenses/by-sa/4.0/",
    "https://creativecommons.org.evil.invalid/licenses/by/4.0/",
    "https://creativecommons.org/licenses/by/4.0/?permission=true", "https://creativecommons.org/licenses/by/4.0/deed.en", ""])
def test_jats_licence_url_must_pass_existing_strict_route(repository, tmp_path, url):
    case = Case(tmp_path / "collection", jats(url=url))
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["code"] == "article_permission_required"
    assert repository.list_documents()["documents"] == []


@pytest.mark.parametrize("version", ["2.0", "3.0", "4.0", "zero"])
def test_only_explicit_by_2_3_4_and_cc0_route_is_accepted(repository, tmp_path, version):
    url = "https://creativecommons.org/publicdomain/zero/1.0/" if version == "zero" else f"https://creativecommons.org/licenses/by/{version}/"
    case = Case(tmp_path / "collection", jats(url=url))
    if version == "zero":
        case.change_record(license_code="CC0")
        for item in case.items:
            item["licence"] = "CC0"
    collection = case.register(repository)
    result = collection.import_selected(case.selected)
    assert result["queued"] == 1
    revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (result["results"][0]["revision_id"],))
    assert revision["status"] == "queued"


@pytest.mark.parametrize("patch,code", [
    ({"is_retracted": True}, "article_retraction_unavailable"),
    ({"is_retracted": None}, "article_retraction_unavailable"),
    ({"is_retracted": "false"}, "article_retraction_unavailable"),
    ({"is_manuscript": True}, "article_oa_version_required"),
    ({"is_pmc_openaccess": False}, "article_oa_version_required"),
    ({"is_historical_ocr": None}, "article_oa_version_required"),
    ({"version": 2}, "article_identity_mismatch"),
    ({"pmcid": "PMC90002"}, "article_identity_mismatch"),
    ({"doi": "10.1234/other"}, "article_identity_mismatch"),
    ({"license_code": "CC BY-NC"}, "article_permission_required"),
    ({"xml_url": "https://example.invalid/PMC90001.1.xml"}, "article_origin_invalid"),
])
def test_exact_version_metadata_required(repository, case, patch, code):
    case.change_record(**patch)
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["code"] == code
    assert repository.list_documents()["documents"] == []
    inspected = next(entry for entry in collection.list()["entries"] if entry["id"] == case.selected[0])
    assert code in inspected["metadata"]["notes"][-1]


@pytest.mark.parametrize("change,code", [("jats_hash", "source_hash_changed"), ("metadata_hash", "source_hash_changed"),
    ("publisher_hash", "article_publisher_hash_changed"), ("provenance", "article_provenance_required"),
    ("permissions", "article_permission_required"), ("version_bool", "article_version_invalid")])
def test_integrity_and_explicit_restrictions(repository, case, change, code):
    if change == "jats_hash":
        case.xml.write_bytes(case.xml.read_bytes() + b" ")
    elif change == "metadata_hash":
        case.meta.write_bytes(case.meta.read_bytes() + b" ")
    elif change == "publisher_hash":
        case.xml.write_bytes(case.xml.read_bytes() + b" ")
        case.items[0] = case.receipt(case.xml, "fulltext-jats", 1)
    elif change == "provenance":
        case.items[0]["acquisition_provenance"] = []
    elif change == "permissions":
        case.items[0]["processing_scope"] = {"embedding": False}
    else:
        case.items[0]["article_version"] = True
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["code"] == code
    assert repository.list_documents()["documents"] == []


@pytest.mark.parametrize("value", ["../outside.xml", "raw/../outside.xml", "raw/file.xml:secret", "file.xml:secret", "C:relative.xml", r"\\server\share\body.xml"])
def test_unsafe_windows_collection_paths(tmp_path, value):
    with pytest.raises(ApiError) as raised:
        collection_path(tmp_path, value, must_exist=False)
    assert raised.value.code == "collection_path_invalid"


@pytest.mark.parametrize("kwargs,code", [({"pmcid": "PMC90002"}, "article_identity_mismatch"),
    ({"article_type": "retracted-article"}, "article_retracted"),
    ({"statement": "Third-party content is excluded"}, "article_permission_required"),
    ({"extra_license": '<license><license-p>Other licence</license-p></license>'}, "article_permission_required")])
def test_jats_identity_retraction_and_ambiguous_permissions(repository, tmp_path, kwargs, code):
    case = Case(tmp_path / "collection", jats(**kwargs))
    collection = case.register(repository)
    assert collection.import_selected(case.selected)["results"][0]["code"] == code


def test_explicit_licence_version_conflict_and_entity_payload(repository, case):
    case.items[0]["licence"] = "CC-BY-3.0"
    collection = case.register(repository)
    assert collection.import_selected(case.selected)["results"][0]["code"] == "article_permission_required"
    case.xml.write_bytes(b'<!DOCTYPE article [<!ENTITY patient SYSTEM "file:///C:/private/patient.txt">]><article>&patient;</article>')
    case.record["xml_url"] = case.record["xml_url"].split("?")[0] + "?md5=" + hashlib.md5(case.xml.read_bytes()).hexdigest()
    case.change_record()
    case.items[0] = case.receipt(case.xml, "fulltext-jats", 1)
    collection = case.register(repository)
    assert collection.import_selected(case.selected)["results"][0]["code"] == "article_xml_invalid"


def test_manifest_metadata_missing_and_stale_catalogue_receipt_fail_without_import(repository, case):
    collection = case.register(repository)
    case.items.pop()
    case.write()
    assert collection.import_selected(case.selected)["results"][0]["code"] == "article_metadata_required"
    case.items[0]["sha256"] = "0" * 64
    case.write()
    collection.register()
    # Refresh restores an inspectable row; changing it afterwards is rejected.
    case.items[0]["sha256"] = "1" * 64
    case.write()
    assert collection.import_selected(case.selected)["results"][0]["code"] == "catalogue_receipt_changed"
    assert repository.list_documents()["documents"] == []


def test_same_text_in_different_versions_is_not_collapsed(repository, tmp_path):
    case = Case(tmp_path / "collection")
    second = Case(case.root, version=2)
    case.items.extend(second.items)
    collection = case.register(repository)
    results = collection.import_selected(case.selected)["results"]
    assert len({r["document_id"] for r in results}) == 2
    assert len(repository.list_documents()["documents"]) == 2


def test_updated_receipt_for_same_version_replaces_one_document(repository, case):
    collection = case.register(repository)
    first = collection.import_selected(case.selected)["results"][0]
    case.xml.write_bytes(case.xml.read_bytes().replace(b"Review renal", b"Updated review of renal"))
    case.record["xml_url"] = case.record["xml_url"].split("?")[0] + "?md5=" + hashlib.md5(case.xml.read_bytes()).hexdigest()
    case.change_record()
    case.items[0] = case.receipt(case.xml, "fulltext-jats", 1)
    collection = case.register(repository)
    changed = collection.import_selected(case.selected)["results"][0]
    assert changed["document_id"] == first["document_id"]
    assert changed["revision_id"] != first["revision_id"]
    assert repository.get_job(first["job"]["id"])["state"] == "cancelled"
    assert len(repository.list_documents()["documents"]) == 1


def test_changed_permission_evidence_revises_same_document_even_when_prose_is_unchanged(repository, case):
    collection = case.register(repository)
    first = collection.import_selected(case.selected)["results"][0]
    case.change_record(citation="Synthetic updated source metadata")
    collection = case.register(repository)
    second = collection.import_selected(case.selected)["results"][0]
    assert first["document_id"] == second["document_id"] and first["revision_id"] != second["revision_id"]
    rows = repository.db.fetch_all("SELECT sha256 FROM knowledge_revisions WHERE document_id=?", (first["document_id"],))
    assert len(rows) == 2 and rows[0]["sha256"] == rows[1]["sha256"]


def test_ambiguous_duplicate_metadata_fields_are_unavailable(repository, case):
    raw = case.meta.read_text().replace('"is_retracted": false', '"is_retracted": true, "is_retracted": false')
    case.meta.write_text(raw, encoding="utf-8")
    case.items[1] = case.receipt(case.meta, "article-version-metadata", 1)
    collection = case.register(repository)
    assert collection.import_selected(case.selected)["results"][0]["code"] == "article_metadata_invalid"


@pytest.mark.parametrize("changes,code", [
    ({"retracted": True}, "article_status_unavailable"),
    ({"repository_removed": True}, "article_status_unavailable"),
    ({"superseded": True}, "article_status_unavailable"),
    ({"access_changed": True}, "article_status_unavailable")])
def test_existing_source_journal_restrictions_override_version_receipts(repository, case, changes, code):
    repository.update_source_status({"contract_version": 1, "event_id": "synthetic-review", "source_id": "L02",
        "identity": {"pmcid": "PMC90001"}, "changes": changes, "evidence": [{"inspected": True}]})
    collection = case.register(repository)
    assert collection.import_selected(case.selected)["results"][0]["code"] == code
    assert repository.list_documents()["documents"] == []


def test_metadata_first_selection_excludes_alternates_media_reserved_and_unrelated_bodies(repository, case, monkeypatch):
    for role in ("fulltext-text", "fulltext-pdf", "article-media-or-supplement", "public_route_response"):
        path = case.xml.parent / (role + ".txt")
        path.write_text("UNRELATED_PRIVATE_SENTINEL")
        item = case.receipt(path, role, 1)
        item["processing_scope"] = {x: True for x in ("display", "cache", "index", "embedding")}
        case.items.append(item)
    reserved = {**case.items[0], "source_id": "E02", "reserved": True}
    case.items.append(reserved)
    allowed = {(case.root / MANIFEST).resolve()}
    opened, original_open = [], Path.open
    def guarded(path, *args, **kwargs):
        resolved = path.resolve()
        if resolved.is_relative_to(case.root):
            opened.append(resolved)
            assert resolved in allowed, "Only the manifest and explicitly matched selections may be read"
        return original_open(path, *args, **kwargs)
    case.write()
    monkeypatch.setattr(Path, "open", guarded)
    collection = CollectionCatalogue(repository, case.root)
    preview = collection.preview()
    assert preview["eligible"] == 0
    assert set(opened) == allowed
    collection.register()
    entries = collection.list()["entries"]
    selected = [e["id"] for e in entries if e["eligibility"] == "inspection_required"]
    allowed.update({case.xml.resolve(), case.meta.resolve()})
    result = collection.import_selected([e["id"] for e in entries])
    assert result["queued"] == 1
    assert len(repository.list_documents()["documents"]) == 1
    assert {r["entry_id"] for r in result["results"] if r["status"] == "queued"} == set(selected)


def test_alternate_jats_dedup_restart_retry_and_original_preservation(repository, case):
    alternate = case.xml.with_name("alternate.xml")
    alternate.write_bytes(case.xml.read_bytes())
    case.items.append(case.receipt(alternate, "fulltext-jats", 1))
    collection = case.register(repository)
    first_batch = collection.import_selected(case.selected)
    assert first_batch["queued"] == 1
    first = first_batch["results"]
    assert len({r["job"]["id"] for r in first}) == 1
    assert len(repository.list_documents()["documents"]) == 1
    repository.db.execute("UPDATE knowledge_catalogue SET document_id=NULL,job_id=NULL")
    collection = CollectionCatalogue(repository, case.root)
    resumed = collection.import_selected(case.selected)["results"][0]
    assert resumed["job"]["id"] == first[0]["job"]["id"]
    repository.cancel_job(resumed["job"]["id"])
    retry = collection.import_selected(case.selected)["results"][0]
    assert retry["document_id"] == first[0]["document_id"]
    assert retry["job"]["id"] != resumed["job"]["id"]
    class FailOnce(SyntheticExtractor):
        def extract_file(self, *args):
            raise ApiError("synthetic_failure", "Synthetic queue failure", 422)
    repository.extractor = FailOnce()
    repository.run_job(retry["job"]["id"])
    assert repository.get_job(retry["job"]["id"])["state"] == "failed"
    successful = collection.import_selected(case.selected)["results"][0]
    assert successful["document_id"] == first[0]["document_id"]
    repository.extractor = SyntheticExtractor()
    repository.run_job(successful["job"]["id"])
    assert collection.import_selected(case.selected)["results"][0]["job"]["id"] == successful["job"]["id"]
    assert case.xml.read_bytes() == alternate.read_bytes() == jats()


def test_selected_locked_artifact_is_an_explained_batch_failure(repository, case, monkeypatch):
    collection = case.register(repository)
    original = Path.open
    def locked(path, *args, **kwargs):
        if path == case.meta:
            raise PermissionError("Synthetic Windows file lock")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", locked)
    assert collection.import_selected(case.selected)["results"][0]["code"] == "article_file_unavailable"
    assert repository.list_documents()["documents"] == []


def test_real_knowledge_durable_queue_seam_and_canonical_provenance(repository, case):
    collection = case.register(repository)
    result = collection.import_selected(case.selected)["results"][0]
    assert result["status"] == "queued"
    assert repository.retrieve("transplant", scope=ContextScope(kind=Scope.STUDY))["passages"] == []
    worker = IngestionWorker(repository)
    try:
        worker.start()
        deadline = time.monotonic() + 15
        while repository.get_job(result["job"]["id"])["state"] not in ("ready", "failed") and time.monotonic() < deadline:
            time.sleep(0.05)
        assert repository.get_job(result["job"]["id"])["state"] == "ready"
        revision = repository.db.fetch_one("SELECT * FROM knowledge_revisions WHERE id=?", (result["revision_id"],))
        derivative = Path(revision["original_path"]).read_bytes()
        assert b"SENTINEL" not in derivative
        metadata, rights = json.loads(revision["metadata_json"]), json.loads(revision["rights_json"])
        evidence = json.loads(next(n[len(EVIDENCE_PREFIX):] for n in metadata["notes"] if n.startswith(EVIDENCE_PREFIX)))
        assert revision["sha256"] == hashlib.sha256(derivative).hexdigest() == evidence["derivative_sha256"]
        assert evidence["original_sha256"] == hashlib.sha256(case.xml.read_bytes()).hexdigest()
        assert metadata["original_sha256"] == evidence["original_sha256"] != revision["sha256"]
        assert evidence["metadata_sha256"] == hashlib.sha256(case.meta.read_bytes()).hexdigest()
        assert metadata["edition"] == "PMC90001.1" and metadata["pmcid"] == "PMC90001"
        assert metadata["publication_status"] == "unknown" and not metadata["latest_final_verified"] and not metadata["content_reviewed"]
        assert "Alex Learner" in rights["attribution"] and "original JATS unchanged" in rights["attribution"]
        assert rights["model_input"] and rights["derivation"] and not rights["redistribution"]
        assert repository.retrieve("transplant rejection", scope=ContextScope(kind=Scope.STUDY))["passages"]
        assert not repository.retrieve("transplant", scope=ContextScope(kind=Scope.STUDY), current_only=True)["passages"]
    finally:
        worker.stop()
