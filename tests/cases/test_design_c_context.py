# SPDX-License-Identifier: MIT
"""Connected Design C Case context actions through the original Save owner."""
import json

import pytest
from fastapi.testclient import TestClient

from renulus.server import create_app


def app_at(profile):
    return create_app(profile)


def case_body(client, route, **fields):
    return {
        'expected_revision': client.get(route).json()['revision'],
        'case_revision': client.get(route + '/context').json()['revision'],
        **fields,
    }


def test_case_context_wrapper_saves_replays_and_preserves_legacy_edit_meaning(tmp_path):
    profile = tmp_path / 'case-context'
    app = app_at(profile)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'text': 'Fictional initial context'}).json()
        route = '/api/v1/conversations/case/' + chat['identity']['id']
        context = client.get(route + '/context')
        assert context.status_code == 200, context.text
        assert 'messages' not in context.json()
        body = case_body(client, route, text='Fictional revised context')
        headers = {'Idempotency-Key': 'context-edit-command'}
        edited = client.patch(route + '/context', json=body, headers=headers)
        assert edited.status_code == 200, edited.text
        assert set(edited.json()) == {'conversation', 'case_revision'}
        assert not client.get(route + '/context').json()['dirty']
        # Independent stale original and sidecar revisions both refuse edits.
        current = case_body(client, route, text='Rejected stale context')
        assert client.patch(route + '/context', json={**current, 'case_revision': body['case_revision']}).status_code == 409
        assert client.patch(route + '/context', json={**current, 'expected_revision': body['expected_revision']}).status_code == 409
    with TestClient(app_at(profile)) as client:
        assert client.patch(route + '/context', json=body, headers=headers).json() == edited.json()
        assert client.get(route + '/context').json()['text'] == 'Fictional revised context'
        owner = '/api/v1/cases/sessions/' + chat['identity']['id']
        revision = client.get(owner).json()['revision']
        legacy = client.patch(owner, json={'revision': revision, 'text': 'Legacy unsaved fictional edit'})
        assert legacy.status_code == 200 and legacy.json()['dirty']
    with TestClient(app_at(profile)) as client:
        assert client.get(route + '/context').json()['text'] == 'Fictional revised context'


def test_teaching_context_wrapper_reveals_only_the_original_pinned_version(tmp_path):
    from .conftest import ContentFixture, HIDDEN_SENTINEL
    profile = tmp_path / 'teaching-context'
    app = app_at(profile)
    content = ContentFixture()
    app.state.services.registry['content'] = content
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'teaching_case_id': content.item['id']}).json()
        route = '/api/v1/conversations/case/' + chat['identity']['id']
        initial = client.get(route + '/context').json()
        assert HIDDEN_SENTINEL not in json.dumps(initial)
        assert 'teaching_points' not in initial['teaching']['stages'][0]
        content.item['version'] = 2
        content.item['stages'][1]['narrative'] = 'New installed version must not replace pin'
        body = case_body(client, route)
        revealed = client.post(route + '/context/reveal', json=body, headers={'Idempotency-Key': 'teaching-stage-reveal'})
        assert revealed.status_code == 200, revealed.text
        visible = client.get(route + '/context').json()['teaching']
        assert visible['version'] == 1 and visible['revealed_count'] == 2
        assert visible['stages'][1]['narrative'] == HIDDEN_SENTINEL
        assert 'teaching_points' not in visible['stages'][1]
        assert client.post(route + '/context/reveal', json=body, headers={'Idempotency-Key': 'teaching-stage-reveal'}).json() == revealed.json()
    with TestClient(app_at(profile)) as client:
        assert client.get(route + '/context').json()['teaching']['version'] == 1
        final = client.post(route + '/context/reveal', json=case_body(client, route))
        assert final.status_code == 200, final.text
        assert client.get(route + '/context').json()['teaching']['debriefed']


@pytest.mark.parametrize('format_version', [1, 2])
def test_wrapper_attachment_removal_tombstone_survives_actual_old_zip(tmp_path, format_version):
    import shutil
    from .test_saved_originals import synthetic_original
    from renulus.cases.repository import CaseRepository
    from renulus.storage.recovery_archive import backup_to
    from renulus.storage.recovery_segmented import backup_segmented_to
    app = app_at(tmp_path / 'wrapper-attachment-restore')
    services = app.state.services
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'text': 'Fictional original removal'}).json()
        identifier = chat['identity']['id']
        route = '/api/v1/conversations/case/' + identifier
        original = synthetic_original()
        cases = services.get('cases')
        attached = cases.attach(identifier, cases.get(identifier)['revision'], original)
        cases.save(identifier, attached['revision'])
        archive = services.paths.cache / 'old-wrapper.zip'
        (backup_to if format_version == 1 else backup_segmented_to)(services, archive)
        body = case_body(client, route)
        removed = client.delete(route + '/attachments/' + original['id'], params=body,
            headers={'Idempotency-Key': 'remove-case-original'})
        assert removed.status_code == 200, removed.text
        assert services.db.is_deleted('case_attachment', original['id'])
        assert client.get(route + '/context').json()['attachments'] == []
        recovery = services.get('data_recovery')
        preview_id, directory = recovery.begin_preview()
        keep = False
        try:
            shutil.copyfile(archive, directory / 'input.zip')
            preview = recovery.complete_preview(preview_id, directory)
            keep = True
        finally:
            recovery.end_upload(directory, keep=keep)
        recovery.restore_preview(preview_id, preview['exported_at'], True)
        assert CaseRepository(services).get(identifier)['attachments'] == []
        assert not services.db.fetch_all('SELECT * FROM case_attachment_parts WHERE attachment_id=?', (original['id'],))


def test_case_preview_wrapper_rollback_keeps_preview_and_original_session_identity(tmp_path, monkeypatch):
    import sqlite3
    from .test_saved_originals import synthetic_original
    from renulus.contracts import ContextScope, Scope
    import renulus.cases.repository as owner_module
    app = app_at(tmp_path / 'preview-rollback')
    services = app.state.services
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'text': 'Fictional image context'}).json()
        identifier = chat['identity']['id']
        route = '/api/v1/conversations/case/' + identifier
        before = client.get(route + '/context').json()
        original = synthetic_original('png')
        previews = services.get('case_previews')
        job = previews.preflight(identifier, before['revision'], ContextScope(kind=Scope.TEMPORARY_CASE, entity_id=identifier),
            original['filename'], original['title'], 'original')
        previews.start(job, original['data'])
        session = job.session
        body = case_body(client, route)
        headers = {'Idempotency-Key': 'keep-image-command'}
        save_originals = owner_module.save_originals
        def fail_after_write(conn, case_id, attachments):
            save_originals(conn, case_id, attachments)
            raise sqlite3.OperationalError('FICTIONAL_SAVE_FAILURE')
        monkeypatch.setattr(owner_module, 'save_originals', fail_after_write)
        failed = client.post(route + '/previews/' + job.id + '/keep', json=body, headers=headers)
        assert failed.status_code == 503 and failed.json()['error']['code'] == 'case_save_failed'
        assert 'FICTIONAL_SAVE_FAILURE' not in failed.text
        assert services.get('cases')._sessions[identifier] is session
        assert previews._guard(job) is session
        assert job.state == 'ready' and job.original == original['data']
        assert client.get(route + '/context').json() == before
        assert not services.db.fetch_all('SELECT * FROM case_attachments')
        assert not services.db.fetch_all('SELECT * FROM conversation_commands WHERE idempotency_key=?', ('keep-image-command',))
        monkeypatch.setattr(owner_module, 'save_originals', save_originals)
        kept = client.post(route + '/previews/' + job.id + '/keep', json=body, headers=headers)
        assert kept.status_code == 200, kept.text
        assert client.post(route + '/previews/' + job.id + '/keep', json=body, headers=headers).json() == kept.json()
        context = client.get(route + '/context').json()
        assert context['attachments'][0]['saved'] and not context['dirty']
        assert services.get('cases').original(identifier, context['attachments'][0]['id'])[1] == original['data']


def test_temporary_case_context_mutation_has_no_durable_payload_or_command(tmp_path):
    from renulus.storage.backup import export_records
    profile = tmp_path / 'temporary-case-context'
    app = app_at(profile)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case', 'temporary': True}).json()
        route = '/api/v1/conversations/case/' + chat['identity']['id']
        marker = 'FICTIONAL_VOLATILE_CONTEXT_782D1'
        body = case_body(client, route, text=marker)
        result = client.patch(route + '/context', json=body, headers={'Idempotency-Key': 'temporary-context-command'})
        assert result.status_code == 200, result.text
        assert result.json()['conversation']['retention'] == 'temporary'
        assert client.get(route + '/context').json()['text'] == marker
        exported = json.dumps(export_records(app.state.services))
        assert marker not in exported and chat['identity']['id'] not in exported
    for path in profile.rglob('*'):
        if path.is_file():
            assert marker.encode() not in path.read_bytes()
