# SPDX-License-Identifier: MIT
"""Actual file-import rights over the fixed synthetic learning fixture.

Only the external account/HTTP/count evidence is synthetic. The original managed
app, public import API, CPU Library engines, native tools and publication remain
unchanged. Each case owns a dedicated Python issuer and a fresh paired profile.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import httpx

from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from test_harness_learning_control_backend import SOURCE, document, module, write_document
from test_harness_learning_models import collect_events


PDF = Path('G:/rh02-inputs/synthetic-ckd-study.pdf')
PDF_SHA256 = '64d90e51e3a5aa9c1b8decae3606344e588ddb2abeda75102425c21b8d089bc0'
PROMPT = 'Explain the synthetic CKD study, including renal-study-delta-47, and cite the Library passage.'
TOKEN = 'synthetic-file-permissions-session'


def run_case(tmp_path, *, derivation, record_property):
    data = PDF.read_bytes()
    assert len(data) == 935 and hashlib.sha256(data).hexdigest() == PDF_SHA256
    profile, file, _, startup = document(tmp_path)
    assets = Path('C:/Renulus/dev/helper-assets').resolve()
    assert (assets / 'manifest.json').is_file()
    environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'SystemRoot', 'WINDIR', 'USERPROFILE')
        if key in os.environ}
    environment['PYTHONPATH'] = os.pathsep.join((str(SOURCE / 'runtime'), str(SOURCE / 'upstream/hermes')))
    environment['TEMP'] = environment['TMP'] = str(tmp_path)
    # Docling 2.133 evaluates Path.home() while defining its settings class.
    # Preserve Windows home unchanged; any Docling cache uses this owned root.
    environment['DOCLING_CACHE_DIR'] = str(profile / 'cache/docling')
    completed = subprocess.run([sys.executable, str(Path(__file__)), '--file-permissions-child',
        str(file), write_document(file, startup), str(profile), str(assets), str(PDF),
        '1' if derivation else '0'], env=environment, capture_output=True, text=True,
        encoding='utf-8', errors='replace', timeout=180)
    assert completed.returncode == 0, completed.stderr + completed.stdout
    receipt = json.loads(next(line.removeprefix('FILE_PERMISSION_RECEIPT ')
        for line in completed.stdout.splitlines() if line.startswith('FILE_PERMISSION_RECEIPT ')))
    record_property('file_permission_receipt', json.dumps(receipt, sort_keys=True))
    return receipt


def test_file_without_derivation_is_retrievable_but_refuses_saved_explanation(tmp_path, record_property):
    receipt = run_case(tmp_path, derivation=False, record_property=record_property)
    assert receipt['import_sha256'] == PDF_SHA256 and receipt['import_bytes'] == 935
    assert receipt['rights']['model_input'] is True and receipt['rights']['derivation'] is False
    assert receipt['search_passages'] == 1
    assert receipt['library_errors'] == ['harness_sources_changed']
    assert receipt['terminal'] == 'error' and receipt['answer_published'] is False
    assert receipt['spent_dispatches'] == 1 and receipt['run_state'] == 'settled'
    assert receipt['automatic_jobs'] == 0
    assert receipt['shutdown'] == receipt['native_settlement'] == 'settled'
    observations = receipt['observations']
    assert observations['http_requests'] == observations['completed_http_requests'] == 1
    assert observations['authenticated_requests'] == observations['counter_calls'] == 1
    assert observations['handlers'] == observations['errors'] == 0
    assert observations['finalized_transports'] == 1 and observations['listener_closed'] is True


def test_explicit_file_derivation_completes_exact_cited_answer(tmp_path, record_property):
    receipt = run_case(tmp_path, derivation=True, record_property=record_property)
    assert receipt['import_sha256'] == PDF_SHA256 and receipt['import_bytes'] == 935
    assert receipt['rights']['model_input'] is True and receipt['rights']['derivation'] is True
    assert receipt['search_passages'] == 1 and receipt['library_errors'] == []
    assert receipt['terminal'] == 'completed' and receipt['answer_published'] is True
    assert receipt['citation_opened'] is True
    assert receipt['spent_dispatches'] == 2 and receipt['run_state'] == 'settled'
    assert receipt['automatic_jobs'] == 0
    assert receipt['shutdown'] == receipt['native_settlement'] == 'settled'
    observations = receipt['observations']
    assert observations['http_requests'] == observations['completed_http_requests'] == 2
    assert observations['authenticated_requests'] == observations['counter_calls'] == 2
    assert observations['handlers'] == observations['errors'] == 0
    assert observations['finalized_transports'] == 2 and observations['listener_closed'] is True


async def child_case(file, digest, profile, assets, pdf, *, derivation):
    raw = pdf.read_bytes()
    assert len(raw) == 935 and hashlib.sha256(raw).hexdigest() == PDF_SHA256
    homes = {name: os.environ.get(name) for name in ('USERPROFILE', 'HOME', 'CODEX_HOME')}
    app = module().create_fixture_app(file, digest, profile=profile, helper_assets=assets, token=TOKEN)
    assert {name: os.environ.get(name) for name in homes} == homes
    services = app.state.services
    result = None
    async with app.router.lifespan_context(app):
        owner = services.get('harness_learning')
        authority = app.state.harness_configuration_authority
        assert owner.model_registry.manager is services.get('provider')
        assert authority.activation_snapshot()['admission_open'] is True
        # Exact existing desktop file-import rights, with only derivation varied.
        rights = {'display': True, 'cache': True, 'index': True, 'embedding': True, 'model_input': True,
            'derivation': derivation, 'evaluation': False, 'redistribution': False,
            'licence': 'user-supplied permission',
            'permission_reference': 'User confirms local library processing for the selected file',
            'attribution': ''}
        options = {'title': 'synthetic-ckd-study.pdf', 'rights': rights,
            'scope': {'kind': 'personal-library'}, 'idempotency_key': 'file-permissions-import'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url='http://127.0.0.1:18777', headers={'x-renulus-token': TOKEN}) as client:
            imported = await client.post('/api/v1/library/import/file', content=raw, headers={
                'x-renulus-filename': 'synthetic-ckd-study.pdf',
                'x-renulus-import-options': json.dumps(options)})
            assert imported.status_code == 202, imported.status_code
            source = imported.json()
            async with asyncio.timeout(60):
                while source['status'] in ('queued', 'processing'):
                    await asyncio.sleep(.1)
                    response = await client.get('/api/v1/library/documents/' + source['document_id'] + '/import-status')
                    assert response.status_code == 200
                    source = response.json()
            assert source['status'] == 'ready', {
                'status': source['status'], 'code': source['job'].get('error_code')}
            response = await client.get('/api/v1/library/documents/' + source['document_id'])
            assert response.status_code == 200
            revision = next(item for item in response.json()['revisions'] if item['id'] == source['revision_id'])
            assert revision['rights'] == rights
            assert revision['sha256'] == PDF_SHA256 and revision['media_type'] == 'application/pdf'
            search = await client.post('/api/v1/library/retrieve', json={
                'query': PROMPT, 'scope': {'kind': 'study'}, 'limit': 1})
            assert search.status_code == 200 and search.json()['status'] == 'ready'
            passages = search.json()['passages']
            assert len(passages) == 1 and 'renal-study-delta-47' in passages[0]['text']
            assert passages[0]['document_revision'] == source['revision_id']
            assert passages[0]['locators'] and passages[0]['locators'][0]['page'] == 1
            library_errors = []
            execute = owner.library.execute

            async def observe_execute(command, arguments, trusted):
                try:
                    return await execute(command, arguments, trusted)
                except ApiError as error:
                    library_errors.append(error.code)
                    raise

            # Public execution observation delegates unchanged and retains only
            # safe typed codes; no body, authority or result is substituted.
            owner.library.execute = observe_execute
            conversations = services.get('conversations')
            chat = conversations.create(NewConversation())
            entry, receipt = conversations.streaming.begin('learning', chat['identity']['id'],
                Send(expected_revision=chat['revision'], text=PROMPT, request_id='file-permissions-explain'))
            events = await collect_events(conversations, entry, receipt)
            completed = owner.bridge.completed(entry['run'].id)
            run = authority.run(entry['run'].id)
            result = {'import_sha256': revision['sha256'], 'import_bytes': len(raw), 'rights': revision['rights'],
                'search_passages': len(passages), 'library_errors': library_errors,
                'terminal': events[-1]['type'], 'answer_published': completed is not None,
                'spent_dispatches': run['spent_dispatches'], 'run_state': run['state'],
                'automatic_jobs': len(services.get('memory').repository.jobs())}
            if completed is not None:
                reference = events[-1]['payload']['answer_reference']
                assert len(reference['citations']) == 1
                citation = reference['citations'][0]
                assert citation['document_id'] == source['document_id']
                assert citation['revision_id'] == source['revision_id']
                assert citation['passage_id'] == passages[0]['id']
                opened = services.get('knowledge').citation(source['revision_id'], passage_id=citation['passage_id'])
                assert opened['locators'] == citation['locators'] == passages[0]['locators']
                original = await client.get(opened['original_url'])
                assert original.status_code == 200 and original.content == raw
                answer = await owner.resolve_completed_answer(reference)
                assert answer['text'].strip() and answer['digest'] == hashlib.sha256(answer['text'].encode()).hexdigest()
                assert completed['publication_digest'] == answer['publication_digest']
                result['citation_opened'] = True
            assert owner.process.domain_status()['active'] == 0
            assert owner.model_registry.status().owned == owner.model_registry.status().runs == 0
    result.update(shutdown=services.shutdown_status()['state'],
        native_settlement=(await owner.process.settlement(0))['state'],
        observations=app.state.learning_fixture.observations())
    return result


if __name__ == '__main__':
    assert sys.argv[1] == '--file-permissions-child' and sys.argv[7] in ('0', '1')
    receipt = asyncio.run(child_case(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]),
        Path(sys.argv[5]), Path(sys.argv[6]), derivation=sys.argv[7] == '1'))
    print('FILE_PERMISSION_RECEIPT ' + json.dumps(receipt, sort_keys=True), flush=True)
