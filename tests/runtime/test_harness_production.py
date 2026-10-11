"""Production entry and real native stores, without account or inference grants."""
import asyncio
import json
import os
from pathlib import Path

from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app


async def test_production_entry_keeps_an_unadmitted_model_turn_failed_without_a_second_transcript(tmp_path):
    services = create_app(tmp_path / 'profile').state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ['RENULUS_HARNESS_NODE']),
        host_entry=Path(__file__).resolve().parents[2] / 'packages/harness/src/main.mjs',
        profile_root=services.paths.root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3',
        max_inflight=1, max_domain_inflight=1)
    owner = HarnessLearningOwner(services, config, configuration_id='synthetic-denied', context_filtering=True)
    owner.install()
    try:
        await owner.start()
        chat = owner.repo.create(NewConversation())
        entry, receipt = owner.repo.streaming.begin('learning', chat['identity']['id'],
            Send(expected_revision=chat['revision'], text='Explain synthetic dialysis learning.',
                request_id='production-unknown-authority'))
        async with asyncio.timeout(25):
            events = [json.loads(value.split('data: ', 1)[1])
                async for value in owner.repo.streaming.events(entry, receipt)]
        assert events[-1]['type'] == 'error', events
        assert events[-1]['payload']['code'] == 'harness_execution_failed'
        assert all(event['type'] != 'completed' for event in events)
        history = await owner.bridge.messages(chat['identity']['id'])
        assert [message['role'] for message in history['items']] == ['user']
        assert history['items'][0]['content'] == 'Explain synthetic dialysis learning.'
        observed = await owner.process.request('host.status', {}, 'status', '1', 5)
        assert observed['result']['activeSessionIds'] == []
    finally:
        await owner.close()
        assert (await owner.process.settlement(0))['state'] == 'settled'
        services.get('helpers').startup.close()
