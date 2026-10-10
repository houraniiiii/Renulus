# SPDX-License-Identifier: MIT
"""Project membership links independent canonical owners through real APIs."""
from fastapi.testclient import TestClient
import json
import shutil
import pytest

from test_design_c_conversations import app_at


def project_app(profile):
    from renulus.study.project_api import create_router
    app = app_at(profile)
    if 'projects' not in app.state.services.registry:
        app.include_router(create_router(app.state.services), prefix='/api/v1')
    return app


def test_projects_move_and_unassign_chats_without_copying_or_deleting_owner(tmp_path):
    profile = tmp_path / 'project-membership'
    with TestClient(project_app(profile)) as client:
        first = client.post('/api/v1/study/projects', json={'title': 'Glomerular study'}).json()
        second = client.post('/api/v1/study/projects', json={'title': 'Transplant study'}).json()
        chat = client.post('/api/v1/conversations', json={'project_id': first['id']}).json()
        path = f"/api/v1/conversations/learning/{chat['identity']['id']}"
        assert chat['project_id'] == first['id']
        moved = client.put(path + '/project', json={'expected_revision': chat['revision'], 'project_id': second['id']})
        assert moved.status_code == 200, moved.text
        assert client.get('/api/v1/study/projects/' + first['id']).json()['chats'] == []
        assert client.get('/api/v1/study/projects/' + second['id']).json()['chats'][0]['identity'] == chat['identity']
    with TestClient(project_app(profile)) as client:
        detail = client.get('/api/v1/study/projects/' + second['id']).json()
        assert client.delete('/api/v1/study/projects/' + second['id'], params={'expected_revision': detail['revision']}).status_code == 200
        independent = client.get(path).json()
        assert independent['project_id'] is None and independent['identity'] == chat['identity']
        assert len(client.get('/api/v1/conversations').json()['items']) == 1
        assert client.get('/api/v1/learn/threads/' + chat['identity']['id']).status_code == 200


@pytest.mark.parametrize('format_version', [1,2])
def test_shared_document_unlink_stays_unlinked_through_older_zip_restore(tmp_path, format_version):
    from renulus.storage.recovery_archive import backup_to
    from renulus.storage.recovery_segmented import backup_segmented_to
    from renulus.storage.database import utc_now
    app = project_app(tmp_path / 'shared-document')
    services = app.state.services
    now = utc_now()
    # Ready synthetic canonical Library revision. No extractor or provider call.
    with services.db.transaction() as conn:
        conn.execute('INSERT INTO knowledge_documents VALUES(?,?,?,?,?,0,?,?,NULL,?,?)',
            ('fictional-document','Fictional nephrology note','original','personal-library',None,'fictional-revision','fictional-revision',now,now))
        conn.execute('INSERT INTO knowledge_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            ('fictional-revision','fictional-document',1,'ready','0'*64,'text/plain',0,None,'{}',
             json.dumps({'model_input':True,'index':True,'embedding':True}),None,None,None,now,now))
    with TestClient(app) as client:
        projects = [client.post('/api/v1/study/projects', json={'title': title}).json() for title in ['First project','Second project']]
        for project in projects:
            linked = client.put('/api/v1/study/projects/' + project['id'] + '/documents',
                json={'expected_revision':project['revision'],'revision_id':'fictional-revision','position':3})
            assert linked.status_code == 200, linked.text
        for project in projects:
            docs = client.get('/api/v1/study/projects/' + project['id']).json()['documents']
            assert [doc['revision_id'] for doc in docs] == ['fictional-revision']
        archive = services.paths.cache / 'older-links.zip'
        (backup_to if format_version==1 else backup_segmented_to)(services,archive)
        first = client.get('/api/v1/study/projects/' + projects[0]['id']).json()
        unlinked = client.delete('/api/v1/study/projects/' + first['id'] + '/documents/fictional-revision',
            params={'expected_revision':first['revision']})
        assert unlinked.status_code == 200, unlinked.text
        recovery = services.registry['data_recovery']
        identifier,directory = recovery.begin_preview()
        keep = False
        try:
            shutil.copyfile(archive,directory/'input.zip')
            preview = recovery.complete_preview(identifier,directory)
            keep = True
        finally:
            recovery.end_upload(directory,keep=keep)
        recovery.restore_preview(identifier,preview['exported_at'],True)
        assert client.get('/api/v1/study/projects/' + first['id']).json()['documents'] == []
        second = client.get('/api/v1/study/projects/' + projects[1]['id']).json()
        assert len(second['documents']) == 1
        assert client.delete('/api/v1/study/projects/' + second['id'],params={'expected_revision':second['revision']}).status_code == 200
        assert client.get('/api/v1/library/documents/fictional-document').status_code == 200


def test_project_goal_keeps_manual_and_real_evidence_progress_with_retry_and_restart(tmp_path):
    from test_design_c_conversations import ConversationProvider,event_payloads
    from renulus.storage.backup import export_records,restore_records
    profile=tmp_path/'project-goals'
    app=project_app(profile)
    app.state.services.registry.update(provider=ConversationProvider(),knowledge=None,retrieval=None,memory=None)
    with TestClient(app) as client:
        project=client.post('/api/v1/study/projects',json={'title':'Fictional transplant study'}).json()
        path='/api/v1/study/projects/'+project['id']
        chat=client.post('/api/v1/conversations',json={'project_id':project['id']}).json()
        sent=event_payloads(client.post('/api/v1/conversations/learning/'+chat['identity']['id']+'/messages',
            json={'expected_revision':chat['revision'],'text':'Fictional transplant learning','request_id':'goal-evidence-request-123'}))
        assert sent[-1]['type']=='completed'
        evidence_id='learn:'+sent[-1]['run_id']
        project=client.get(path).json()
        body={'expected_revision':project['revision'],'title':'Review transplant learning',
            'target_date':'2026-11-01','progress':{'manual_intent':'Review my saved discussion','evidence_ids':[evidence_id]}}
        headers={'Idempotency-Key':'create-project-goal-123'}
        created=client.post(path+'/goals',json=body,headers=headers)
        assert created.status_code==201,created.text
        assert client.post(path+'/goals',json=body,headers=headers).json()==created.json()
        detail=client.get(path).json()
        assert len(detail['goals'])==1
        goal=detail['goals'][0]
        assert goal['progress']=={'manual_intent':'Review my saved discussion','evidence_ids':[evidence_id]}
        invalid={**body,'expected_revision':detail['revision'],'progress':{'evidence_ids':['missing-evidence']}}
        assert client.post(path+'/goals',json=invalid).status_code==409
    app=project_app(profile)
    with TestClient(app) as client:
        detail=client.get(path).json()
        goal=detail['goals'][0]
        completed=client.put(path+'/goals/'+goal['id'],json={**body,'expected_revision':detail['revision'],
            'goal_revision':goal['revision'],'status':'completed','progress':{'manual_intent':'I reviewed the discussion','evidence_ids':[evidence_id]}})
        assert completed.status_code==200,completed.text
        detail=client.get(path).json()
        assert detail['goals'][0]['status']=='completed'
        assert 'percent' not in json.dumps(detail['goals'][0])
        older=export_records(app.state.services)
        removed=client.delete(path+'/goals/'+goal['id'],params={'expected_revision':detail['revision'],'goal_revision':detail['goals'][0]['revision']})
        assert removed.status_code==200,removed.text
        restore_records(app.state.services,older,confirm_older=True)
        assert client.get(path).json()['goals']==[]
        assert client.get('/api/v1/conversations/learning/'+chat['identity']['id']).status_code==200


def save_note_revision(conn, document_id, revision_id, ordinal):
    """Synthetic Notes caller writes its canonical rows before the Project seam."""
    from renulus.storage.database import utc_now
    now = utc_now()
    if ordinal == 1:
        conn.execute('INSERT INTO knowledge_documents VALUES(?,?,?,?,?,0,NULL,?,NULL,?,?)',
            (document_id, 'Fictional study note', 'original', 'personal-library', None, revision_id, now, now))
    else:
        conn.execute('UPDATE knowledge_documents SET latest_revision=? WHERE id=?', (revision_id, document_id))
    conn.execute('INSERT INTO knowledge_revisions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
        (revision_id, document_id, ordinal, 'queued', '0'*64, 'text/plain', 0, None,
         json.dumps({'asset_role':['study-note']}), '{}', None, None, None, now, None))


def test_note_save_transfers_active_and_archived_memberships_without_retrieval_or_pin_rewrite(tmp_path):
    from renulus.storage.invalidation import context_epoch_in
    app = project_app(tmp_path / 'project-note-save')
    services = app.state.services
    with TestClient(app) as client:
        first, second = [client.post('/api/v1/study/projects', json={'title': title}).json()
                         for title in ('Fictional active notes', 'Fictional archived notes')]
        projects = services.get('projects')
        chat = client.post('/api/v1/conversations', json={'project_id': first['id']}).json()
        with services.db.transaction() as conn:
            save_note_revision(conn, 'note-doc', 'note-one', 1)
            projects.note_saved_in(conn, 'note-doc', 'note-one', first['id'])
            projects.note_saved_in(conn, 'note-doc', 'note-one', second['id'])
        old = [client.get('/api/v1/study/projects/'+p['id']).json() for p in (first, second)]
        client.post('/api/v1/study/projects/'+second['id']+'/archive', json={'expected_revision':old[1]['revision']})
        with services.db.transaction() as conn:
            pinned = dict(conn.execute('SELECT * FROM knowledge_revisions WHERE id=?', ('note-one',)).fetchone())
            save_note_revision(conn, 'note-doc', 'note-two', 2)
            epoch = context_epoch_in(conn)
            projects.note_saved_in(conn, 'note-doc', 'note-two')
            assert context_epoch_in(conn) == epoch+1
            projects.note_saved_in(conn, 'note-doc', 'note-two')
            assert context_epoch_in(conn) == epoch+1
            assert dict(conn.execute('SELECT * FROM knowledge_revisions WHERE id=?', ('note-one',)).fetchone()) == pinned
            assert projects.context_in(conn, 'learning', chat['identity']['id'])['revision_ids'] == []
        for previous in old:
            current = client.get('/api/v1/study/projects/'+previous['id']).json()
            assert [d['revision_id'] for d in current['documents']] == ['note-two']
            assert services.db.is_deleted('project_document', previous['documents'][0]['id'])
            assert current['revision'] > previous['revision']


@pytest.mark.parametrize('refusal', ['classification', 'latest', 'document_deleted', 'revision_deleted', 'project_deleted', 'archived', 'rollback'])
def test_note_membership_refusal_rolls_back_callers_saved_revision(tmp_path, refusal):
    from renulus.contracts import ApiError
    app = project_app(tmp_path / 'note-refusal')
    services = app.state.services
    with TestClient(app) as client:
        project = client.post('/api/v1/study/projects', json={'title':'Fictional note rollback'}).json()
        with pytest.raises((ApiError, RuntimeError)):
            with services.db.transaction() as conn:
                save_note_revision(conn, 'refused-note', 'refused-revision', 1)
                if refusal == 'classification':
                    conn.execute("UPDATE knowledge_revisions SET metadata_json='{}' WHERE id='refused-revision'")
                elif refusal == 'latest':
                    conn.execute("UPDATE knowledge_documents SET latest_revision=NULL WHERE id='refused-note'")
                elif refusal in ('document_deleted', 'revision_deleted', 'project_deleted'):
                    entity, identifier = {'document_deleted':('knowledge-document','refused-note'),
                        'revision_deleted':('knowledge-revision','refused-revision'), 'project_deleted':('project',project['id'])}[refusal]
                    services.db.mark_deleted(entity, identifier, conn)
                elif refusal == 'archived':
                    conn.execute("UPDATE study_projects SET lifecycle='archived' WHERE id=?", (project['id'],))
                services.get('projects').note_saved_in(conn, 'refused-note', 'refused-revision', project['id'])
                if refusal == 'rollback':
                    raise RuntimeError('Synthetic owner transaction failure')
        assert client.get('/api/v1/study/projects/'+project['id']).json()['documents'] == []
        assert not services.db.fetch_all('SELECT * FROM knowledge_documents')
        assert not services.db.fetch_all('SELECT * FROM knowledge_revisions')


def test_note_edit_does_not_recreate_explicitly_unlinked_project_membership(tmp_path):
    app = project_app(tmp_path / 'note-unlinked')
    services = app.state.services
    with TestClient(app) as client:
        project = client.post('/api/v1/study/projects', json={'title':'Fictional removed note link'}).json()
        route = '/api/v1/study/projects/'+project['id']
        with services.db.transaction() as conn:
            save_note_revision(conn, 'unlinked-note', 'unlinked-one', 1)
            services.get('projects').note_saved_in(conn, 'unlinked-note', 'unlinked-one', project['id'])
        current = client.get(route).json()
        assert client.delete(route+'/documents/unlinked-one', params={'expected_revision':current['revision']}).status_code == 200
        with services.db.transaction() as conn:
            save_note_revision(conn, 'unlinked-note', 'unlinked-two', 2)
            services.get('projects').note_saved_in(conn, 'unlinked-note', 'unlinked-two')
        assert client.get(route).json()['documents'] == []
