"""Explicit synthetic ready Library rows, with real canonical local resolvers.

This uncomposed lane loads exact public parent sources for the supplied-conn
Library prerequisite. It never copies private state or invents a source digest.
"""
import importlib
import inspect
import subprocess
import sys
from types import ModuleType

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.design_c_contracts import Identity
from renulus.knowledge.repository import KnowledgeRepository
from renulus.memory.lineage import AnswerInputs


PARENT = '63457a15'


def parent_module(name, path, monkeypatch):
    source = subprocess.run(['git', 'show', PARENT + ':' + path],
        capture_output=True, text=True, check=True).stdout
    module = ModuleType(name)
    module.__file__ = PARENT + ':' + path
    module.__package__ = name.rpartition('.')[0]
    monkeypatch.setitem(sys.modules, name, module)
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


def source_fixture(services, monkeypatch):
    try:
        module = importlib.import_module('renulus.runtime.harness_library')
    except ModuleNotFoundError as error:
        if error.name != 'renulus.runtime.harness_library':
            raise
        module = parent_module('renulus.runtime.harness_library',
            'runtime/renulus/runtime/harness_library.py', monkeypatch)
    repository_type = KnowledgeRepository
    if 'conn' not in inspect.signature(repository_type.check_evidence).parameters:
        repository_type = parent_module('renulus.knowledge._h05_parent_repository',
            'runtime/renulus/knowledge/repository.py', monkeypatch).KnowledgeRepository
    services.db.apply_migration('legacy-source-test',
        (services.paths.source_root / 'runtime/renulus/knowledge/schema.sql').read_text(encoding='utf-8'))
    repository = repository_type(services)
    imported = repository.import_text('Synthetic canonical CKD source passage.', process=False,
        scope=ContextScope(kind=Scope.LIBRARY), idempotency_key='canonical-source')
    revision_id, document_id = imported['revision_id'], imported['document_id']
    passage_id = 'passage_' + '1' * 32
    with services.db.transaction() as conn:
        conn.execute("UPDATE knowledge_revisions SET status='ready' WHERE id=?", (revision_id,))
        conn.execute('UPDATE knowledge_documents SET active_revision=? WHERE id=?', (revision_id, document_id))
        conn.execute('INSERT INTO knowledge_passages VALUES(?,?,?,?,?,?,?)',
            (passage_id, revision_id, 0, 'Synthetic canonical CKD source passage.',
             'Synthetic canonical CKD source passage.', '[{"page":1}]', '[]'))
    citation = {'id': passage_id, 'document_id': document_id, 'document_revision': revision_id,
        'text': 'Synthetic canonical CKD source passage.', 'locators': [{'page': 1}]}
    library = module.HarnessLibrary(repository)
    services.registry['harness_library'] = library

    class SourceRetrieval:
        """Synthetic retrieval selection; eligibility is real canonical Library."""
        def retrieve(self, *args, **kwargs):
            return {'passages': [citation]}
        def check_evidence(self, *args, **kwargs):
            return repository.check_evidence(*args, **kwargs)

    services.registry['knowledge'] = SourceRetrieval()
    def authority():
        return module.LibraryAuthority(scope=ContextScope(kind=Scope.STUDY), revision_ids=None,
            policy_revision=1, context_epoch=0, cancelled=lambda: False,
            guard=lambda conn: None, record_dependencies=lambda items: None)
    with services.db.transaction() as conn:
        digest = library.resolve_dependency(conn, Identity(type='library_revision', id=revision_id),
            authority=authority())
    assert isinstance(digest, str) and len(digest) == 64

    class SyntheticIndependentSourceAdapter:
        """Trusted local eligibility for this independently authored synthetic note."""
        def resolve_dependency_in(self, conn, dependency, *, project_id, for_support):
            actual = library.resolve_dependency(conn, dependency.target, authority=authority())
            if actual is None or actual != dependency.expected_revision:
                raise ApiError('memory_dependency_revoked', 'Synthetic source receipt changed', 409)
            return AnswerInputs()

    return revision_id, digest, SyntheticIndependentSourceAdapter()
