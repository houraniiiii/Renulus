# SPDX-License-Identifier: MIT
"""Actual saved transfer/SDK/SQLite; legacy response and account data are synthetic."""
import httpx
import asyncio
import json
import pytest
import test_harness_learning_models as model_fixture
from renulus.contracts import ApiError

from renulus.design_c_contracts import ConversationDraft
from renulus.learn.conversation_models import NewConversation, Send
from renulus.assessment.test_models import CreateReviewedTestRequest
from renulus.assessment.attempt_models import StartAttempt
from renulus.server import create_app
from test_harness_learning_models import PROMPT, collect_events, command, learning_models
from test_harness_model_dispatch_sdk import offline
from renulus.runtime.harness_process import ManagedHarnessProcess
from test_harness_learning_purge_reconciliation import replace_settled_process


class LegacyProvider:
    async def stream(self, messages, **options):
        yield 'Retained legacy transplantation explanation.\nUnknown historical lineage.'

    async def cancel(self, run_id):
        return True


class HeldTransferAcknowledgment(ManagedHarnessProcess):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.entered, self.release = asyncio.Event(), asyncio.Event()
        self.commands = []

    async def request(self, command, payload, operation_id, attempt_id, timeout):
        result = await super().request(command, payload, operation_id, attempt_id, timeout)
        self.commands.append(command)
        if command == 'session.import.stage':
            self.entered.set()
            await self.release.wait()
        return result


async def saved_legacy(tmp_path):
    services = create_app(tmp_path / 'profile').state.services
    services.registry['provider'] = LegacyProvider()
    repo = services.get('conversations')
    chat = repo.create(NewConversation(title='Synthetic transplantation history'), 'migration-create')
    identifier = chat['identity']['id']
    entry, receipt = repo.streaming.begin('learning', identifier, Send(
        expected_revision=chat['revision'], text='Explain synthetic graft rejection.',
        request_id='migration-legacy-send'))
    assert (await collect_events(repo, entry, receipt))[-1]['type'] == 'completed'
    draft = repo.save_draft('learning', identifier, ConversationDraft(
        expected_revision=repo.get('learning', identifier)['revision'],
        text='My unsent transplant follow-up.', content_refs=[]), 'migration-draft')
    original = repo.messages('learning', identifier)
    public = repo.get('learning', identifier)
    await repo.streaming.close()
    services.get('helpers').startup.close()
    return identifier, public, draft, original


async def test_public_saved_history_migrates_once_without_generation_or_replacing_legacy_rows(tmp_path, offline):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get('conversations')
        result = await owner.migrate_saved(identifier, expected_revision=public['revision'])
        assert result.state == 'active' and result.retirement == 'retired'
        assert result.mapping.conversation.id == identifier
        assert len(result.message_refs) == 2
        assert [ref.legacy_id for ref in result.message_refs] == [item['id'] for item in original['items']]
        assert all(ref.lineage == 'unknown' and ref.context_eligible is False
            and ref.capture_eligible is False for ref in result.message_refs)
        assert repo.messages('learning', identifier) == original
        assert await owner.bridge.messages(identifier) == original
        assert repo.get('learning', identifier) == public
        assert repo.draft('learning', identifier) == draft
        again = await owner.migrate_saved(identifier, expected_revision=public['revision'])
        assert again == result
        native = await command(owner.process, 'session.messages',
            {'session_id': result.mapping.runtime.session_id, 'limit': 20})
        assert {item['id'] for item in native['messages']} == {ref.native_id for ref in result.message_refs}
        assert (await command(owner.process, 'session.get',
            {'session_id': result.mapping.runtime.session_id}))['execution'] == 'settled'
        assert counter.calls == [] and observer.calls == [] and transports == [] and admissions == []
        assert registries[-1].status().owned == 0
        assert owner.process.domain_status()['active'] == 0


async def test_migrated_saved_owner_continues_without_admitting_unknown_imported_context(tmp_path, offline):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get('conversations')
        result = await owner.migrate_saved(identifier, expected_revision=public['revision'])
        entry, receipt = repo.streaming.begin('learning', identifier, Send(
            expected_revision=public['revision'], text=PROMPT, request_id='migration-native-continuation'))
        counter.release.set()
        observer.release.set()
        events = await collect_events(repo, entry, receipt)
        if events[-1]['type'] != 'completed':
            native = await command(owner.process, 'session.get',
                {'session_id': result.mapping.runtime.session_id})
            raise AssertionError((events, native, len(counter.calls), len(observer.calls)))
        reference = events[-1]['payload']['answer_reference']
        assert reference['runtime']['session_id'] == result.mapping.runtime.session_id
        assert len(counter.calls) == len(observer.calls) == 1
        body, manifest = counter.calls[0]
        assert len(manifest.messages) == 1 and manifest.messages[0].role == 'user'
        assert manifest.messages[0].content[0].text == PROMPT
        assert b'Unknown historical lineage' not in body and b'synthetic graft rejection' not in body
        history = await owner.bridge.messages(identifier)
        assert history['items'][:2] == original['items']
        assert len(history['items']) == 4
        assert repo.messages('learning', identifier) == original
        assert authority.run(entry['run'].id)['spent_dispatches'] == 1
        current = repo.get('learning', identifier)
        assert await owner.migrate_saved(identifier, expected_revision=current['revision']) == result
        assert len(counter.calls) == len(observer.calls) == 1
        assert owner.process.domain_status()['active'] == 0
        assert registries[-1].status().owned == 0


async def test_public_http_saved_migration_preserves_legacy_facade_and_strict_revision(tmp_path, offline, monkeypatch):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    apps = []
    original_create = model_fixture.create_app
    def observed_app(*args, **kwargs):
        app = original_create(*args, **kwargs)
        apps.append(app)
        return app
    monkeypatch.setattr(model_fixture, 'create_app', observed_app)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=apps[-1]), base_url='http://testserver') as client:
            url = '/api/v1/conversations/learning/' + identifier + '/migrate'
            response = await client.post(url, json={'expected_revision': public['revision']})
            assert response.status_code == 200, response.text
            result = response.json()
            assert result['state'] == 'active' and result['retirement'] == 'retired'
            assert (await client.post(url, json={'expected_revision': public['revision']})).json() == result
            assert (await client.get('/api/v1/conversations/learning/' + identifier + '/messages')).json() == original
            assert (await client.post(url, json={'expected_revision': public['revision'], 'session_id': 'forged'})).status_code == 422
            stale = await client.post(url, json={'expected_revision': public['revision'] - 1})
            assert stale.status_code == 409
            assert stale.json()['error']['code'] == 'conversation_revision_conflict'
            assert (await client.get('/api/v1/conversations/learning/' + identifier + '/draft')).json() == draft
        assert counter.calls == observer.calls == transports == admissions == []


async def test_stale_completed_migration_does_not_block_a_valid_saved_send(tmp_path, offline, monkeypatch):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    apps = []
    original_create = model_fixture.create_app
    def observed_app(*args, **kwargs):
        app = original_create(*args, **kwargs)
        apps.append(app)
        return app
    monkeypatch.setattr(model_fixture, 'create_app', observed_app)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=apps[-1]), base_url='http://testserver') as client:
            url = '/api/v1/conversations/learning/' + identifier
            migrated = await client.post(url + '/migrate', json={'expected_revision': public['revision']})
            assert migrated.status_code == 200 and migrated.json()['retirement'] == 'retired'
            stale = await client.post(url + '/migrate', json={'expected_revision': public['revision'] - 1})
            assert stale.status_code == 409 and stale.json()['error']['code'] == 'conversation_revision_conflict'
            counter.release.set()
            observer.release.set()
            async with asyncio.timeout(40):
                sent = await client.post(url + '/messages', json={'expected_revision': public['revision'],
                    'text': PROMPT, 'request_id': 'after-stale-migration'})
            assert sent.status_code == 200, sent.text
            events = [json.loads(line.split('data: ', 1)[1]) for line in sent.text.splitlines() if line.startswith('data: ')]
            assert events[-1]['type'] == 'completed', events[-1]
        assert len(counter.calls) == len(observer.calls) == 1


async def test_transfer_observation_timeout_keeps_root_gate_until_exact_reconciliation(tmp_path, offline):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        process = HeldTransferAcknowledgment(domain_authority=owner.authorize)
        await replace_settled_process(owner, process)
        repo = services.get('conversations')
        pending = asyncio.create_task(owner.migrate_saved(identifier, expected_revision=public['revision']))
        try:
            await asyncio.wait_for(process.entered.wait(), 10)
            with pytest.raises(ApiError) as expired:
                await pending
            assert expired.value.code == 'harness_migration_observation_timeout'
            assert owner.saved_transfer.status()['active'] == 1
            other = repo.create(NewConversation(), 'migration-other-owner')
            with pytest.raises(ApiError) as busy:
                repo.streaming.begin('learning', other['identity']['id'], Send(
                    expected_revision=other['revision'], text=PROMPT, request_id='migration-pending-new-root'))
            assert busy.value.code == 'harness_configuration_busy'
            assert (await command(process, 'host.status'))['state'] == 'ready'
        finally:
            process.release.set()
            await asyncio.gather(pending, return_exceptions=True)
        await owner.saved_transfer.settled()
        result = await owner.migrate_saved(identifier, expected_revision=public['revision'])
        assert result.state == 'active' and result.retirement == 'retired'
        assert process.commands.count('session.import.stage') == 1
        assert process.commands.count('session.import') == 1
        seal = owner.seal_new_runs(expected_effective=owner.configuration_id)
        seal.release()
        assert counter.calls == observer.calls == transports == admissions == []


async def test_ordinary_saved_send_migrates_legacy_history_then_reopens_one_native_owner(tmp_path, offline, monkeypatch):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    apps = []
    original_create = model_fixture.create_app
    def observed_app(*args, **kwargs):
        app = original_create(*args, **kwargs)
        apps.append(app)
        return app
    monkeypatch.setattr(model_fixture, 'create_app', observed_app)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        path = '/api/v1/conversations/learning/' + identifier
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=apps[-1]), base_url='http://testserver') as client:
            assert (await client.get(path + '/messages')).json() == original
            project = (await client.post('/api/v1/study/projects',
                json={'title': 'Synthetic transplant review'})).json()
            moved = await client.put(path + '/project', json={
                'expected_revision': public['revision'], 'project_id': project['id']})
            assert moved.status_code == 200, moved.text
            archived = await client.post(path + '/archive', json={
                'expected_revision': moved.json()['revision']})
            assert archived.status_code == 200, archived.text
            restored = await client.post(path + '/restore', json={
                'expected_revision': archived.json()['revision']})
            assert restored.status_code == 200, restored.text
            assert (await client.get(path + '/draft')).json()['text'] == draft['text']
            request = {'expected_revision': restored.json()['revision'], 'text': PROMPT,
                'request_id': 'migration-ordinary-send'}
            counter.release.set()
            observer.release.set()
            sent = await client.post(path + '/messages', json=request)
            assert sent.status_code == 200, sent.text
            events = [json.loads(line[6:]) for line in sent.text.splitlines()
                if line.startswith('data: ')]
            assert events[-1]['type'] == 'completed', events
            reference = events[-1]['payload']['answer_reference']
            history = (await client.get(path + '/messages')).json()
            assert history['items'][:2] == original['items']
            assert len(history['items']) == 4
            assert (await client.get(path)).json()['project_id'] == project['id']
            assert (await client.get(path + '/draft')).json()['text'] == ''
            assert len(counter.calls) == len(observer.calls) == 1
            assert len(counter.calls[0][1].messages) == 1
            replay = await client.post(path + '/messages', json=request)
            assert replay.status_code == 200, replay.text
            assert len(counter.calls) == len(observer.calls) == 1
            generation = owner.process.native_identity().generation
            await replace_settled_process(owner, ManagedHarnessProcess(domain_authority=owner.authorize))
            assert owner.process.native_identity().generation != generation
            assert (await client.get(path + '/messages')).json() == history
            assert (await command(owner.process, 'session.get',
                {'session_id': reference['runtime']['session_id']}))['execution'] == 'settled'
            assert (await client.get(path)).json()['project_id'] == project['id']
            assert (await client.get(path + '/draft')).json()['text'] == ''
            assert len(counter.calls) == len(observer.calls) == 1
            assert authority.run(reference['run_id'])['state'] == 'settled'
            assert owner.process.domain_status()['active'] == 0
            assert registries[-1].status().owned == 0
            retained = await owner.process.request('session.messages',
                {'session_id': reference['runtime']['session_id'], 'limit': 20},
                reference['run_id'], '1', 5)
            assert retained['outcome'] == 'committed_reference' and retained['result']['messages']
            current = (await client.get(path)).json()
            deleted = await client.delete(path, params={'expected_revision': current['revision']})
            assert deleted.status_code == 200, deleted.text
            assert await owner.process.query_result(retained['request_id']) is None, \
                'Deletion must retire new turns as well as the originating migration.'
            assert (await command(owner.process, 'session.find', operation=reference['run_id']))['sessions'] == []
            assert (await client.get(path)).status_code == 404
            retired = await client.post('/api/v1/conversations', json={
                'title': 'Synthetic transplantation history'}, headers={'Idempotency-Key': 'migration-create'})
            assert retired.status_code == 410, retired.text
            project_after = await client.get('/api/v1/study/projects/' + project['id'])
            assert project_after.status_code == 200 and project_after.json()['chats'] == []
            assert len(counter.calls) == len(observer.calls) == 1


async def test_migrated_stop_keeps_draft_and_disconnected_retry_finishes_with_neutral_test_status(tmp_path, offline):
    identifier, public, draft, original = await saved_legacy(tmp_path)
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get('conversations')
        await owner.migrate_saved(identifier, expected_revision=public['revision'])
        entry, receipt = repo.streaming.begin('learning', identifier, Send(
            expected_revision=public['revision'], text=PROMPT, request_id='migration-explicit-stop'))
        stopped_events = asyncio.create_task(collect_events(repo, entry, receipt))
        stop = None
        try:
            await asyncio.wait_for(counter.entered.wait(), 20)
            stop = asyncio.create_task(repo.streaming.cancel('learning', identifier, entry['run'].id))
            async with asyncio.timeout(5):
                while not admissions[-1].cancellation.cancelled:
                    await asyncio.sleep(.01)
            counter.release.set()
            stopped = await asyncio.wait_for(asyncio.shield(stop), 15)
            assert stopped['state'] == 'cancelled'
        finally:
            counter.release.set()
            counter.finalizer_release.set()
            await asyncio.gather(stopped_events, *([stop] if stop is not None else []), return_exceptions=True)
        assert (await stopped_events)[-1]['type'] == 'cancelled'
        assert observer.calls == transports == []
        assert authority.run(entry['run'].id)['state'] == 'settled'
        assert authority.run(entry['run'].id)['spent_dispatches'] == 0
        assert repo.draft('learning', identifier)['text'] == PROMPT
        assert (await owner.bridge.messages(identifier))['items'][:2] == original['items']
        current = repo.get('learning', identifier)
        counter.release.clear()
        counter.entered.clear()
        next_entry, next_receipt = repo.streaming.begin('learning', identifier, Send(
            expected_revision=current['revision'], text=PROMPT, request_id='migration-disconnected-retry'))
        repo.streaming.launch(next_entry)
        connection = repo.streaming.events(next_entry, next_receipt)
        try:
            assert 'started' in await anext(connection)
            await asyncio.wait_for(counter.entered.wait(), 20)
            await connection.aclose()
            run_id = next_entry['run'].id
            assert repo.streaming.status('learning', identifier, run_id)['state'] == 'running'
            assert (await command(owner.process, 'host.status'))['state'] == 'ready'
        finally:
            counter.release.set()
            observer.release.set()
            await connection.aclose()
        async with asyncio.timeout(15):
            while repo.streaming.status('learning', identifier, run_id)['state'] == 'running':
                await asyncio.sleep(.02)
        assert repo.streaming.status('learning', identifier, run_id)['state'] == 'completed'
        assert (await owner.settle_run(next_entry, timeout=10))['state'] == 'settled'
        assert len(observer.calls) == len(transports) == 1
        assert authority.run(run_id)['state'] == 'settled'
        assert authority.run(run_id)['spent_dispatches'] == 1
        assert repo.draft('learning', identifier)['text'] == ''
        history = await owner.bridge.messages(identifier)
        assert history['items'][:2] == original['items']
        assert len(history['items']) == 5
        test = services.get('saved_tests').create_reviewed(CreateReviewedTestRequest(
            count=1, idempotency_key='migration-neutral-reviewed-test'))
        attempt = services.get('whole_attempts').start(StartAttempt(
            version={'type': 'saved_test_version', 'id': test['version_id']},
            mode='test'), 'migration-neutral-active-test')
        assert attempt['mode'] == 'test' and attempt['status'] == 'active'
        assert repo.streaming.status('learning', identifier, run_id, neutral=True) == {
            'run_id': run_id, 'state': 'completed'}
        assert repo.streaming.status('learning', identifier, run_id) == {
            'run_id': run_id, 'state': 'completed'}
        with pytest.raises(ApiError) as restricted:
            await owner.bridge.messages(identifier)
        assert restricted.value.code == 'assistance_restricted'
        assert len(observer.calls) == 1
