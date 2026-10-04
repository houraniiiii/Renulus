import json
from pathlib import Path

import pytest

from renulus.contracts import ContextScope, Scope
from renulus.services import Services
from renulus.storage import AppPaths, Database, utc_now
from renulus.memory.repository import MemoryRepository

SOURCE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def services(tmp_path):
    paths = AppPaths.create(tmp_path / 'memory-profile', SOURCE_ROOT)
    services = Services(paths, Database(paths.database))
    # Only the test harness applies DDL; production registration does not.
    services.db.apply_migration('memory-001',
        (SOURCE_ROOT / 'runtime/renulus/memory/schema.sql').read_text(encoding='utf-8'))
    return services


@pytest.fixture
def repository(services):
    return MemoryRepository(services)


def evidence(services, identifier='evidence-1', *, text='Compare urinary sediment across glomerular disorders.',
             scope=None, kind='learning-point', topic='glomerular'):
    scope = scope or ContextScope(kind=Scope.STUDY, entity_id='study-1')
    payload = {'scope': scope.model_dump(mode='json'), 'general_learning': True, 'text': text}
    services.db.execute('INSERT INTO learning_evidence VALUES(?,?,?,?,?,?)',
        (identifier, kind, topic, scope.entity_id, json.dumps(payload), utc_now()))
    return scope
