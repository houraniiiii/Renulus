# SPDX-License-Identifier: MIT
"""H02 public Library adapter, with real offline FastEmbed/LanceDB."""
import os
import asyncio
from pathlib import Path
import socket
import ipaddress
from threading import Event

import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.knowledge.models import SourceMetadata
from renulus.knowledge.repository import KnowledgeRepository
from renulus.runtime.helpers import HelperAssets
from renulus.services import Services
from renulus.storage import AppPaths, Database
from renulus.runtime.harness_library import HarnessLibrary, LibraryAuthority
from renulus.assessment.attempt_models import HelpRequest, SaveDraft, StartAttempt
from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.study_help import StudyHelpContext, require_context_in


@pytest.fixture(scope="module")
def library(tmp_path_factory):
    root = tmp_path_factory.mktemp("h02-library")
    assets = Path(os.environ["RENULUS_LIBRARY_HELPERS"]).resolve()
    # Junction only public, hash-validated CPU assets; never a private profile.
    import subprocess
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{assets}' | Out-Null"], check=True)
    paths = AppPaths.create(root)
    db = Database(paths.database)
    schema = Path(__file__).resolve().parents[2] / "runtime/renulus/knowledge/schema.sql"
    db.apply_migration("knowledge-001", schema.read_text())
    for migration in sorted((schema.parent / "migrations").glob("*.sql")):
        db.apply_migration("knowledge-" + migration.stem, migration.read_text())
    services = Services(paths, db)
    services.registry["helpers"] = HelperAssets(paths)
    with pytest.MonkeyPatch.context() as patch:
        original = socket.socket.connect
        original_ex = socket.socket.connect_ex
        def offline(method):
            def connect(sock, address):
                if isinstance(address, tuple) and ipaddress.ip_address(address[0]).is_loopback:
                    return method(sock, address)
                raise AssertionError("H02 proof forbids external network access")
            return connect
        patch.setattr(socket.socket, "connect", offline(original))
        patch.setattr(socket.socket, "connect_ex", offline(original_ex))
        repo = KnowledgeRepository(services)
        yield repo, HarnessLibrary(repo)
    services.registry["helpers"].startup.close()


def authority(*revisions, cancelled=None, guard=None, record_dependencies=None, policy_revision=1, context_epoch=0, **options):
    return LibraryAuthority(scope=ContextScope(kind=Scope.STUDY),
        revision_ids=tuple(revisions), policy_revision=policy_revision, context_epoch=context_epoch,
        cancelled=(cancelled or Event()).is_set, guard=guard or (lambda conn: None),
        record_dependencies=record_dependencies or (lambda dependencies: None), **options)


def note(repo, text, **options):
    result = repo.import_text(text, scope=ContextScope(kind=Scope.LIBRARY), **options)
    assert result["status"] == "ready", result
    return result


def test_retrieves_real_passage_in_host_revision_scope_and_opens_exact_citation(library):
    repo, adapter = library
    source = note(repo, "Synthetic dialysis access surveillance assesses fistula flow and stenosis.")
    note(repo, "Excluded synthetic transplant rejection biopsy context.")
    trusted = authority(source["revision_id"])
    result = adapter.retrieve({"query": "fistula stenosis", "limit": 2}, trusted)
    assert result["status"] == "ready"
    assert len(result["passages"]) == 1
    passage = result["passages"][0]
    assert passage["text"] == "Synthetic dialysis access surveillance assesses fistula flow and stenosis."
    assert passage["document_revision"] == source["revision_id"]
    assert passage["id"].startswith("passage_")
    assert passage["locators"] == [{"item_ref": "#/texts/0", "page": None, "char_span": [0, 74]}]
    citation = adapter.open_citation({"document_id": source["document_id"],
        "document_revision": source["revision_id"], "passage_id": passage["id"]}, trusted)
    assert citation["locators"] == passage["locators"]
    assert citation["passage_id"] == passage["id"]
    assert citation["original_url"] == passage["original_url"]
    assert "passage_id=" + passage["id"] in citation["viewer_url"]


def test_cancelled_operation_cannot_read_even_an_empty_source_scope(library):
    _, adapter = library
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "glomerular hematuria"}, authority(cancelled=cancelled))
    assert caught.value.code == "harness_tool_cancelled"


def status_event(doi, **changes):
    return {"contract_version": 1, "event_id": "notice-" + doi, "source_id": "L02",
        "identity": {"doi": doi}, "changes": changes, "scope": {},
        "evidence": [{"url": "https://example.org/notice", "locator": "Synthetic notice",
            "finding": "Synthetic source eligibility change", "checked_on": "2026-10-11", "inspected": True}],
        "reason": "Synthetic adapter check"}


def test_revoked_source_between_search_and_return_cannot_be_disclosed(library):
    repo, adapter = library
    doi = "10.1234/h02-return"
    source = note(repo, "Synthetic transplantation rejection uses biopsy and clinical context.",
        metadata=SourceMetadata(source_id="L02", doi=doi))
    checks = []
    def guard(conn):
        checks.append(True)
        if len(checks) == 2:
            repo.update_source_status(status_event(doi, retracted=True))
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "transplantation rejection"},
            authority(source["revision_id"], guard=guard))
    assert caught.value.code == "harness_sources_changed"


def test_citation_cannot_cross_the_host_source_revision_set(library):
    repo, adapter = library
    allowed = note(repo, "Synthetic CKD permitted source.")
    excluded = note(repo, "Synthetic glomerular excluded source.")
    passage = repo.retrieve("glomerular", scope=ContextScope(kind=Scope.STUDY),
        revision_ids=[excluded["revision_id"]])["passages"][0]
    with pytest.raises(ApiError) as caught:
        adapter.open_citation({"document_id": excluded["document_id"],
            "document_revision": excluded["revision_id"], "passage_id": passage["id"]},
            authority(allowed["revision_id"]))
    assert caught.value.code == "harness_sources_changed"


@pytest.mark.parametrize("options,code", [
    ({"policy_revision": 99}, "assistance_changed"),
    ({"context_epoch": 99}, "dependency_changed"),
])
def test_stale_host_admission_blocks_retrieval(library, options, code):
    _, adapter = library
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "glomerular hematuria"}, authority(**options))
    assert caught.value.code == code


@pytest.mark.parametrize("at_check", [1, 2])
def test_cancellation_at_a_callback_prevents_read_or_return(library, at_check):
    repo, adapter = library
    source = note(repo, "Synthetic glomerular hematuria and proteinuria teaching.")
    cancelled, checks = Event(), []
    def guard(conn):
        checks.append(True)
        if len(checks) == at_check:
            cancelled.set()
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "glomerular hematuria"},
            authority(source["revision_id"], cancelled=cancelled, guard=guard))
    assert caught.value.code == "harness_tool_cancelled"


@pytest.mark.parametrize("change", ["superseded", "expired", "deleted", "revised"])
def test_publication_rechecks_canonical_source_eligibility_in_its_transaction(library, change):
    repo, adapter = library
    doi = "10.1234/h02-publication-" + change
    source = note(repo, "Synthetic CKD albuminuria teaching.",
        metadata=SourceMetadata(source_id="L02", doi=doi, publication_status="final",
            latest_final_verified=True, content_reviewed=True, review_due="2999-12-31"))
    trusted = authority(source["revision_id"], current_only=True)
    result = adapter.retrieve({"query": "CKD albuminuria"}, trusted)
    assert len(result["passages"]) == 1
    if change == "deleted":
        repo.delete_document(source["document_id"])
    elif change == "revised":
        note(repo, "Synthetic corrected CKD source.", document_id=source["document_id"],
            metadata=SourceMetadata(source_id="L02", doi=doi))
    else:
        repo.update_source_status(status_event(doi, **({"superseded": True} if change == "superseded"
            else {"review_due": "2000-01-01"})))
    with pytest.raises(ApiError) as caught:
        with repo.db.transaction() as conn:
            adapter.validate_publication(result["passages"], trusted, conn=conn)
    assert caught.value.code == "harness_sources_changed"


@pytest.mark.parametrize("arguments", [
    {"query": "CKD", "scope": {"kind": "personal-library"}},
    {"query": "CKD", "revision_ids": ["ungranted"]},
    {"query": "CKD", "toolkit": ["shell"]},
    {"query": "CKD", "limit": 50}, {"query": "CKD", "limit": "2"},
    {"query": " "},
])
def test_model_payload_cannot_change_authority_or_retrieval_bounds(library, arguments):
    _, adapter = library
    with pytest.raises(ApiError) as caught:
        adapter.retrieve(arguments, authority())
    assert caught.value.code == "invalid_library_arguments"


async def test_cancelled_async_execute_retains_cpu_thread_until_actual_settlement(library):
    repo, adapter = library
    source = note(repo, "Synthetic dialysis access flow teaching for cancellation.")
    started, release, settled = Event(), Event(), Event()
    original = repo.embedder
    class GatedCPU:
        def embed(self, texts, *, query=False):
            started.set()
            assert release.wait(10), "Release the synthetic CPU gate"
            try:
                return original.embed(texts, query=query)
            finally:
                settled.set()
    repo.embedder = GatedCPU()
    task = asyncio.create_task(adapter.execute("library.retrieve", {"query": "dialysis flow"},
        authority(source["revision_id"])))
    try:
        assert await asyncio.to_thread(started.wait, 5), "The actual CPU read should start"
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done(), "Cancellation must retain the running CPU worker"
        assert not settled.is_set()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert settled.is_set()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        repo.embedder = original


def test_retrieval_and_citation_record_exact_references_through_trusted_callback(library):
    repo, adapter = library
    source = note(repo, "Synthetic electrolyte hyponatremia evidence with exact provenance.")
    consumed = []
    trusted = authority(source["revision_id"], record_dependencies=consumed.extend)
    result = adapter.retrieve({"query": "hyponatremia"}, trusted)
    passage = result["passages"][0]
    expected = {"document_id": source["document_id"], "document_revision": source["revision_id"],
        "passage_id": passage["id"],
        "locators": [{"item_ref": "#/texts/0", "page": None, "char_span": [0, 66]}]}
    assert consumed == [expected]
    adapter.open_citation({key: expected[key] for key in ("document_id", "document_revision", "passage_id")}, trusted)
    assert consumed == [expected, expected]


@pytest.mark.parametrize("change", ["cancel", "revoke"])
def test_dependency_callback_cannot_allow_late_cancelled_or_revoked_result(library, change):
    repo, adapter = library
    doi = "10.1234/h02-record-" + change
    source = note(repo, "Synthetic glomerular source checked after dependency recording.",
        metadata=SourceMetadata(source_id="L02", doi=doi))
    cancelled = Event()
    def record(dependencies):
        if change == "cancel":
            cancelled.set()
        else:
            repo.update_source_status(status_event(doi, access_changed=True))
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "glomerular"}, authority(source["revision_id"],
            cancelled=cancelled, record_dependencies=record))
    assert caught.value.code == ("harness_tool_cancelled" if change == "cancel" else "harness_sources_changed")


@pytest.mark.parametrize("extra", [{"scope": {"kind": "personal-library"}}, {"page": True},
    {"page": "2"}, {"page": 301}, {"page": None}, {"passage_id": "forged"}])
def test_python_citation_rejects_model_authority_and_invalid_locations(library, extra):
    _, adapter = library
    arguments = {"document_id": "doc_" + "1" * 32, "document_revision": "rev_" + "1" * 32,
        "passage_id": "passage_" + "1" * 32, **extra}
    with pytest.raises(ApiError) as caught:
        adapter.open_citation(arguments, authority())
    assert caught.value.code == "invalid_library_arguments"


def test_python_admission_captures_scope_and_revision_pins(library):
    repo, adapter = library
    source = note(repo, "Synthetic PKD permitted scope evidence.")
    excluded = note(repo, "Synthetic PKD excluded scope evidence.")
    scope = ContextScope(kind=Scope.STUDY)
    revisions = [source["revision_id"]]
    trusted = LibraryAuthority(scope=scope, revision_ids=revisions, policy_revision=1, context_epoch=0,
        cancelled=lambda: False, guard=lambda conn: None, record_dependencies=lambda dependencies: None)
    scope.entity_id = "ungranted-context"
    revisions.append(excluded["revision_id"])
    assert trusted.scope.entity_id is None
    result = adapter.retrieve({"query": "PKD"}, trusted)
    assert [passage["document_revision"] for passage in result["passages"]] == [source["revision_id"]]


@pytest.mark.parametrize("callback", ["guard", "record_dependencies"])
def test_unawaited_owner_callback_cannot_admit_a_library_result(library, callback):
    _, adapter = library
    async def asynchronous(_):
        raise AssertionError("The adapter must reject an asynchronous owner callback")
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "CKD"}, authority(**{callback: asynchronous}))
    assert caught.value.code == "invalid_library_authority"


def test_non_study_authority_is_rejected_before_library_read_or_owner_callback(library):
    _, adapter = library
    checks = []
    with pytest.raises(ApiError) as caught:
        trusted = LibraryAuthority(scope=ContextScope(kind=Scope.LIBRARY), revision_ids=(),
            policy_revision=1, context_epoch=0, cancelled=lambda: False,
            guard=lambda conn: checks.append(True), record_dependencies=lambda dependencies: None)
        adapter.retrieve({"query": "CKD"}, trusted)
    assert caught.value.code == "invalid_library_authority"
    assert checks == []


@pytest.fixture
def assessment(tmp_path):
    app = create_app(tmp_path / "assessment-profile")
    services = app.state.services
    version = SavedTestVersion(id="h02_version", test_id="h02_test", ordinal=1, origin="imported",
        review_quality="personal", status="ready", provenance={"method": "import"}, created_at=utc_now(),
        terms="Synthetic owned educational fixture", items=[QuestionSnapshot(item_id="h02_item",
            question_id="h02_question", question_version="1", key_version="1", family_id="h02_family",
            family_version="1", topic_id="general", stem="Which synthetic statement is suitable?",
            options=[{"id": "a", "text": "First statement"}, {"id": "b", "text": "Second statement"}],
            correct_option_ids=["a"], explanation="Synthetic private answer key")])
    with services.db.transaction() as conn:
        services.get("saved_tests").publish_version(conn, version, title="Synthetic H02 assessment",
            provenance={"schema": "saved-test-provenance/1"}, idempotency_key="h02-create-version")
    return services, HarnessLibrary(services.get("knowledge"))


def start_assessment(services, mode):
    return services.get("whole_attempts").start(StartAttempt(
        version={"type": "saved_test_version", "id": "h02_version"}, mode=mode), "h02-start-" + mode)


@pytest.mark.parametrize("phase", ["read", "return", "publication"])
def test_real_active_test_blocks_adapter_read_return_and_publication(assessment, phase):
    services, adapter = assessment
    calls = []
    def guard(conn):
        calls.append(True)
        if phase == "return" and len(calls) == 2:
            start_assessment(services, "test")
    trusted = authority(guard=guard)
    if phase != "return":
        start_assessment(services, "test")
    with pytest.raises(ApiError) as caught:
        if phase == "publication":
            with services.db.transaction() as conn:
                adapter.validate_publication([], trusted, conn=conn)
        else:
            adapter.retrieve({"query": "CKD"}, trusted)
    assert caught.value.code == "assistance_restricted"


def test_active_test_started_during_owner_check_prevents_any_library_read(assessment, monkeypatch):
    services, adapter = assessment
    reads = []
    original = adapter.repository.retrieve
    def observe(*args, **options):
        reads.append(True)
        return original(*args, **options)
    monkeypatch.setattr(adapter.repository, "retrieve", observe)
    def guard(conn):
        start_assessment(services, "test")
    with pytest.raises(ApiError) as caught:
        adapter.retrieve({"query": "CKD"}, authority(guard=guard))
    assert caught.value.code == "assistance_restricted"
    assert reads == []


@pytest.mark.parametrize("phase", ["read", "return", "publication"])
def test_real_study_receipt_change_blocks_adapter_read_return_and_publication(assessment, phase):
    services, adapter = assessment
    attempt = start_assessment(services, "study")
    owner = services.get("whole_attempts")
    receipt = owner.help(attempt["id"], HelpRequest(expected_revision=attempt["draft_revision"],
        expected_policy_revision=attempt["policy"]["revision"], item_id="h02_item", kind="sources"), "h02-open-help")
    context = StudyHelpContext.model_validate(receipt["context"])
    def change():
        owner.save(attempt["id"], SaveDraft(expected_revision=attempt["draft_revision"], position=0,
            answers=[{"item_id": "h02_item", "option_ids": ["b"], "marked": False}]), "h02-change-draft")
    checks = []
    def guard(conn):
        checks.append(True)
        if phase == "return" and len(checks) == 2:
            change()
        require_context_in(services, conn, context)
    trusted = authority(guard=guard)
    if phase != "return":
        change()
    with pytest.raises(ApiError) as caught:
        if phase == "publication":
            with services.db.transaction() as conn:
                adapter.validate_publication([], trusted, conn=conn)
        else:
            adapter.retrieve({"query": "CKD"}, trusted)
    assert caught.value.code == "revision_conflict"


def test_cancelled_publication_and_missing_transaction_are_refused(library):
    repo, adapter = library
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ApiError) as caught:
        with repo.db.transaction() as conn:
            adapter.validate_publication([], authority(cancelled=cancelled), conn=conn)
    assert caught.value.code == "harness_tool_cancelled"
    with pytest.raises(ApiError) as caught:
        with repo.db.connect() as conn:
            adapter.validate_publication([], authority(), conn=conn)
    assert caught.value.code == "harness_publication_transaction_required"
