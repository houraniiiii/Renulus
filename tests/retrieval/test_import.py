import asyncio
import hashlib
from pathlib import Path

import httpx
import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.repository import KnowledgeRepository
from renulus.retrieval.literature import licensed_article
from renulus.retrieval.service import RetrievalService
from .conftest import SyntheticProtector
from .fixtures import PMCID, article, europe

LIBRARY = ContextScope(kind=Scope.LIBRARY)


class QueuedIndex:
    """Public path/remove contract; queued imports never call an inference engine."""
    def __init__(self, path):
        self.path = path
        self.removed = []

    def remove(self, revision_id):
        self.removed.append(revision_id)


def setup(services, *, metadata=None, raw=None):
    calls = []
    raw = article() if raw is None else raw
    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/search"):
            assert request.url.params["query"] == "PMCID:" + PMCID
            return httpx.Response(200, json=metadata or europe())
        assert request.url.path.endswith("/" + PMCID + "/fullTextXML")
        return httpx.Response(200, content=raw, headers={"Content-Type": "application/xml"})
    # Real original/rights/queue repository; no helper model is run by this route.
    knowledge = KnowledgeRepository(services, extractor=object(), embedder=object(),
                                    index=QueuedIndex(services.paths.indexes / "knowledge"))
    services.registry["knowledge"] = knowledge
    service = RetrievalService(services, transport=httpx.MockTransport(handler), protector=SyntheticProtector())
    return service, knowledge, calls


def test_real_library_import_exact_attribution_rights_queue_and_restart_replay(services):
    raw = article(body='<fig><p>EXCLUDED_FIGURE</p></fig><table-wrap><p>EXCLUDED_TABLE</p></table-wrap><disp-quote><p>EXCLUDED_QUOTATION</p></disp-quote><p specific-use="third-party">EXCLUDED_THIRD_PARTY</p>')
    service, knowledge, calls = setup(services, raw=raw, metadata=europe(commentCorrectionList={"commentCorrection": [{"type": "Erratum in", "source": "MED", "id": "10002"}]}))
    result = asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert result["import"]["status"] == "queued" and len(calls) == 2
    assert result["latest_final_verified"] is result["content_reviewed"] is False
    document = knowledge.get_document(result["import"]["document_id"])
    revision = document["revisions"][0]
    metadata, rights = revision["metadata"], revision["rights"]
    assert metadata["source_id"] == "L03" and metadata["source_owner"] == "Synthetic Press"
    assert metadata["topic_ids"] == ["T21"] and metadata["pmcid"] == PMCID
    assert metadata["doi"] == "10.0000/synthetic" and metadata["publication_date"] == "2026-09-01"
    assert metadata["publication_status"] == "unknown" and metadata["latest_final_verified"] is False
    assert '"type": "Erratum in"' in metadata["correction"] and '"id": "10002"' in metadata["correction"]
    assert "Europe PMC fullTextXML SHA256:" + hashlib.sha256(raw).hexdigest() in metadata["notes"]
    for operation in ("display", "cache", "index", "embedding", "model_input", "derivation"):
        assert rights[operation] is True
    assert rights["evaluation"] is rights["redistribution"] is False
    assert rights["licence"] == "CC-BY-4.0" and rights["permission_reference"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "Synthetic Author" in rights["attribution"] and "Copyright Synthetic Author 2026" in rights["attribution"]
    assert "formatting changed" in rights["attribution"]
    original = services.db.fetch_one("SELECT original_path FROM knowledge_revisions WHERE id=?", (revision["id"],))
    content = Path(original["original_path"]).read_text(encoding="utf-8")
    assert "\n\nResults\n\n" in content and "Kidney study paragraph" in content
    assert "EXCLUDED_" not in content
    assert services.db.fetch_all("SELECT * FROM knowledge_passages") == []
    binding = services.db.fetch_one("SELECT * FROM retrieval_imports")
    assert binding["key_hash"] == hashlib.sha256(b"synthetic_import").hexdigest()
    restarted = RetrievalService(services, transport=httpx.MockTransport(lambda request: pytest.fail("Replay must not use network")), protector=SyntheticProtector())
    replay = asyncio.run(restarted.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert replay["replayed"] is True and replay["import"] == result["import"]
    assert replay["article"] == result["article"] and len(knowledge.list_documents()["documents"]) == 1
    with pytest.raises(ApiError) as conflict:
        asyncio.run(restarted.import_article("T19", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert conflict.value.code == "idempotency_conflict"
    knowledge.delete_document(document["id"])
    assert knowledge.index.removed == [revision["id"]]
    assert not Path(original["original_path"]).exists()
    assert services.db.fetch_all("SELECT * FROM knowledge_cleanup") == []
    with pytest.raises(ApiError):
        asyncio.run(restarted.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert knowledge.list_documents()["documents"] == []


@pytest.mark.parametrize("scope", [Scope.STUDY, Scope.TEMPORARY_CASE, Scope.SAVED_CASE, Scope.UNCLASSIFIED])
def test_import_forbidden_scopes_do_not_touch_network_profile_or_ledger(services, scope):
    service, _, calls = setup(services)
    before = {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}
    with pytest.raises(ApiError) as error:
        asyncio.run(service.import_article("T21", PMCID, scope=ContextScope(kind=scope), idempotency_key="synthetic_import"))
    assert error.value.code == "retrieval_scope_blocked" and calls == []
    assert before == {str(path): path.read_bytes() for path in services.paths.root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("changes,error_code", [
    ({"license": "cc by-nc"}, "article_permission_required"),
    ({"isOpenAccess": "N"}, "article_permission_required"),
    ({"pubTypeList": {"pubType": ["Retracted Publication"]}}, "article_retracted"),
    ({"commentCorrectionList": {"commentCorrection": [{"type": "Retraction in", "id": "999", "source": "MED"}]}}, "article_retracted"),
])
def test_preflight_blocks_unlicensed_or_reported_retracted_before_fulltext(services, changes, error_code):
    service, knowledge, calls = setup(services, metadata=europe(**changes))
    with pytest.raises(ApiError) as error:
        asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert error.value.code == error_code and len(calls) == 1
    assert knowledge.list_documents()["documents"] == []


@pytest.mark.parametrize("licence", ["https://creativecommons.org/licenses/by-nc/4.0/", "https://creativecommons.org/licenses/by-nd/4.0/", "https://creativecommons.org/licenses/by-sa/4.0/", "https://creativecommons.org.evil.test/licenses/by/4.0/", "https://creativecommons.org/licenses/by/4.0/?grant=yes", "https://creativecommons.org:444/licenses/by/4.0/", "https://creativecommons.org/licenses/by/4.0/extra"])
def test_exact_licence_allowlist_rejects_restricted_and_spoofed_uris(licence):
    with pytest.raises(ApiError) as error:
        licensed_article(article(licence=licence), PMCID)
    assert error.value.code == "article_permission_required"


@pytest.mark.parametrize("licence,name", [("http://creativecommons.org/licenses/by/2.0", "CC-BY-2.0"), ("https://creativecommons.org/licenses/by/3.0/", "CC-BY-3.0"), ("https://creativecommons.org/publicdomain/zero/1.0/", "CC0-1.0")])
def test_explicit_supported_versions_and_nested_jats_link(licence, name):
    result = licensed_article(article(licence=licence), PMCID)
    assert result["licence"] == name and result["authors"] == ["Synthetic Author"]


def test_conflicting_exclusions_identity_and_entities_fail_closed():
    for raw, code in [
        (article(statement="Third-party material is excluded."), "article_permission_required"),
        (article(pmcid="PMC20002"), "article_identity_mismatch"),
        (article(article_type="retraction"), "article_retracted"),
        (article(attributes='xlink:href="https://creativecommons.org/licenses/by-nc/4.0/"'), "article_permission_required"),
        (b'<!DOCTYPE article [<!ENTITY e SYSTEM "file:///C:/private/patient.txt">]><article>&e;</article>', "article_xml_invalid"),
    ]:
        with pytest.raises(ApiError) as error:
            licensed_article(raw, PMCID)
        assert error.value.code == code


def test_metadata_ambiguity_and_xml_core_identifier_mismatch_do_not_import(services):
    metadata = europe()
    metadata["resultList"]["result"] *= 2
    service, knowledge, calls = setup(services, metadata=metadata)
    with pytest.raises(ApiError) as error:
        asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert error.value.code == "article_identity_mismatch" and len(calls) == 1
    service, knowledge, calls = setup(services, metadata=europe(doi="10.0000/other"))
    with pytest.raises(ApiError) as error:
        asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_second"))
    assert error.value.code == "article_identity_mismatch" and knowledge.list_documents()["documents"] == []


def test_resume_after_library_commit_before_replay_record_keeps_stable_request(services, monkeypatch):
    service, knowledge, calls = setup(services)
    execute = services.db.execute
    interrupted = [False]
    def fail_completion(sql, parameters=()):
        if "SET document_id=" in sql and not interrupted[0]:
            interrupted[0] = True
            raise RuntimeError("Synthetic interrupted acknowledgement")
        return execute(sql, parameters)
    monkeypatch.setattr(services.db, "execute", fail_completion)
    with pytest.raises(ApiError) as error:
        asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert error.value.code == "article_import_failed"
    assert len(knowledge.list_documents()["documents"]) == 1
    result = asyncio.run(service.import_article("T21", PMCID, scope=LIBRARY, idempotency_key="synthetic_import"))
    assert result["import"]["status"] == "queued" and len(knowledge.list_documents()["documents"]) == 1
    assert len(calls) == 4  # Only an unacknowledged first attempt refetches.
