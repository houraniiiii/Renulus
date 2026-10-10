# SPDX-License-Identifier: MIT
"""Actual committed schema1 and current producers; synthetic lane state only."""
import asyncio
import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from uuid import uuid4
import zipfile

import pytest

from renulus.server import create_app
from renulus.storage.backup import export_records
from renulus.storage.invalidation import context_epoch

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path('C:/Renulus/scratch/design-c/dc-review-data/dc20')
OLD_COMMIT = '1b30a89687cfcc5fb13b1cf824bbc43c19f870ed'
FIXTURES = REPO / 'packages/contracts/fixtures/design-c'
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aK1sAAAAASUVORK5CYII='
HISTORY_TABLES = ('learn_threads', 'learn_messages', 'learn_runs', 'case_sessions', 'case_attachments',
    'assessment_sessions', 'assessment_items', 'assessment_attempts',
    'assessment_exposure', 'assessment_generated_sessions', 'assessment_generated_items',
    'assessment_generated_attempts', 'memory_facts', 'memory_history', 'learning_evidence')


def child(root, runtime, source, *arguments, expected=0):
    # No account, API key, proxy or owner-profile environment is inherited.
    environment = {name: os.environ[name] for name in ('SystemRoot', 'WINDIR', 'PATH') if name in os.environ}
    environment.update(PYTHONPATH=str(runtime), PYTHONDONTWRITEBYTECODE='1', TEMP=str(root), TMP=str(root),
        USERPROFILE=str(root / 'home'), APPDATA=str(root / 'home/roaming'), LOCALAPPDATA=str(root / 'home/local'),
        HF_HOME=str(root / 'hf'), XDG_CACHE_HOME=str(root / 'cache'), HF_HUB_OFFLINE='1')
    result = subprocess.run([sys.executable, '-c', source, *map(str, arguments)], cwd=root, env=environment,
        capture_output=True, text=True, timeout=90)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


OLD_SEED = r'''
import base64, json, socket, sys
from pathlib import Path
from renulus.server import create_app
from renulus.knowledge.models import SourceMetadata, own_text_rights
from renulus.cases.models import StartCase
from renulus.cases.originals import accepted_original
from renulus.storage.backup import export_records

def forbidden(*args, **kwargs): raise AssertionError('Old upgrade seed forbids network and providers')
socket.socket.connect = socket.socket.connect_ex = forbidden
profile, fixture, png = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
services = create_app(profile).state.services
bundle = json.loads(fixture.read_text(encoding='utf-8'))
services.get('data_recovery').restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle['exported_at'])
services.get('learn').create_thread('SYNTHETIC populated upgrade dialysis', topic_id='T01')
path = profile / 'synthetic-old-source.txt'
path.write_text('SYNTHETIC legacy transplant original with preserved ownership.\n', encoding='utf-8')
document = services.get('knowledge').import_file(path, rights=own_text_rights(), metadata=SourceMetadata(), process=False)
case = services.get('cases').start(StartCase(text='SYNTHETIC legacy glomerular teaching case'))
original = accepted_original('synthetic-old.png', 'SYNTHETIC retained original', 'image/png', base64.b64decode(png))
case = services.get('cases').attach(case['id'], case['revision'], original)
case = services.get('cases').save(case['id'], case['revision'])
with services.db.connect() as conn: assert conn.execute('PRAGMA user_version').fetchone()[0] == 1
record = export_records(services)
(profile / 'legacy-export.json').write_text(json.dumps(record), encoding='utf-8')
for version in (1, 2):
    directory, manifest = services.get('data_recovery').backup(format_version=version)
    (profile / ('legacy-zip%d.zip' % version)).write_bytes((directory / 'backup.zip').read_bytes())
print(json.dumps({'profile': str(profile), 'schema': 1, 'case_id': case['id'],
    'attachment_id': original['id'], 'document_id': document['document_id'], 'revision_id': document['revision_id']}))
'''


@pytest.fixture(scope='module')
def legacy():
    root = SCRATCH / ('run-' + uuid4().hex[:10])
    root.mkdir(parents=True)
    archive = root / 'source.zip'
    subprocess.run(['git', 'archive', '--format=zip', '--output=' + str(archive), OLD_COMMIT,
        'runtime', 'content', 'upstream/hermes', 'packaging/runtime/helper-assets.json'], cwd=REPO, check=True, capture_output=True)
    source = root / 'old-source'
    with zipfile.ZipFile(archive) as selected:
        selected.extractall(source)
    manifest = json.loads((FIXTURES / 'fixture-manifest.json').read_text(encoding='utf-8'))
    for name in ('legacy-schema1-records.json', 'legacy-schema1-inventory.json'):
        data = (FIXTURES / name).read_bytes()
        assert len(data) == manifest['files'][name]['bytes']
        assert hashlib.sha256(data).hexdigest() == manifest['files'][name]['sha256']
    result = child(root, source / 'runtime', OLD_SEED, root / 'legacy', FIXTURES / 'legacy-schema1-records.json', PNG)
    metadata = json.loads(result.stdout.splitlines()[-1])
    metadata.update(root=root, source=source, profile=root / 'legacy')
    return metadata


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('DC20 populated upgrade cannot use live providers or network')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)


def rows(db, table):
    with closing(db.connect()) as conn:
        if not conn.execute('PRAGMA table_info("%s")' % table).fetchall():
            return []
        result = [dict(row) for row in conn.execute('SELECT * FROM "%s"' % table)]
    return sorted(result, key=lambda row: json.dumps(row, sort_keys=True))


def restore_zip(services, archive):
    recovery = services.get('data_recovery')
    identifier, directory = recovery.begin_preview()
    keep = False
    try:
        (directory / 'input.zip').write_bytes(Path(archive).read_bytes())
        preview = recovery.complete_preview(identifier, directory)
        keep = True
    finally:
        recovery.end_upload(directory, keep=keep)
    return recovery.restore_preview(preview['preview_token'], preview['exported_at'], True)


def old_clone(legacy, name):
    profile = legacy['root'] / name
    child(legacy['root'], legacy['source'] / 'runtime', r'''
import socket, sys
from pathlib import Path
from renulus.server import create_app

def forbidden(*args, **kwargs): raise AssertionError('Legacy clone cannot contact network')
socket.socket.connect = socket.socket.connect_ex = forbidden
services = create_app(sys.argv[1]).state.services
recovery = services.get('data_recovery')
identifier, directory = recovery.begin_preview()
(directory / 'input.zip').write_bytes(Path(sys.argv[2]).read_bytes())
preview = recovery.complete_preview(identifier, directory)
recovery.end_upload(directory, keep=True)
recovery.restore_preview(preview['preview_token'], preview['exported_at'], True)
''', profile, legacy['profile'] / 'legacy-zip2.zip')
    return profile


def assert_legacy_history(services, legacy):
    original = json.loads((legacy['profile'] / 'legacy-export.json').read_text(encoding='utf-8'))['records']
    for table in HISTORY_TABLES:
        expected, actual = original.get(table, []), rows(services.db, table)
        assert sorted(expected, key=lambda row: json.dumps(row, sort_keys=True)) == actual, table


def test_populated_schema_one_coordinated_upgrade_reopen_and_old_binary_refusal(legacy):
    profile = old_clone(legacy, 'upgrade-reopen')
    services = create_app(profile).state.services
    assert_legacy_history(services, legacy)
    with services.db.connect() as conn:
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 2
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert services.get('saved_tests').backfill_legacy()['created'] == 2
    manifests = rows(services.db, 'assessment_test_versions')
    reopened = create_app(profile).state.services
    assert reopened.get('saved_tests').backfill_legacy()['created'] == 0
    assert rows(reopened.db, 'assessment_test_versions') == manifests
    assert_legacy_history(reopened, legacy)
    result = child(legacy['root'], legacy['source'] / 'runtime', r'''
import sys
from renulus.server import create_app
try: create_app(sys.argv[1])
except RuntimeError as error:
    assert 'downgrade refused' in str(error)
    print('schema1 binary refused populated schema2')
else: raise AssertionError('Old binary accepted schema2')
''', profile)
    assert 'refused' in result.stdout
    assert_legacy_history(reopened, legacy)


def test_real_mid_migration_process_exit_rolls_back_failed_script_and_restarts(legacy):
    profile = old_clone(legacy, 'upgrade-interrupted')
    child(legacy['root'], REPO / 'runtime', r'''
import os, socket, sys
from pathlib import Path
from renulus.storage.database import Database
from renulus.server import create_app

def forbidden(*args, **kwargs): raise AssertionError('Interrupted upgrade cannot contact network')
socket.socket.connect = socket.socket.connect_ex = forbidden
original = Database.connect

def connect(self):
    conn = original(self)
    def trace(sql):
        if 'CREATE INDEX assessment_tests_recent' in sql:
            Path(sys.argv[2]).write_text(sql, encoding='utf-8')
            os._exit(73)
    conn.set_trace_callback(trace)
    return conn
Database.connect = connect
create_app(sys.argv[1])
raise AssertionError('Committed migration interruption seam was not reached')
''', profile, legacy['root'] / 'interrupted-at.sql', expected=73)
    with sqlite3.connect(profile / 'state/renulus.sqlite3') as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='assessment_tests'").fetchone() is None
        assert conn.execute("SELECT name FROM migration_ledger WHERE name='assessment-003'").fetchone() is None
        assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        # Completed scripts and compatibility stamp persist; failed-script DDL rolls back.
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 2
    restarted = create_app(profile).state.services
    assert_legacy_history(restarted, legacy)
    assert restarted.db.fetch_one("SELECT name FROM migration_ledger WHERE name='assessment-003'")
    assert restarted.get('saved_tests').backfill_legacy()['created'] == 2


@pytest.mark.parametrize('format', ['json', 'zip1', 'zip2'])
def test_actual_old_schema_one_archives_keep_populated_history_and_media_contract(legacy, format):
    services = create_app(legacy['root'] / ('old-restore-' + format)).state.services
    if format == 'json':
        bundle = json.loads((legacy['profile'] / 'legacy-export.json').read_text(encoding='utf-8'))
        services.get('data_recovery').restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle['exported_at'])
        assert services.db.fetch_all('SELECT * FROM case_attachment_parts') == []
    else:
        result = restore_zip(services, legacy['profile'] / ('legacy-' + format + '.zip'))
        # Library files are promoted; Case bytes use their existing SQLite parts.
        assert result['restored_originals'] == 1
        from renulus.cases.originals import load_metadata, read_original
        original = load_metadata(services.db, legacy['case_id'])[0]
        assert read_original(services.db, original) == base64.b64decode(PNG)
    assert_legacy_history(services, legacy)
    assert services.get('saved_tests').backfill_legacy()['created'] == 2
    assert context_epoch(services.db) == 1
    assert services.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.restore_dirty'")['value'] == 'true'
    assert services.db.fetch_all('SELECT id FROM memory_jobs') == []

