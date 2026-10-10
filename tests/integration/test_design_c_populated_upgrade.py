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
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGP8//8/AwMDEwMYAAAkBgMBXaJOiAAAAABJRU5ErkJggg=='
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
from renulus.memory.models import ManualFact
from renulus.contracts import ContextScope, Scope
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
memory = services.get('memory').add(ManualFact(text='SYNTHETIC legacy retained learning point',
    scope=ContextScope(kind=Scope.STUDY), idempotency_key='old-populated-memory'))
services.get('memory').edit(memory['id'], 'SYNTHETIC legacy personally corrected learning point', memory['revision'])
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


@pytest.fixture(scope='module', autouse=True)
def no_network():
    def forbidden(*args, **kwargs):
        raise AssertionError('DC20 populated upgrade cannot use live providers or network')
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(socket.socket, 'connect', forbidden)
        monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
        yield


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


def assert_legacy_history(services, legacy, *, additional=False):
    original = json.loads((legacy['profile'] / 'legacy-export.json').read_text(encoding='utf-8'))['records']
    for table in HISTORY_TABLES:
        expected, actual = original.get(table, []), rows(services.db, table)
        if additional:
            assert all(row in actual for row in expected), table
        else:
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


class InstalledSyntheticTransport:
    """Only the remote endpoint is synthetic; ProviderManager owns the real route."""
    def __init__(self):
        self.calls = []

    async def stream(self, provider, model, token, messages):
        assert (provider, model, token) == ('codex', 'gpt-6.1-sol', 'dc20-synthetic-token')
        self.calls.append((provider, model))
        output = {'items': [{'stem': 'SYNTHETIC generated renal question %d' % index,
            'options': [{'id': 'a', 'text': 'First interpretation', 'rationale': 'Private synthetic rationale'},
                        {'id': 'b', 'text': 'Second interpretation', 'rationale': 'Private alternative'}],
            'correct_option_id': 'a', 'explanation': 'Private synthetic explanation',
            'hint': None, 'source_indices': []} for index in range(5)]}
        yield {'type': 'delta', 'text': json.dumps(output)}
        yield {'type': 'completed', 'response_model': model}


PASTED = ('  1. Which SYNTHETIC CKD choice is supplied?\nA. First interpretation\nB. Second interpretation\nAnswer: A\n\n'
          '2. Which SYNTHETIC dialysis choice is supplied?\nA. First dialysis option\nB. Second dialysis option\nAnswer: A\n  ')
NOTE_ONE = 'SYNTHETIC first saved glomerular note.\n'
NOTE_TWO = 'SYNTHETIC personally revised glomerular note.\n'
STABLE_CURRENT = ('assessment_tests', 'assessment_test_versions', 'assessment_test_attempts',
    'assessment_attempt_drafts', 'assessment_attempt_exposure',
    'assessment_question_reports', 'assessment_test_imports', 'assessment_test_jobs', 'learn_conversations', 'case_conversations',
    'study_projects', 'study_project_chats', 'study_project_documents', 'study_project_goals',
    'knowledge_attachments', 'knowledge_attachment_metadata', 'memory_facts', 'memory_history')


@pytest.fixture(scope='module')
def populated(legacy):
    from renulus.assessment.attempt_models import DraftState, QuestionReport, StartAttempt, SubmitAttempt
    from renulus.assessment.generation_models import CreateGenerationRequest
    from renulus.assessment.import_models import (CreateImportRequest, EditImportCandidateRequest,
        ImportRevisionCommand, ResolveImportCandidateRequest)
    from renulus.assessment.test_models import CreateReviewedTestRequest
    from renulus.design_c_contracts import ConversationDraft
    from renulus.knowledge.attachment_models import AttachmentUpload
    from renulus.knowledge.models import SourceMetadata, own_text_rights
    from renulus.knowledge.note_models import CreateNote, EditNote
    from renulus.learn.conversation_models import NewConversation
    from renulus.storage.assessment_policy import policy_snapshot
    from renulus.study.project_models import NewProject

    services = create_app(old_clone(legacy, 'current-producers')).state.services
    services.get('saved_tests').backfill_legacy()
    projects, chats = (services.get(key) for key in ('projects', 'conversations'))
    notes = services.get('notes')
    project = projects.create(NewProject(title='SYNTHETIC mixed renal learning'), 'dc20-project-create')
    chat = chats.create(NewConversation(title='SYNTHETIC saved dialysis chat', project_id=project['id']), 'dc20-chat-create')
    note1 = notes.save(CreateNote(title='SYNTHETIC glomerular note', text=NOTE_ONE,
        idempotency_key='dc20-note-create', project_id=project['id']))
    note2 = notes.save(EditNote(title='SYNTHETIC revised glomerular note', text=NOTE_TWO,
        idempotency_key='dc20-note-edit', expected_revision_id=note1['revision_id']), document_id=note1['document_id'])
    with services.db.transaction() as conn:
        policy_revision = policy_snapshot(conn)['revision']
    attachment = services.get('knowledge_attachments').upload(AttachmentUpload(conversation=chat['identity'],
        expected_conversation_revision=chat['revision'], expected_policy_revision=policy_revision,
        expected_context_epoch=context_epoch(services.db), idempotency_key='dc20_chat_upload',
        filename='synthetic-chat.png', title='SYNTHETIC saved chat original', rights=own_text_rights(),
        metadata=SourceMetadata()), base64.b64decode(PNG))
    chats.save_draft('learning', chat['identity']['id'], ConversationDraft(
        expected_revision=attachment['conversation_revision'], text='SYNTHETIC retained draft',
        content_refs=(attachment['reference'], note2['reference'])), 'dc20-chat-draft')

    imports = services.get('saved_imports')
    imported = imports.create(CreateImportRequest(idempotency_key='dc20-import-create', title='SYNTHETIC personal imported set',
        original={'kind': 'paste', 'text': PASTED, 'terms': 'Synthetic personal original', 'permission_confirmed': True}))
    first = imported['candidates'][0]
    imported = imports.mutate_candidate(imported['id'], first['id'], 'edit', EditImportCandidateRequest(
        idempotency_key='dc20-import-edit', expected_revision=imported['revision'],
        stem='SYNTHETIC personally edited CKD choice', options=first['options'], explanation='Personal retained explanation'))
    for index, candidate in enumerate(imported['candidates']):
        imported = imports.mutate_candidate(imported['id'], candidate['id'], 'resolve', ResolveImportCandidateRequest(
            idempotency_key='dc20-import-resolve-%d' % index, expected_revision=imported['revision'],
            correct_option_ids=('a',), review_confirmed=True))
    imported = imports.save(imported['id'], ImportRevisionCommand(idempotency_key='dc20-import-save', expected_revision=imported['revision']))
    reviewed = services.get('saved_tests').create_reviewed(CreateReviewedTestRequest(idempotency_key='dc20-reviewed-create', count=2))

    transport = InstalledSyntheticTransport()
    provider = services.get('provider')
    provider._settings['connections']['codex'] = {'access_token': 'dc20-synthetic-token', 'expires_at': 9999999999}
    provider._settings['selected_provider'] = 'codex'
    provider._settings.setdefault('selected_models', {})['codex'] = 'gpt-6.1-sol'
    provider._transport = transport

    async def generate():
        owner = services.get('saved_generation')
        row = await owner.create(CreateGenerationRequest(idempotency_key='dc20-generated-create', count=5, topic_id='T01'))
        await owner.tasks[row['id']]
        return owner.read(row['id'])
    generated = asyncio.run(generate())
    assert generated['state'] == 'published' and generated['result']['item_count'] == 5
    assert transport.calls == [('codex', 'gpt-6.1-sol')]

    attempts, reports = [], []
    for result in (imported['result'], reviewed):
        with services.db.transaction() as conn:
            version = services.get('saved_tests').pinned_version(conn, result['version_id'])
        attempt = services.get('whole_attempts').start(StartAttempt(version={'type': 'saved_test_version', 'id': version.id}, mode='test'),
            'dc20-attempt-' + version.id[-24:])
        reports.append(services.get('whole_attempts').report(attempt['id'], QuestionReport(
            item_id=version.items[0].item_id, report_text='SYNTHETIC neutral retained provenance report'), 'dc20-report-' + version.id[-24:]))
        answers = [{'item_id': item.item_id, 'option_ids': list(item.correct_option_ids) if version.origin == 'reviewed_bank' or index == 0 else []}
                   for index, item in enumerate(version.items)]
        attempt = services.get('whole_attempts').submit(attempt['id'], SubmitAttempt(expected_draft_revision=attempt['draft_revision'],
            latest_draft=DraftState(position=0, answers=answers)), 'dc20-submit-' + version.id[-24:])
        attempts.append(attempt)
    assert attempts[0]['result']['denominator'] == 2 and attempts[0]['result']['correct'] == 1
    assert attempts[0]['result']['unanswered'] == 1 and attempts[0]['result']['cohorts']['personal']['denominator'] == 2
    assert attempts[1]['result']['denominator'] == 2 and attempts[1]['result']['correct'] == 2
    progress = services.get('study').progress()
    assert sum(group['answered'] for group in progress['groups'].values()) == 3  # One captured old + two current reviewed; personal excluded.
    records = export_records(services)
    archives = {}
    for number in (1, 2):
        directory, _ = services.get('data_recovery').backup(format_version=number)
        archives['zip%d' % number] = legacy['root'] / ('current-zip%d.zip' % number)
        archives['zip%d' % number].write_bytes((directory / 'backup.zip').read_bytes())
    yield dict(services=services, records=records, archives=archives, chat=chat, project=project,
        notes=(note1, note2), imported=imported, reviewed=reviewed, generated=generated, attempts=attempts,
        reports=reports, transport=transport, progress=progress)
    services.get('knowledge').index.close()


def recover_current(services, populated, format):
    if format == 'json':
        bundle = populated['records']
        return services.get('data_recovery').restore_json(bundle, confirm_backup_date=True, confirmed_exported_at=bundle['exported_at'])
    return restore_zip(services, populated['archives'][format])


@pytest.mark.parametrize('format', ['json', 'zip1', 'zip2'])
def test_populated_upgrade_current_producers_restore_reopen_and_owned_deletions(legacy, populated, format):
    from renulus.assessment.import_models import ImportRevisionCommand
    from renulus.assessment.test_models import TestLifecycleRequest
    from renulus.contracts import ApiError
    from renulus.learn.conversation_models import Mutation
    from renulus.knowledge.note_models import DeleteNote

    profile = legacy['root'] / ('combined-restore-' + format)
    services = create_app(profile).state.services
    before_epoch = context_epoch(services.db)
    before_memory_epoch = services.db.fetch_one('SELECT epoch FROM memory_index_state')['epoch']
    recover_current(services, populated, format)
    assert context_epoch(services.db) == before_epoch + 1
    assert services.db.fetch_one('SELECT epoch FROM memory_index_state')['epoch'] == before_memory_epoch + 1
    assert services.db.fetch_one('SELECT state FROM memory_index_state')['state'] != 'ready'
    assert services.db.fetch_one("SELECT value FROM preferences WHERE key='knowledge.restore_dirty'")['value'] == 'true'
    for table in STABLE_CURRENT:
        expected = sorted(populated['records']['records'].get(table, []), key=lambda row: json.dumps(row, sort_keys=True))
        assert rows(services.db, table) == expected, table
    assert_legacy_history(services, legacy, additional=True)
    assert services.get('study').progress() == populated['progress']
    assert services.get('saved_imports').original(populated['imported']['id'])['text'] == PASTED
    assert services.get('conversations').draft('learning', populated['chat']['identity']['id'])['text'] == 'SYNTHETIC retained draft'
    for attempt in populated['attempts']:
        stored = services.db.fetch_one('SELECT result_json FROM assessment_test_attempts WHERE id=?', (attempt['id'],))
        assert json.loads(stored['result_json']) == attempt['result']
    if format == 'json':
        assert all(row['original_path'] is None for row in rows(services.db, 'knowledge_revisions'))
        assert all(row['original_path'] is None for row in rows(services.db, 'knowledge_attachment_originals'))
        assert rows(services.db, 'case_attachment_parts') == []
    else:
        for note, text in zip(populated['notes'], (NOTE_ONE, NOTE_TWO)):
            assert services.get('notes').get(note['document_id'], revision_id=note['revision_id'])['text'] == text
        for original in rows(services.db, 'knowledge_attachment_originals'):
            assert Path(original['original_path']).read_bytes() == base64.b64decode(PNG)
    services.get('knowledge').index.close()
    services = create_app(profile).state.services
    assert services.get('saved_tests').backfill_legacy()['created'] == 0
    assert services.get('study').progress() == populated['progress']
    assert rows(services.db, 'memory_jobs') == []

    # Delete actual owners then restore the older populated snapshot. Membership
    # deletion must not propagate into independently owned chats/Library notes.
    project = services.get('projects').get(populated['project']['id'])
    services.get('projects').delete(project['id'], Mutation(expected_revision=project['revision']), 'dc20-project-delete')
    recover_current(services, populated, format)
    assert rows(services.db, 'study_projects') == []
    assert rows(services.db, 'study_project_chats') == rows(services.db, 'study_project_documents') == []
    assert services.db.fetch_one('SELECT id FROM learn_threads WHERE id=?', (populated['chat']['identity']['id'],))
    assert services.db.fetch_one('SELECT id FROM knowledge_documents WHERE id=?', (populated['notes'][0]['document_id'],))

    chat = services.get('conversations').get('learning', populated['chat']['identity']['id'])
    asyncio.run(services.get('conversations').delete('learning', chat['identity']['id'], Mutation(expected_revision=chat['revision']), 'dc20-chat-delete'))
    imported = services.get('saved_imports').read(populated['imported']['id'])
    asyncio.run(services.get('saved_imports').delete(imported['id'], ImportRevisionCommand(idempotency_key='dc20-import-delete', expected_revision=imported['revision'])))
    services.get('saved_tests').lifecycle(populated['imported']['result']['test_id'],
        TestLifecycleRequest(idempotency_key='dc20-test-delete', expected_revision=1), 'delete')
    if format != 'json':
        note = populated['notes'][1]
        services.get('notes').delete(note['document_id'], DeleteNote(expected_revision_id=note['revision_id'], idempotency_key='dc20-note-delete'))
    recover_current(services, populated, format)
    assert not services.db.fetch_one('SELECT id FROM learn_threads WHERE id=?', (chat['identity']['id'],))
    assert rows(services.db, 'knowledge_attachments') == rows(services.db, 'knowledge_attachment_originals') == []
    assert not services.db.fetch_one('SELECT id FROM assessment_test_imports WHERE id=?', (imported['id'],))
    assert not services.db.fetch_one('SELECT id FROM assessment_test_versions WHERE id=?', (populated['imported']['result']['version_id'],))
    for attempt in populated['attempts']:
        row = services.db.fetch_one('SELECT * FROM assessment_test_attempts WHERE id=?', (attempt['id'],))
        assert json.loads(row['result_json']) == attempt['result']
        if attempt['version_id'] == populated['imported']['result']['version_id']:
            assert row['live_version_id'] is None
    for report in populated['reports']:
        row = services.db.fetch_one('SELECT * FROM assessment_question_reports WHERE id=?', (report['id'],))
        expected = next(row for row in populated['records']['records']['assessment_question_reports'] if row['id'] == report['id'])
        assert row['question_snapshot_json'] == expected['question_snapshot_json']
    assert services.get('study').progress() == populated['progress']
    assert rows(services.db, 'memory_facts') == populated['records']['records']['memory_facts']
    assert rows(services.db, 'memory_jobs') == []
    assert populated['transport'].calls == [('codex', 'gpt-6.1-sol')]
    with services.db.connect() as conn:
        assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    services.get('knowledge').index.close()

