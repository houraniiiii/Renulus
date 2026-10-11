"""Actual native history and learner-memory context through private IPC."""
import asyncio
import json
import os
from pathlib import Path
import subprocess

from renulus.contracts import ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.memory.models import ManualFact
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app


async def test_native_followup_excludes_revoked_memory_history_before_model_dispatch(tmp_path):
    from renulus.runtime.harness_learning import HarnessLearningOwner

    root = tmp_path / 'profile'
    root.mkdir()
    assets = Path(os.environ['RENULUS_LIBRARY_HELPERS']).resolve()
    subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{assets}' | Out-Null"], check=True)
    services = create_app(root).state.services
    memory = services.get('memory')
    original = await asyncio.to_thread(memory.add, ManualFact(
        text='For synthetic CKD learning, explain albuminuria before filtration.',
        scope=ContextScope(kind=Scope.STUDY), idempotency_key='native-context-root'))
    config = HarnessProcessConfig(node_executable=Path(os.environ['RENULUS_HARNESS_NODE']),
        host_entry=Path(__file__).resolve().parents[2] / 'packages/harness/test/fixtures/learning-memory-host.mjs',
        profile_root=root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3',
        max_inflight=1, max_domain_inflight=1)
    owner = HarnessLearningOwner(services, config, configuration_id='synthetic-h05',
        memory=memory, context_filtering=True)
    owner.install()
    try:
        await owner.start()
        repo = services.get('conversations')
        chat = repo.create(NewConversation())

        async def answer(summary, text, key):
            entry, receipt = repo.streaming.begin('learning', summary['identity']['id'],
                Send(expected_revision=summary['revision'], text=text, request_id=key))
            async with asyncio.timeout(60):
                events = [json.loads(encoded.split('data: ', 1)[1])
                    async for encoded in repo.streaming.events(entry, receipt)]
            assert events[-1]['type'] == 'completed', json.dumps(events, indent=2)
            return events[-1]['payload']

        first = await answer(chat, 'Explain synthetic CKD albuminuria.', 'memory-first')
        ref = first['answer_reference']
        assert any(item['kind'] == 'memory' and item['dependency']['target']['id'] ==
            f"{original['id']}:{original['revision']}" for item in ref['inputs'])
        resolved = await owner.resolve_completed_answer(ref)
        assert resolved['text'] == 'Synthetic CKD explanation.'
        assert resolved['digest'] == ref['sha256']
        assert resolved['input']['inputs'] == ref['inputs']
        second = await answer(first['conversation'], 'Continue synthetic CKD.', 'memory-followup')
        assert any(item['kind'] == 'committed_evidence' and item['dependency']['target']['id'] ==
            'learn-answer:' + ref['run_id'] for item in second['answer_reference']['inputs'])
        await asyncio.to_thread(memory.edit, original['id'],
            'For synthetic CKD learning, explain filtration before albuminuria.', original['revision'])
        third = await answer(second['conversation'], 'Continue corrected synthetic CKD.', 'memory-corrected')
        assert not any(item['kind'] == 'committed_evidence' for item in third['answer_reference']['inputs'])
        observed = (await owner.process.request('host.status', {}, 'context-proof', '1', 5))['result']
        assert observed['modelCalls'] == 3
        first_ids = {ref['input_id'], *ref['message_ids']}
        second_ids = {second['answer_reference']['input_id'], *second['answer_reference']['message_ids']}
        sent_second = {item['id'] for item in observed['contexts'][1]['messages']}
        sent_third = {item['id'] for item in observed['contexts'][2]['messages']}
        assert first_ids <= sent_second
        assert not (first_ids | second_ids) & sent_third
        assert 'explain albuminuria before filtration' in json.dumps(observed['contexts'][0]['system'])
        assert 'explain filtration before albuminuria' in json.dumps(observed['contexts'][2]['system'])
        assert services.db.fetch_all('SELECT * FROM learn_messages') == []
        assert memory.repository.jobs() == []  # Migrated automatic capture remains disabled.
    finally:
        await owner.close()
        await memory.close()
        services.get('helpers').startup.close()
