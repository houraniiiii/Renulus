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
