"""Connected saved learning: actual native SDK, IPC and offline Library engine."""
import asyncio
import json
import os
from pathlib import Path
import subprocess

from renulus.contracts import ContextScope, Scope
from renulus.learn.conversation_models import NewConversation, Send
from renulus.runtime.harness_process import HarnessProcessConfig
from renulus.server import create_app


async def test_saved_cited_answer_uses_native_ipc_and_real_library_without_second_transcript(tmp_path):
    from renulus.runtime.harness_learning import HarnessLearningOwner

    root = tmp_path / 'profile'
    root.mkdir()
    assets = Path(os.environ['RENULUS_LIBRARY_HELPERS']).resolve()
    subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        f"New-Item -ItemType Junction -Path '{root / 'helpers'}' -Target '{assets}' | Out-Null"], check=True)
    app = create_app(root)
    services = app.state.services
    config = HarnessProcessConfig(node_executable=Path(os.environ['RENULUS_HARNESS_NODE']),
        host_entry=Path(__file__).resolve().parents[2] / 'packages/harness/test/fixtures/learning-host.mjs',
        profile_root=root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3',
        max_inflight=1, max_domain_inflight=1)
    owner = HarnessLearningOwner(services, config, configuration_id='synthetic-h02',
        memory=services.get('memory'), context_filtering=True)
    owner.install()
    try:
        await owner.start()
        source = await asyncio.to_thread(services.get('knowledge').import_text,
            'Synthetic CKD education considers albuminuria and filtration together.',
            scope=ContextScope(kind=Scope.LIBRARY))
        assert source['status'] == 'ready', source
        repo = services.get('conversations')
        chat = repo.create(NewConversation())
        entry, receipt = repo.streaming.begin('learning', chat['identity']['id'],
            Send(expected_revision=chat['revision'], text='Explain synthetic CKD using Library evidence.',
                request_id='saved-library-roundtrip'))
        async with asyncio.timeout(45):
            events = [json.loads(encoded.split('data: ', 1)[1])
                async for encoded in repo.streaming.events(entry, receipt)]
        assert events[-1]['type'] == 'completed', json.dumps(events, indent=2)
        reference = events[-1]['payload']['answer_reference']
        assert reference['citations'], reference
        assert reference['citations'][0]['revision_id'] == source['revision_id']
        assert reference['dependencies'][0]['target'] == {'type': 'library_revision', 'id': source['revision_id']}
        history = await owner.bridge.messages(chat['identity']['id'])
        assert history['items'][-1]['content'] == 'Synthetic cited CKD explanation [1].'
        resolved = await owner.resolve_completed_answer(reference)
        assert resolved['text'] == history['items'][-1]['content']
        citation = services.get('knowledge').citation(source['revision_id'],
            passage_id=reference['citations'][0]['passage_id'])
        assert citation['document_id'] == source['document_id']
        assert reference['citations'][0].get('locators') == citation['locators']
        assert services.db.fetch_all('SELECT * FROM learn_messages') == []
        assert len(services.db.fetch_all('SELECT * FROM learn_harness_answers')) == 1
        assert services.db.fetch_one('SELECT state FROM learn_harness_answers')['state'] == 'completed'
        assert (await owner.process.request('host.status', {}, 'verify', '1', 5))['result']['modelCalls'] == 2
    finally:
        await owner.close()
        await services.get('memory').close()
        services.get('helpers').startup.close()
