# SPDX-License-Identifier: MIT
"""Legacy source closure over real canonical ports; no engines or network.

Extraction, vector selection and answer text are explicitly synthetic. Library
eligibility, completed-answer publication and derived Memory support are real.
"""
from pathlib import Path
import socket

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.design_c_contracts import Dependency, Identity
from renulus.knowledge.engines import Extracted
from renulus.knowledge.repository import KnowledgeRepository
from renulus.runtime.harness_library import HarnessLibrary, LibraryAuthority
from renulus.server import create_app
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in


ROOT = Path(__file__).resolve().parents[2]
NOTE = "Synthetic CKD exercise: compare albuminuria and kidney filtration trends."
QUESTION = "Explain this synthetic CKD learner preference."
STUDY = ContextScope(kind=Scope.STUDY)


class SyntheticExtractor:
    def extract_file(self, path, title):
        text = path.read_text(encoding="utf-8")
        return Extracted([{"text": text, "context_text": text, "headings": [],
            "locators": [{"page": None, "char_span": [0, len(text)],
                          "item_ref": "#/texts/0"}]}], {"synthetic": True})


class SyntheticVectors:
    model_id, max_tokens = "synthetic-legacy-context", 512

    def embed(self, texts, *, query=False):
        return [[1.0] for _ in texts]


class SyntheticIndex:
    def __init__(self, path):
        self.path = path
        path.mkdir(parents=True)

    def stage(self, rows, *, create_fts=False):
        pass

    def build_fts(self):
        pass

    def search(self, query, vector, revisions, limit):
        # The source is consumed by the declared seed publisher below. The
        # follow-up exercises its inherited Memory closure, not fresh retrieval.
        return []

    def remove(self, revision_id):
        pass


class SyntheticProvider:
    def __init__(self, db):
        self.db, self.calls = db, []

    async def stream(self, messages, **kwargs):
        # Public quiescence would refuse an active writer: validation must have
        # released its local transaction before advancing the async provider.
        with self.db.quiesce_writes():
            pass
        self.calls.append({"messages": messages, **kwargs})
        yield NOTE

    async def cancel(self, run_id):
        return True


@pytest.fixture
def legacy_source(tmp_path, monkeypatch):
    original = socket.socket.connect

    def loopback_only(sock, address):
        if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
            return original(sock, address)
        raise AssertionError("Legacy context proof forbids external network")

    monkeypatch.setattr(socket.socket, "connect", loopback_only)
    profile = tmp_path / "synthetic-legacy-library"
    app = create_app(profile, source_root=ROOT, collection_root=profile / "collection")
    services = app.state.services
    repository = KnowledgeRepository(services, extractor=SyntheticExtractor(),
        embedder=SyntheticVectors(), index=SyntheticIndex(services.paths.indexes / "synthetic"))
    imported = repository.import_text(NOTE, scope=ContextScope(kind=Scope.LIBRARY),
        idempotency_key="owned-source")
    assert imported["status"] == "ready", imported
    library = HarnessLibrary(repository)
    memory = services.get("memory")
    # Bind the actual persistent adapter before publishing any source closure.
    services.registry["harness_library"] = library
    memory.register_dependency_resolver("library_revision", library)
    services.registry["knowledge"] = repository
    provider = SyntheticProvider(services.db)
    services.registry["provider"] = provider
    monkeypatch.setattr(memory, "retrieve", lambda *args, **kwargs: {"records": []})
    with services.db.transaction() as conn:
        identity = Identity(type="library_revision", id=imported["revision_id"])
        digest = library.resolve_dependency(conn, identity, authority=LibraryAuthority(
            scope=STUDY, revision_ids=None, policy_revision=require_assistance(conn),
            context_epoch=context_epoch_in(conn), cancelled=lambda: False,
            guard=lambda snapshot: None, record_dependencies=lambda items: None))
    assert isinstance(digest, str) and len(digest) == 64
    dependency = Dependency(target=identity, expected_revision=digest)
    return services, repository, memory, provider, dependency, imported


async def retained_source_point(services, memory, dependency, monkeypatch):
    learn = services.get("learn")
    # This trusted synthetic producer consumes the imported note's exact text
    # as its declared input and pins its real canonical source at publication.
    question = "Explain this declared synthetic source: " + NOTE
    _, seed = learn.prepare(question, STUDY, None, "ckd", "direct", "seed-source")
    seed.publication = lambda conn: memory.publish_answer_lineage_in(conn,
        "learn-answer:" + seed.id, inputs=(), dependencies=(dependency,))
    flow = [event async for event in learn.answer(seed, question, "direct", "ckd")]
    assert flow[-1].type == "completed", flow[-1].payload
    scope = ContextScope(kind=Scope.STUDY, entity_id=seed.thread_id)
    job = memory.repository.enqueue("learn-answer:" + seed.id, scope)
    job = memory.repository.claim(job["id"])
    material = memory.repository.material(job["evidence_id"], scope)
    # Only extraction output is controlled; the public commit creates the real
    # source-linked support and completed job without Mem0/FastEmbed or SQL setup.
    identifiers = memory.repository.commit_capture(job, material, [NOTE])
    assert len(identifiers) == 1
    assert memory.repository.job(job["id"])["state"] == "completed"
    point = memory.repository.get(identifiers[0])
    monkeypatch.setattr(memory, "retrieve", lambda *args, **kwargs: {"records": [point]})
    return learn, point


@pytest.mark.asyncio
async def test_legacy_recall_completes_with_real_retained_library_support(legacy_source, monkeypatch):
    services, repository, memory, provider, dependency, imported = legacy_source
    try:
        learn, point = await retained_source_point(services, memory, dependency, monkeypatch)
        _, run = learn.prepare(QUESTION, STUDY, None, "ckd", "direct", "follow-up")
        flow = [event async for event in learn.answer(run, QUESTION, "direct", "ckd")]
        assert next(event for event in flow if event.type == "memory").payload["count"] == 1
        assert flow[-1].type == "completed", flow[-1].payload
        assert NOTE in provider.calls[-1]["system"]
        assert len(provider.calls) == 2
        assert learn.get_thread(run.thread_id)["runs"][0]["state"] == "completed"
        assert len(memory.eligible_history(learn.get_thread(run.thread_id)["messages"])[1]) == 1
    finally:
        await services.finish_shutdown()


@pytest.mark.asyncio
async def test_source_revocation_after_legacy_recall_refuses_before_dispatch(legacy_source, monkeypatch):
    services, repository, memory, provider, dependency, imported = legacy_source
    try:
        learn, point = await retained_source_point(services, memory, dependency, monkeypatch)
        _, run = learn.prepare(QUESTION, STUDY, None, "ckd", "direct", "revoked-follow-up")
        flow = []
        async for event in learn.answer(run, QUESTION, "direct", "ckd"):
            flow.append(event)
            if event.type == "memory":
                assert event.payload["count"] == 1
                assert repository.delete_document(imported["document_id"])["status"] == "deleted"
        assert flow[-1].type == "error"
        assert flow[-1].payload["code"] == "memory_dependency_revoked"
        assert len(provider.calls) == 1  # Only the completed seed dispatched.
        thread = learn.get_thread(run.thread_id)
        assert [message["role"] for message in thread["messages"]] == ["user"]
        assert thread["runs"][0]["state"] == "failed"
    finally:
        await services.finish_shutdown()
