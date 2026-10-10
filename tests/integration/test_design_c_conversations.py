# SPDX-License-Identifier: MIT
"""Connected conversations use the real legacy owners and additive sidecars."""
from fastapi.testclient import TestClient
import pytest
import json


class ConversationProvider:
    def __init__(self):
        self.inputs = []
        self.fail = False
        self.on_reply = None

    async def stream(self, messages, **options):
        self.inputs.append(messages.copy())
        if self.on_reply:
            self.on_reply()
        yield 'Fictional learning response.'
        if self.fail:
            raise RuntimeError('FICTIONAL_RAW_PROVIDER_FAILURE')

    async def cancel(self, run_id):
        return True


def event_payloads(response):
    assert response.status_code == 200, response.text
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]

from renulus.server import create_app
from renulus.learn.conversation_api import create_router


def app_at(profile):
    app = create_app(profile)
    if "conversations" not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix="/api/v1")
    if not any(getattr(route, 'path', '') == '/api/v1/attachments' for route in app.routes):
        from renulus.knowledge.attachment_api import create_router as attachment_router
        app.include_router(attachment_router(app.state.services), prefix='/api/v1')
    return app


def upload_chat_file(client, app, chat, *, key='fictional-upload-command'):
    from renulus.knowledge.models import own_text_rights
    from renulus.storage.assessment_policy import policy_snapshot
    from renulus.storage.invalidation import context_epoch_in
    with app.state.services.db.transaction() as conn:
        options = {'conversation': chat['identity'], 'expected_conversation_revision': chat['revision'],
            'expected_policy_revision': policy_snapshot(conn)['revision'], 'expected_context_epoch': context_epoch_in(conn),
            'idempotency_key': key, 'filename': 'fictional.md', 'title': 'Fictional owned original',
            'rights': own_text_rights().model_dump(mode='json'), 'metadata': {}}
    response = client.post('/api/v1/attachments', content=b'# FICTIONAL OWNED CHAT FILE' + bytes([10]) + b'Educational text only.',
        headers={'x-renulus-attachment-options': json.dumps(options)})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize('kind,legacy', [('learning', False), ('case', False), ('learning', True), ('case', True)])
def test_chat_and_legacy_owner_delete_journal_actual_attachment_cleanup_after_commit(tmp_path, monkeypatch, kind, legacy):
    import renulus.storage.attachment_cleanup as cleanup
    app = app_at(tmp_path / 'owned-file-delete')
    services = app.state.services
    with TestClient(app) as client:
        project = client.post('/api/v1/study/projects', json={'title': 'Fictional attachment project'}).json()
        chat = client.post('/api/v1/conversations', json={'kind': kind, 'project_id': project['id']}).json()
        identifier = chat['identity']['id']
        route = '/api/v1/conversations/' + kind + '/' + identifier
        uploaded = upload_chat_file(client, app, chat)
        original = services.db.fetch_one('SELECT * FROM knowledge_attachment_originals WHERE attachment_id=?', (uploaded['id'],))
        directory = services.paths.library / 'attachments' / uploaded['id']
        assert directory.is_dir()
        membership = services.db.fetch_one('SELECT id FROM study_project_chats WHERE chat_kind=? AND chat_id=?', (kind, identifier))
        remove_tree, observed = cleanup.remove_owned_tree, []
        def postcommit_only(paths, target):
            # A new connection sees the complete deletion before filesystem work.
            with services.db.connect() as conn:
                owner = 'learn_threads' if kind == 'learning' else 'case_sessions'
                assert not conn.in_transaction
                assert conn.execute('SELECT id FROM ' + owner + ' WHERE id=?', (identifier,)).fetchone() is None
                assert conn.execute('SELECT id FROM knowledge_attachments WHERE id=?', (uploaded['id'],)).fetchone() is None
                assert conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type='attachment' AND entity_id=?", (uploaded['id'],)).fetchone()
                assert conn.execute('SELECT id FROM study_project_chats WHERE id=?', (membership['id'],)).fetchone() is None
            observed.append(str(target))
            remove_tree(paths, target)
        monkeypatch.setattr(cleanup, 'remove_owned_tree', postcommit_only)
        if legacy:
            owner_route = '/api/v1/learn/threads/' + identifier if kind == 'learning' else '/api/v1/cases/sessions/' + identifier
            removed = client.delete(owner_route)
        else:
            removed = client.delete(route, params={'expected_revision': uploaded['conversation_revision']},
                headers={'Idempotency-Key': 'delete-owned-chat-command'})
        assert removed.status_code == 200, removed.text
        assert observed and not directory.exists()
        assert services.db.is_deleted('attachment', uploaded['id'])
        assert services.db.is_deleted('attachment_original', original['id'])
        assert services.db.is_deleted('project_chat', membership['id'])
        assert not services.db.fetch_all('SELECT * FROM knowledge_attachment_metadata WHERE attachment_id=?', (uploaded['id'],))
        assert services.db.fetch_one('SELECT value FROM preferences WHERE key=?', (cleanup.JOURNAL,)) is None


@pytest.mark.parametrize('kind', ['learning', 'case'])
def test_temporary_chat_delete_discards_actual_attachment_bytes_and_upload_receipts(tmp_path, kind):
    from renulus.storage.backup import export_records
    app = app_at(tmp_path / 'temporary-attachment-delete')
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': kind, 'temporary': True}).json()
        uploaded = upload_chat_file(client, app, chat)
        repository = app.state.services.get('chat_attachments')
        assert uploaded['id'] in repository._volatile and repository._volatile_commands
        route = '/api/v1/conversations/' + kind + '/' + chat['identity']['id']
        removed = client.delete(route, params={'expected_revision': uploaded['conversation_revision']})
        assert removed.status_code == 200, removed.text
        assert not repository._volatile and not repository._volatile_commands
        exported = json.dumps(export_records(app.state.services))
        assert uploaded['id'] not in exported and chat['identity']['id'] not in exported
        assert 'FICTIONAL OWNED CHAT FILE' not in exported


def test_owned_attachment_cleanup_pending_journal_drains_after_actual_restart(tmp_path, monkeypatch):
    import renulus.storage.attachment_cleanup as cleanup
    profile = tmp_path / 'restart-file-cleanup'
    app = app_at(profile)
    remove_tree = cleanup.remove_owned_tree
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        uploaded = upload_chat_file(client, app, chat)
        directory = app.state.services.paths.library / 'attachments' / uploaded['id']
        def locked_file(*args):
            raise OSError('Fictional temporary file lock')
        monkeypatch.setattr(cleanup, 'remove_owned_tree', locked_file)
        removed = client.delete('/api/v1/conversations/learning/' + chat['identity']['id'],
            params={'expected_revision': uploaded['conversation_revision']})
        assert removed.status_code == 200 and directory.exists()
        assert app.state.services.db.fetch_one('SELECT value FROM preferences WHERE key=?', (cleanup.JOURNAL,))
    monkeypatch.setattr(cleanup, 'remove_owned_tree', remove_tree)
    reopened = app_at(profile)
    with TestClient(reopened):
        assert not directory.exists()
        assert reopened.state.services.db.fetch_one('SELECT value FROM preferences WHERE key=?', (cleanup.JOURNAL,)) is None


@pytest.mark.parametrize('failure_point', ['journal', 'owner_tombstone'])
def test_attachment_and_owner_deletion_roll_back_when_journal_enqueue_fails(tmp_path, monkeypatch, failure_point):
    import renulus.learn.conversation_repository as owner_module
    app = app_at(tmp_path / 'journal-rollback')
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': 'case'}).json()
        uploaded = upload_chat_file(client, app, chat)
        directory = app.state.services.paths.library / 'attachments' / uploaded['id']
        enqueue = owner_module.enqueue_in
        def fail_after_enqueue(conn, plan):
            enqueue(conn, plan)
            raise RuntimeError('Fictional transaction refusal')
        if failure_point == 'journal':
            monkeypatch.setattr(owner_module, 'enqueue_in', fail_after_enqueue)
        else:
            mark_deleted = app.state.services.db.mark_deleted
            def fail_after_owner_delete(entity_type, identifier, conn=None):
                mark_deleted(entity_type, identifier, conn)
                if entity_type == 'case':
                    raise RuntimeError('Fictional transaction refusal')
            monkeypatch.setattr(app.state.services.db, 'mark_deleted', fail_after_owner_delete)
        with pytest.raises(RuntimeError, match='Fictional transaction refusal'):
            client.delete('/api/v1/conversations/case/' + chat['identity']['id'],
                params={'expected_revision': uploaded['conversation_revision']})
        assert client.get('/api/v1/conversations/case/' + chat['identity']['id']).status_code == 200
        assert app.state.services.db.fetch_one('SELECT id FROM knowledge_attachments WHERE id=?', (uploaded['id'],))
        assert not app.state.services.db.is_deleted('attachment', uploaded['id'])
        assert directory.is_dir()


def test_neutral_run_detail_has_exact_keys_before_and_during_active_test(tmp_path):
    app = app_at(tmp_path / 'neutral-run-detail')
    app.state.services.registry['provider'] = ConversationProvider()
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        identifier = chat['identity']['id']
        route = '/api/v1/conversations/learning/' + identifier
        sent = client.post(route + '/messages', json={'expected_revision': chat['revision'],
            'text': 'Fictional neutral receipt request', 'request_id': 'neutral-receipt-request'})
        events = event_payloads(sent)
        run_id = events[0]['run_id']
        streams = app.state.services.get('conversations').streaming
        assert streams.status('learning', identifier, run_id, neutral=True) == {'run_id': run_id, 'state': 'completed'}
        assert 'conversation' in streams.status('learning', identifier, run_id)
        assert client.get(route + '/runs/' + run_id + '?neutral=true').json() == {'run_id': run_id, 'state': 'completed'}
        app.state.services.db.execute(
            "INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
            "VALUES('neutral-active-test','unavailable','{}','test',?,?,?)", (chat['created_at'],) * 3)
        assert streams.status('learning', identifier, run_id, neutral=True) == {'run_id': run_id, 'state': 'completed'}


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_saved_default_chat_and_draft_survive_restart_using_original_owner(tmp_path, kind):
    profile = tmp_path / "saved-chat"
    with TestClient(app_at(profile)) as client:
        created = client.post("/api/v1/conversations", json={"kind": kind, "title": "Fictional CKD study"})
        assert created.status_code == 201, created.text
        chat = created.json()
        assert chat["retention"] == "saved" and chat["project_id"] is None
        identifier = chat["identity"]["id"]
        route = f"/api/v1/conversations/{kind}/{identifier}"
        written = client.put(route + "/draft", json={"expected_revision": chat["revision"],
            "text": "Explain this fictional nephrology topic.", "content_refs": []})
        assert written.status_code == 200, written.text
    with TestClient(app_at(profile)) as restarted:
        result = restarted.get(route).json()
        assert result["identity"] == chat["identity"]
        assert restarted.get(route + "/draft").json()["text"] == "Explain this fictional nephrology topic."
        owner_route = f"/api/v1/learn/threads/{identifier}" if kind == "learning" else f"/api/v1/cases/sessions/{identifier}"
        assert restarted.get(owner_route).status_code == 200


@pytest.mark.parametrize("kind", ["learning", "case"])
def test_archive_restore_rename_and_delete_preserve_revision_and_draft(tmp_path, kind):
    with TestClient(app_at(tmp_path / "chat-lifecycle")) as client:
        chat = client.post("/api/v1/conversations", json={"kind": kind}).json()
        route = f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        saved = client.put(route + "/draft", json={"expected_revision": chat["revision"], "text": "A retained draft"}).json()
        renamed = client.patch(route, json={"expected_revision": saved["conversation_revision"], "title": "Renamed CKD discussion"})
        assert renamed.status_code == 200, renamed.text
        revision = renamed.json()["revision"]
        archived = client.post(route + "/archive", json={"expected_revision": revision})
        assert archived.status_code == 200, archived.text
        assert client.get("/api/v1/conversations").json()["items"] == []
        assert client.get("/api/v1/conversations?lifecycle=archived").json()["items"][0]["identity"] == chat["identity"]
        restored = client.post(route + "/restore", json={"expected_revision": archived.json()["revision"]}).json()
        assert client.get(route + "/draft").json()["text"] == "A retained draft"
        assert client.patch(route, json={"expected_revision": revision, "title": "Stale title"}).status_code == 409
        deleted = client.delete(route, params={"expected_revision": restored["revision"]})
        assert deleted.status_code == 200, deleted.text
        assert client.get(route).status_code == 404
        assert client.get("/api/v1/conversations").json()["items"] == []


def test_saved_command_replay_survives_restart_and_checks_present_policy(tmp_path):
    profile = tmp_path / 'command-replay'
    body = {'kind': 'learning', 'title': 'Fictional dialysis learning'}
    headers = {'Idempotency-Key': 'create-command-1234'}
    with TestClient(app_at(profile)) as client:
        original = client.post('/api/v1/conversations', json=body, headers=headers).json()
    app = app_at(profile)
    with TestClient(app) as client:
        assert client.post('/api/v1/conversations', json=body, headers=headers).json() == original
        assert client.post('/api/v1/conversations', json={**body, 'title': 'Different'}, headers=headers).status_code == 409
        # A real active Test row is installed by the assessment owner; this fixture
        # tests the shared disclosure boundary through the conversation API.
        app.state.services.db.execute(
            "INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) "
            "VALUES('policy-test','pinned-unavailable','{}','test',?,?,?)",
            (original['created_at'],) * 3)
        denied = client.post('/api/v1/conversations', json=body, headers=headers)
        assert denied.status_code == 409 and denied.json()['error']['code'] == 'assistance_restricted'


@pytest.mark.parametrize('kind', ['learning', 'case'])
def test_temporary_draft_and_delete_leave_no_durable_identity_or_payload(tmp_path, kind):
    from renulus.storage.backup import export_records
    profile = tmp_path / 'volatile-chat'
    app = app_at(profile)
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={'kind': kind, 'temporary': True}).json()
        identifier = chat['identity']['id']
        route = f'/api/v1/conversations/{kind}/{identifier}'
        marker = 'FICTIONAL_VOLATILE_DRAFT_981427'
        draft = client.put(route + '/draft', json={'expected_revision': 1, 'text': marker}).json()
        assert client.get('/api/v1/conversations').json()['items'] == []
        assert client.get(route + '/draft').json()['text'] == marker
        assert client.delete(route, params={'expected_revision': draft['conversation_revision']}).status_code == 200
        exported = json.dumps(export_records(app.state.services))
        assert marker not in exported and identifier not in exported
    for path in profile.rglob('*'):
        if path.is_file():
            assert marker.encode() not in path.read_bytes() and identifier.encode() not in path.read_bytes()


def test_message_pages_pin_snapshot_and_reject_cross_chat_cursor(tmp_path):
    app = app_at(tmp_path / 'paged-chat')
    with TestClient(app) as client:
        chat = client.post('/api/v1/conversations', json={}).json()
        other = client.post('/api/v1/conversations', json={}).json()
        identifier = chat['identity']['id']
        db = app.state.services.db
        # Deliberate timestamp ties exercise keyset ordering at the public page seam.
        with db.transaction() as conn:
            conn.execute("INSERT INTO learn_runs VALUES('page-run',?,'page-key','completed',NULL,?,?)",
                         (identifier, chat['created_at'], chat['created_at']))
            for i in range(5):
                conn.execute('INSERT INTO learn_messages VALUES(?,?,?,?,?,?,?)',
                    (f'message-{i}', identifier, 'page-run', 'user', f'Fictional message {i}', '[]', chat['created_at']))
        path = f'/api/v1/conversations/learning/{identifier}/messages'
        first = client.get(path, params={'limit': 2}).json()
        db.execute('INSERT INTO learn_messages VALUES(?,?,?,?,?,?,?)',
            ('message-later', identifier, 'page-run', 'user', 'Later addition', '[]', '2099-01-01T00:00:00+00:00'))
        seen = [x['id'] for x in first['items']]
        cursor = first['next_cursor']
        invalid = client.get(f"/api/v1/conversations/learning/{other['identity']['id']}/messages", params={'cursor': cursor})
        assert invalid.status_code == 422
        while cursor:
            page = client.get(path, params={'limit': 2, 'cursor': cursor}).json()
            seen.extend(x['id'] for x in page['items'])
            cursor = page['next_cursor']
        assert seen == [f'message-{i}' for i in range(5)]
        assert 'message-later' in [x['id'] for x in client.get(path).json()['items']]


@pytest.mark.parametrize('kind',['learning','case'])
def test_saved_wrapper_send_checkpoints_failure_and_success_then_replays_after_restart(tmp_path,kind):
    profile=tmp_path/'send-restart'
    app=app_at(profile)
    provider=ConversationProvider()
    app.state.services.registry.update(provider=provider,knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind}).json()
        path=f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        body={'expected_revision':chat['revision'],'request_id':'failure-request-123','text':'Explain fictional dialysis.'}
        provider.fail=True
        failed=event_payloads(client.post(path+'/messages',json=body,headers={'Idempotency-Key':body['request_id']}))
        assert failed[-1]['type']=='error'
        assert 'FICTIONAL_RAW_PROVIDER_FAILURE' not in json.dumps(failed)
        assert client.get(path+'/draft').json()['text']==body['text']
        current=client.get(path).json()
        provider.fail=False
        success={**body,'expected_revision':current['revision'],'request_id':'success-request-123'}
        completed=event_payloads(client.post(path+'/messages',json=success,headers={'Idempotency-Key':success['request_id']}))
        assert completed[-1]['type']=='completed', completed
        assert client.get(path+'/draft').json()['text']==''
        assert [row['role'] for row in client.get(path+'/messages').json()['items']]==['user','user','assistant']
    restarted=app_at(profile)
    restarted.state.services.registry.update(provider=ConversationProvider(),knowledge=None,retrieval=None,memory=None)
    with TestClient(restarted) as client:
        replay=event_payloads(client.post(path+'/messages',json=success,headers={'Idempotency-Key':success['request_id']}))
        assert replay[-1]['type']=='completed' and replay[-1]['payload']['replayed'] is True
        assert restarted.state.services.get('provider').inputs==[]
        assert client.post(path+'/messages',json={**success,'text':'Changed text'},headers={'Idempotency-Key':success['request_id']}).status_code==409


@pytest.mark.parametrize('kind',['learning','case'])
def test_temporary_multi_turn_generation_stays_out_of_profile_and_export(tmp_path,kind):
    from renulus.storage.backup import export_records
    profile=tmp_path/'temporary-generation'
    app=app_at(profile)
    provider=ConversationProvider()
    app.state.services.registry.update(provider=provider,knowledge=None,retrieval=None,memory=None)
    marker='FICTIONAL_VOLATILE_MULTI_TURN_36985'
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind,'temporary':True}).json()
        path=f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        for text,key in [(marker,'first-temp-request'),('Continue the previous explanation','second-temp-request')]:
            current=client.get(path).json()
            completed=event_payloads(client.post(path+'/messages',json={'expected_revision':current['revision'],'text':text,'request_id':key}))
            assert completed[-1]['type']=='completed',completed
        assert marker in json.dumps(provider.inputs[-1])
        assert 'Fictional learning response.' in json.dumps(provider.inputs[-1])
        assert len(client.get(path+'/messages').json()['items'])==4
        assert client.get('/api/v1/conversations').json()['items']==[]
        exported=json.dumps(export_records(app.state.services))
        assert marker not in exported and 'Fictional learning response.' not in exported
        assert chat['identity']['id'] not in exported
    for file in profile.rglob('*'):
        if file.is_file():
            data=file.read_bytes()
            assert marker.encode() not in data and chat['identity']['id'].encode() not in data


@pytest.mark.parametrize('kind',['learning','case'])
def test_context_change_during_reply_blocks_late_assistant_publication(tmp_path,kind):
    from renulus.storage.invalidation import bump_context_epoch
    app=app_at(tmp_path/'context-change')
    provider=ConversationProvider()
    def invalidate():
        with app.state.services.db.transaction() as conn:
            bump_context_epoch(conn)
    provider.on_reply=invalidate
    app.state.services.registry.update(provider=provider,knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind}).json()
        path=f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        result=event_payloads(client.post(path+'/messages',json={'expected_revision':chat['revision'],'text':'Fictional learning request','request_id':'invalidated-reply-123'}))
        assert result[-1]['type']=='error'
        assert result[-1]['payload']['code']=='dependency_changed'
        assert [row['role'] for row in client.get(path+'/messages').json()['items']]==['user']
        assert client.get(path+'/draft').json()['text']=='Fictional learning request'


@pytest.mark.parametrize('kind',['learning','case'])
def test_explicit_save_promotes_temporary_owner_once_and_preserves_history(tmp_path,kind):
    profile=tmp_path/'explicit-promotion'
    app=app_at(profile)
    app.state.services.registry.update(provider=ConversationProvider(),knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind,'temporary':True}).json()
        path=f"/api/v1/conversations/{kind}/{chat['identity']['id']}"
        flow=event_payloads(client.post(path+'/messages',json={'expected_revision':chat['revision'],'text':'Fictional explicitly retained learning','request_id':'before-save-request'}))
        assert flow[-1]['type']=='completed'
        current=client.get(path).json()
        body={'expected_revision':current['revision']}
        headers={'Idempotency-Key':'explicit-save-request'}
        promoted=client.post(path+'/save',json=body,headers=headers)
        assert promoted.status_code==200,promoted.text
        assert promoted.json()['identity']==chat['identity'] and promoted.json()['retention']=='saved'
        assert client.post(path+'/save',json=body,headers=headers).json()==promoted.json()
    with TestClient(app_at(profile)) as client:
        assert client.get(path).json()['retention']=='saved'
        assert [row['role'] for row in client.get(path+'/messages').json()['items']]==['user','assistant']


class PausedProvider(ConversationProvider):
    async def stream(self, messages, **options):
        import asyncio
        self.inputs.append(messages.copy())
        self.release = asyncio.Event()
        yield 'Fictional partial response.'
        await self.release.wait()
        yield ' Fictional completed response.'


@pytest.mark.parametrize('kind',['learning','case'])
def test_saved_producer_outlives_subscription_and_stop_preserves_terminal_winner(tmp_path,kind):
    import asyncio
    from renulus.learn.conversation_models import Send
    app=app_at(tmp_path/'detached-response')
    provider=PausedProvider()
    app.state.services.registry.update(provider=provider,knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind}).json()
        identifier=chat['identity']['id']
        path=f'/api/v1/conversations/{kind}/{identifier}'
        streams=app.state.services.get('conversations').streaming
        async def detach():
            entry,receipt=streams.begin(kind,identifier,Send(expected_revision=chat['revision'],text='Fictional saved request',request_id='detached-request-123'))
            streams.launch(entry)
            subscription=streams.events(entry,receipt)
            await anext(subscription)
            await subscription.aclose()
            for _ in range(50):
                if hasattr(provider,'release'):
                    break
                await asyncio.sleep(.01)
            return receipt['run_id']
        run_id=client.portal.call(detach)
        status=client.get(path+'/runs/'+run_id)
        assert status.status_code==200,status.text
        assert status.json()['state']=='running'
        assert client.get(path+'/runs').json()['items'][0]['run_id']==run_id
        async def finish():
            provider.release.set()
            await streams.tasks[run_id]
        client.portal.call(finish)
        assert client.get(path+'/runs/'+run_id).json()['state']=='completed'
        assert client.post(path+'/runs/'+run_id+'/cancel').json()['state']=='completed'
        assert [row['role'] for row in client.get(path+'/messages').json()['items']]==['user','assistant']
        assert client.get(path+'/draft').json()['text']==''
        # Status reads stay neutral even before shared middleware exemptions.
        app.state.services.db.execute(
            "INSERT INTO assessment_test_attempts(id,version_id,version_snapshot_json,mode,clock_high_water_at,created_at,updated_at) VALUES('active-policy-test','unavailable','{}','test',?,?,?)",
            (chat['created_at'],)*3)
        assert streams.status(kind,identifier,run_id)=={'run_id':run_id,'state':'completed'}
        assert 'conversation' not in streams.list(kind,identifier)['items'][0]


def test_restart_reconciles_saved_receipt_without_provider_or_erasing_draft(tmp_path):
    from renulus.learn.conversation_models import Send
    profile=tmp_path/'interrupted-response'
    app=app_at(profile)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={}).json()
        identifier=chat['identity']['id']
        streams=app.state.services.get('conversations').streaming
        _,receipt=streams.begin('learning',identifier,Send(expected_revision=chat['revision'],text='Fictional interrupted request',request_id='interrupted-request-123'))
        # Abrupt exit leaves a running receipt. A new runtime owns reconciliation.
        restarted=app_at(profile)
        provider=ConversationProvider()
        restarted.state.services.registry['provider']=provider
        with TestClient(restarted) as other:
            path=f'/api/v1/conversations/learning/{identifier}'
            state=other.get(path+'/runs/'+receipt['run_id']).json()
            assert state['state']=='interrupted'
            assert other.get(path+'/draft').json()['text']=='Fictional interrupted request'
            assert [m['role'] for m in other.get(path+'/messages').json()['items']]==['user']
            assert provider.inputs==[]



@pytest.mark.parametrize('kind',['learning','case'])
def test_temporary_subscription_close_stops_producer_without_saved_command(tmp_path,kind):
    from renulus.learn.conversation_models import Send
    from renulus.storage.backup import export_records
    app=app_at(tmp_path/'volatile-subscription')
    provider=PausedProvider()
    app.state.services.registry.update(provider=provider,knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        chat=client.post('/api/v1/conversations',json={'kind':kind,'temporary':True}).json()
        identifier=chat['identity']['id']
        streams=app.state.services.get('conversations').streaming
        async def detach():
            entry,receipt=streams.begin(kind,identifier,Send(expected_revision=chat['revision'],text='FICTIONAL_VOLATILE_RUN_3187',request_id='volatile-detached-123'))
            subscription=streams.events(entry,receipt)
            await anext(subscription)
            await anext(subscription)
            await subscription.aclose()
            return receipt['run_id']
        run_id=client.portal.call(detach)
        assert streams.status(kind,identifier,run_id)['state']=='cancelled'
        assert run_id not in streams.active and streams.tasks=={}
        exported=json.dumps(export_records(app.state.services))
        assert identifier not in exported and 'FICTIONAL_VOLATILE_RUN_3187' not in exported
