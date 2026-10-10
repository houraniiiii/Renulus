# SPDX-License-Identifier: MIT
"""Real Study exposure, HTTP handoffs and late canonical publication refusal."""
import asyncio
import json

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

from renulus.assessment.attempt_models import HelpRequest, SaveDraft, StartAttempt
from renulus.contracts import ApiError
from renulus.design_c_contracts import QuestionSnapshot, SavedTestVersion
from renulus.server import create_app
from renulus.storage import utc_now
from renulus.storage.publication import bind_publication_guard
from renulus.storage.study_help import StudyHelpContext, require_context_in


@pytest.fixture
def study(tmp_path):
    app = create_app(tmp_path / 'study-help')
    services = app.state.services
    version = SavedTestVersion(id='help_version', test_id='help_test', ordinal=1, origin='imported',
        review_quality='personal', status='ready', provenance={'method':'import'}, created_at=utc_now(),
        terms='Synthetic owned teaching material', items=[QuestionSnapshot(item_id='help_item', question_id='help_question',
        question_version='1', key_version='1', family_id='help_family', family_version='1', topic_id='general',
        stem='Which synthetic learning option is suitable?', options=[{'id':'a','text':'First learning option'},
        {'id':'b','text':'Second learning option'}], correct_option_ids=['a'], explanation='PRIVATE_HELP_KEY_SENTINEL')])
    with services.db.transaction() as conn:
        services.get('saved_tests').publish_version(conn, version, title='Synthetic Study help',
            provenance={'schema':'saved-test-provenance/1'}, idempotency_key='help-version-publication')
    owner = services.get('whole_attempts')
    attempt = owner.start(StartAttempt(version={'type':'saved_test_version','id':version.id}), 'help-start-study')
    receipt = owner.help(attempt['id'], HelpRequest(expected_revision=attempt['draft_revision'], expected_policy_revision=attempt['policy']['revision'],
        item_id='help_item', kind='chat'), 'help-open-chat')
    return app, attempt, receipt['context']


def invalidate(app, attempt):
    return app.state.services.get('whole_attempts').save(attempt['id'], SaveDraft(expected_revision=attempt['draft_revision'],
        position=0, answers=[{'item_id':'help_item','option_ids':['b'],'marked':False}]), 'help-change-draft')


def test_current_receipt_prepares_only_the_public_question_and_guards_saved_chat(study):
    app, attempt, context = study
    client = TestClient(app)
    prepared = client.post('/api/v1/study/help-context', json=context)
    assert prepared.status_code == 200
    assert 'PRIVATE_HELP_KEY_SENTINEL' not in prepared.text
    assert prepared.json()['seed_text'].endswith('a. First learning option\nb. Second learning option'.replace('\\n','\n'))
    headers = {'X-Renulus-Study-Context': json.dumps(context), 'Idempotency-Key':'help-create-conversation'}
    first = client.post('/api/v1/conversations', json={'title':'Study question'}, headers=headers)
    assert first.status_code == 201
    assert client.post('/api/v1/conversations', json={'title':'Study question'}, headers=headers).json() == first.json()
    assert len(app.state.services.db.fetch_all('SELECT * FROM learn_conversations')) == 1
    invalidate(app, attempt)
    assert client.post('/api/v1/conversations', json={'title':'Study question'}, headers=headers).status_code == 409
    assert len(app.state.services.db.fetch_all('SELECT * FROM learn_conversations')) == 1


@pytest.mark.parametrize('change', ['extra','wrong_item','wrong_kind','duplicate'])
def test_forged_context_never_opens_or_publishes_help(study, change):
    app, _, context = study
    context = dict(context)
    if change == 'extra': context['private_key'] = 'PRIVATE_HELP_KEY_SENTINEL'
    if change == 'wrong_item': context['item_id'] = 'other_item'
    if change == 'wrong_kind': context['kind'] = 'notes'
    encoded = json.dumps(context)
    if change == 'duplicate': encoded = encoded[:-1] + ',"kind":"chat"}'
    response = TestClient(app).get('/api/v1/workspace/entries', headers={'X-Renulus-Study-Context':encoded})
    assert response.status_code in (409,422)
    assert 'PRIVATE_HELP_KEY_SENTINEL' not in response.text


@pytest.mark.asyncio
async def test_detached_help_task_keeps_canonical_guard_after_request_returns(study):
    app, attempt, context = study
    services = app.state.services
    release = asyncio.Event()
    outcome = []
    task = None
    @app.post('/api/v1/reader-background-publication')
    async def start():
        async def publish():
            await release.wait()
            try:
                services.db.execute('INSERT INTO preferences VALUES(?,?,?)', ('synthetic.help-output','PRIVATE_HELP_KEY_SENTINEL',utc_now()))
                outcome.append('published')
            except ApiError as error:
                outcome.append(error.code)
        nonlocal task
        task = asyncio.create_task(publish())
        return {'state':'running'}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://127.0.0.1') as client:
        response = await client.post('/api/v1/reader-background-publication', headers={'X-Renulus-Study-Context':json.dumps(context)})
        assert response.status_code == 200
        invalidate(app, attempt)
        release.set()
        await asyncio.wait_for(task, 3)
    assert outcome == ['revision_conflict']
    assert services.db.fetch_one("SELECT * FROM preferences WHERE key='synthetic.help-output'") is None


def test_commit_rechecks_help_receipt_and_rolls_back_on_same_transaction_change(study):
    app, attempt, context = study
    services = app.state.services
    parsed = StudyHelpContext.model_validate(context)
    with pytest.raises(ApiError):
        with bind_publication_guard(services.db, lambda conn: require_context_in(services, conn, parsed)):
            with services.db.transaction() as conn:
                conn.execute('UPDATE assessment_test_attempts SET draft_revision=draft_revision+1 WHERE id=?', (attempt['id'],))
                conn.execute('INSERT INTO preferences VALUES(?,?,?)', ('synthetic.help-output','PRIVATE_HELP_KEY_SENTINEL',utc_now()))
    assert services.get('whole_attempts').get(attempt['id'])['draft_revision'] == attempt['draft_revision']
    assert services.db.fetch_one("SELECT * FROM preferences WHERE key='synthetic.help-output'") is None
