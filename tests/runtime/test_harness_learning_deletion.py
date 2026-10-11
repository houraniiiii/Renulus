# SPDX-License-Identifier: MIT
"""Saved-owner deletion over the actual native store; account/HTTP are synthetic."""
import asyncio

import pytest

from renulus.contracts import ApiError
from renulus.learn.conversation_models import Mutation, NewConversation, Send
from renulus.runtime.harness_process import ManagedHarnessProcess
from test_harness_learning_models import (PROMPT, collect_events, command, learning_models)
from test_harness_model_dispatch_sdk import offline


@pytest.mark.parametrize('route', ['conversation', 'legacy'])
async def test_deleted_saved_owner_purges_native_session_without_another_dispatch(tmp_path, offline, route):
    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get("conversations")
        chat = repo.create(NewConversation(), "native-delete-create")
        thread_id = chat["identity"]["id"]
        entry, receipt = repo.streaming.begin("learning", thread_id,
            Send(expected_revision=chat["revision"], text=PROMPT, request_id="native-delete-send"))
        counter.release.set()
        observer.release.set()
        events = await collect_events(repo, entry, receipt)
        assert events[-1]["type"] == "completed", events
        run_id = entry["run"].id
        assert authority.run(run_id)["state"] == "settled"
        assert registries[-1].status().owned == 0
        before = await command(owner.process, "session.find", operation=run_id)
        assert len(before["sessions"]) == 1
        retained = await owner.process.request('session.messages',
            {'session_id': before['sessions'][0]['id'], 'limit': 20}, run_id, '1', 5)
        assert retained['outcome'] == 'committed_reference', retained
        assert retained['result']['messages']
        unrelated = await owner.process.request('host.status', {}, 'unrelated-status', '1', 5)
        revision = repo.get("learning", thread_id)["revision"]
        if route == 'legacy':
            deleted = await services.get('learn').delete_thread(thread_id)
        else:
            deleted = await repo.delete("learning", thread_id, Mutation(expected_revision=revision),
                "native-delete-command")
        assert deleted["deleted"] is True
        after = await command(owner.process, "session.find", operation=run_id)
        assert after["sessions"] == [], "Deleted canonical owners must not retain native transcript bytes."
        assert await owner.process.query_result(retained['request_id']) is None, \
            'Retirement must forget the deleted operation transcript receipt.'
        assert await owner.process.query_result(unrelated['request_id']) == unrelated
        retired = await owner.process.request('session.create', {'title': 'Retired operation replay'},
            run_id, '1', 5)
        assert retired['outcome'] == 'rejected_before_admission', retired
        assert retired['error']['code'] == 'operation_terminal_unavailable'
        assert (await command(owner.process, 'session.find', operation=run_id))['sessions'] == []
        with pytest.raises(ApiError) as missing:
            repo.get("learning", thread_id)
        assert missing.value.code == "conversation_missing"
        with pytest.raises(ApiError) as replay:
            repo.create(NewConversation(), "native-delete-create")
        assert replay.value.code == "command_terminal_unavailable"
        assert len(observer.calls) == 1
        assert authority.run(run_id)["spent_dispatches"] == 1
        assert owner.process.domain_status()["active"] == 0
        if route == 'conversation':
            generation = owner.process.native_identity().generation
            seal = owner.seal_new_runs(expected_effective=owner.configuration_id)
            try:
                assert (await owner.process.close(10))['state'] == 'closed'
                assert (await owner.process.settlement(10))['state'] == 'settled'
                owner.replace_process(ManagedHarnessProcess(domain_authority=owner.authorize),
                    configuration_id=owner.configuration_id, seal=seal)
                await owner.start()
            finally:
                seal.release()
            assert owner.process.native_identity().generation != generation
            replay = await owner.process.request('session.create', {'title': 'Deleted restart replay'}, run_id, '1', 5)
            assert replay['outcome'] == 'rejected_before_admission', replay
            assert replay['error']['code'] == 'operation_terminal_unavailable'
            assert (await command(owner.process, 'session.find', operation=run_id))['sessions'] == []
            assert len(observer.calls) == 1


async def test_cancelled_delete_observer_keeps_new_runs_sealed_until_actual_cleanup(tmp_path, offline):
    entered, release = asyncio.Event(), asyncio.Event()

    class ObservedRemoval(ManagedHarnessProcess):
        async def request(self, command, payload, operation_id, attempt_id, timeout):
            response = await super().request(command, payload, operation_id, attempt_id, timeout)
            if command == 'session.remove':
                entered.set()
                await release.wait()
            return response

    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get('conversations')
        chat = repo.create(NewConversation(), 'held-delete-create')
        second = repo.create(NewConversation(), 'held-delete-other')
        thread_id = chat['identity']['id']
        entry, receipt = repo.streaming.begin('learning', thread_id, Send(
            expected_revision=chat['revision'], text=PROMPT, request_id='held-delete-send'))
        counter.release.set()
        observer.release.set()
        assert (await collect_events(repo, entry, receipt))[-1]['type'] == 'completed'
        seal = owner.seal_new_runs(expected_effective=owner.configuration_id)
        try:
            assert (await owner.process.close(10))['state'] == 'closed'
            assert (await owner.process.settlement(10))['state'] == 'settled'
            owner.replace_process(ObservedRemoval(domain_authority=owner.authorize),
                configuration_id=owner.configuration_id, seal=seal)
            await owner.start()
        finally:
            seal.release()
        deletion = asyncio.create_task(repo.delete('learning', thread_id, Mutation(
            expected_revision=repo.get('learning', thread_id)['revision']), 'held-delete-command'))
        try:
            await asyncio.wait_for(entered.wait(), 10)
            deletion.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(deletion, 2)
            with pytest.raises(ApiError) as sealed:
                repo.streaming.begin('learning', second['identity']['id'], Send(
                    expected_revision=second['revision'], text=PROMPT, request_id='held-delete-new'))
            assert sealed.value.code == 'harness_configuration_busy'
            assert len(observer.calls) == 1
        finally:
            release.set()
        await owner.purge_native_owners()
        assert (await command(owner.process, 'session.find', operation=entry['run'].id))['sessions'] == []
        assert len(observer.calls) == 1
