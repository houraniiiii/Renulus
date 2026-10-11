# SPDX-License-Identifier: MIT
"""H06 preparation: public retained history and the actual SDK import capability."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
import pytest

from renulus.server import create_app

REPO = Path(__file__).resolve().parents[2]
NODE = Path(os.environ.get('RENULUS_HARNESS_NODE', ''))
pytestmark = pytest.mark.skipif(
    not os.environ.get('RENULUS_HARNESS_NODE') or not NODE.is_file() or
    not (REPO / 'packages/harness/node_modules/@opencode/sdk/package.json').is_file(),
    reason='Requires managed Node 26.4.0 and the pinned source-built SDK cohort.')


def native(mode, root, snapshot):
    env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'ComSpec', 'SystemDrive')
        if key in os.environ}
    for key in ('HOME', 'USERPROFILE', 'OPENCODE_TEST_HOME', 'APPDATA', 'LOCALAPPDATA',
                'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME',
                'XDG_RUNTIME_DIR', 'TEMP', 'TMP'):
        owned = root / 'environment' / key.lower()
        owned.mkdir(parents=True, exist_ok=True)
        env[key] = str(owned)
    env['PATH'] = str(NODE.parent)
    output = subprocess.run([str(NODE), str(REPO / 'packages/harness/test/fixtures/h06-import.mjs'),
        mode, str(root), str(snapshot)], env=env, cwd=REPO / 'packages/harness',
        capture_output=True, text=True, timeout=45)
    assert output.returncode == 0, output.stderr
    return json.loads(output.stdout)


async def test_public_legacy_snapshot_imports_exact_native_history_and_reopens_without_dispatch(tmp_path):
    app = create_app(tmp_path / 'synthetic-h06-domain')
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://testserver') as client:
            chat = (await client.post('/api/v1/conversations', json={'title': 'Synthetic transplantation'})).json()
            identifier = chat['identity']['id']
            # Seed historical records only. No legacy or native producer is admitted.
            citation = {'document_id': 'synthetic-document', 'revision_id': 'synthetic-revision',
                'passage_id': 'synthetic-passage', 'locator': {'page': 4},
                'text': 'Synthetic retained passage.'}
            with app.state.services.db.transaction() as conn:
                conn.execute('INSERT INTO learn_runs VALUES(?,?,?,?,?,?,?)',
                    ('synthetic-legacy-run', identifier, 'synthetic-h06-history', 'completed', None,
                     '2026-10-10T10:00:00+00:00', '2026-10-10T10:00:01+00:00'))
                for mid, role, text, citations, created in (
                    ('legacy-user', 'user', 'Synthetic transplant potassium 5.2 mmol/L.', [], '2026-10-10T10:00:00+00:00'),
                    ('legacy-answer', 'assistant', 'Synthetic retained answer, not current advice.', [citation], '2026-10-10T10:00:01+00:00')):
                    conn.execute('INSERT INTO learn_messages VALUES(?,?,?,?,?,?,?)',
                        (mid, identifier, 'synthetic-legacy-run', role, text, json.dumps(citations), created))
            route = '/api/v1/learn/threads/' + identifier
            original = (await client.get(route)).json()
            snapshot = tmp_path / 'retained-legacy.json'
            snapshot.write_text(json.dumps(original), encoding='utf-8')
            root = tmp_path / 'synthetic-h06-native'
            staged = native('import', root, snapshot)
            assert staged == {'acknowledged': False,
                'commands': ['session.create', 'session.remove', 'session.import'], 'model_calls': 0}
            reopened = native('observe', root, snapshot)
            assert reopened['commands'] == ['session.get', 'session.export']
            assert reopened['model_calls'] == 0
            assert reopened['info']['metadata']['lineage'] == 'unknown'
            assert reopened['info']['id'] == 'ses_' + hashlib.sha256(identifier.encode()).hexdigest()
            for actual, expected in zip(reopened['messages'], original['messages'], strict=True):
                assert actual['id'] == 'msg_' + hashlib.sha256((identifier + '/' + expected['id']).encode()).hexdigest()
                assert actual['type'] == expected['role']
                text = actual['text'] if actual['type'] == 'user' else actual['content'][0]['text']
                assert text == expected['content']
                assert actual['metadata']['legacy']['citations'] == expected['citations']
                assert actual['metadata']['legacy']['id'] == expected['id']
                assert actual['metadata']['lineage'] == 'unknown'
            assert (await client.get(route)).json() == original
            # Importing a native stage does not activate a domain mapping.
            assert app.state.services.db.fetch_all('SELECT * FROM learn_harness_mappings') == []
            removed = native('delete', root, snapshot)
            assert removed == {'deleted': True, 'unavailable': 'Session.NotFoundError',
                'commands': ['session.remove', 'session.get'], 'model_calls': 0}
            assert (await client.get(route)).json() == original
    finally:
        await app.state.services.shutdown()
