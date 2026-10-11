"""Additive upgrade of a synthetic populated memory-001 profile."""
from pathlib import Path

import pytest

from renulus.memory.repository import MemoryRepository
from renulus.services import Services
from renulus.storage import AppPaths, Database, utc_now


def test_additive_upgrade_preserves_global_fact_and_the_applied_checksum(tmp_path):
    source = Path(__file__).resolve().parents[2]
    paths = AppPaths.create(tmp_path / 'legacy-memory-profile', source)
    db = Database(paths.database)
    original = (source / 'runtime/renulus/memory/schema.sql').read_text(encoding='utf-8')
    additive = (source / 'runtime/renulus/memory/migrations/002.sql').read_text(encoding='utf-8')
    db.apply_migration('memory-001', original)
    # Explicit trusted fixture for an existing canonical record before support
    # tables existed; no historical producer manifest is invented by upgrade.
    now = utc_now()
    db.execute('INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        ('memory_legacy', 'Synthetic retained global preference.', 'legacy-hash',
         'preference', 'dialysis', 'study', 3, 'manual', None, now, now))
    db.apply_migration('memory-002', additive)
    db.apply_migration('memory-002', additive)
    db.apply_migration('memory-001', original)
    with pytest.raises(RuntimeError, match='Applied migration changed'):
        db.apply_migration('memory-001', original + '\n-- forbidden checksum change')
    repository = MemoryRepository(Services(paths, db))
    fact = repository.get('memory_legacy')
    assert fact['text'] == 'Synthetic retained global preference.'
    assert fact['revision'] == 3 and fact['project_id'] is None
    assert fact['visibility'] == 'profile-global'
