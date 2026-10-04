# SPDX-License-Identifier: MIT
"""The capacity experiment is isolated and its disk staging retains canonical rows."""
import json
import importlib.util
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/measure_recovery_capacity.py'


@pytest.fixture(scope='module')
def capacity_case(tmp_path_factory):
    work = tmp_path_factory.mktemp('capacity') / 'bench'
    result = subprocess.run([sys.executable, '-B', str(SCRIPT),
        '--source-root', str(ROOT), '--work-dir', str(work), '--documents', '3',
        '--passages', '32', '--text-bytes', '512', '--segment-bytes', '65536',
        '--row-bytes', '16384', '--canonical-budget-bytes', '2097152'],
        capture_output=True, text=True, timeout=150)
    assert result.returncode == 0, result.stderr + result.stdout
    report = json.loads(result.stdout)
    spec = importlib.util.spec_from_file_location('measure_recovery_capacity', SCRIPT)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    with sqlite3.connect(work / 's/state/renulus.sqlite3') as conn:
        conn.row_factory = sqlite3.Row
        definitions = tool.schema(conn)
    return work, report, tool, definitions


def test_capacity_experiment_preserves_unicode_citation_and_journal_with_real_schema(capacity_case):
    work, report, _, _ = capacity_case
    assert report['production_restore_supported'] is False
    assert report['legacy']['status'] == 'within_bounds'
    assert report['segmented']['status'] == 'validated'
    assert report['segmented']['tables']['knowledge_documents'] == 3
    assert report['segmented']['tables']['knowledge_passages'] == 32
    assert report['segmented']['segments'] > 1
    assert report['legacy']['measurement']['python_peak_bytes'] > 0
    assert report['segmented']['measurement']['python_peak_bytes'] > 0
    assert report['current_limits']['json_bytes'] == 16777216
    with sqlite3.connect(work / 'stage.sqlite3') as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM knowledge_passages WHERE id=?', ('pass_0000000000',)).fetchone()
        assert 'Δ' in row['text'] and 'SYNTHETIC' in row['text']
        assert json.loads(row['locators_json']) == [{'page': 1, 'item_id': '#/texts/0'}]
        assert json.loads(row['headings_json']) == ['SYNTHETIC ckd heading']
        assert conn.execute('SELECT COUNT(*) FROM knowledge_source_status_events').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM content_active_pack WHERE pack_version=?', ('1.1.0',)).fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM knowledge_revisions WHERE extraction_json IS NOT NULL').fetchone()[0] == 0
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert 'knowledge_catalogue' not in names and 'preferences' not in names
    assert report['segmented']['source_digest'] == report['segmented']['staged_digest']


def test_late_segment_corruption_rolls_back_all_scratch_records(capacity_case, tmp_path):
    work, report, tool, definitions = capacity_case
    segments = tmp_path / 'segments'
    shutil.copytree(work / 'segments', segments)
    manifest = json.loads((segments / 'manifest.json').read_text(encoding='utf-8'))
    last = segments / manifest['segments'][-1]['path']
    lines = last.read_bytes().splitlines(keepends=True)
    frame = json.loads(lines[-1])
    # A valid scalar with identical byte length gets through record/schema checks;
    # the final segment hash must still refuse it after earlier rows were staged.
    original = frame['row']['created_at']
    frame['row']['created_at'] = '3' + original[1:]
    lines[-1] = json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode() + b'\n'
    assert len(lines[-1]) == len(last.read_bytes().splitlines(keepends=True)[-1])
    last.write_bytes(b''.join(lines))
    stage = tmp_path / 'failed.sqlite3'
    with pytest.raises(tool.CapacityError, match='integrity'):
        tool.stage_segments(segments, stage, definitions, report['synthetic'])
    with sqlite3.connect(stage) as conn:
        for table in definitions:
            assert conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0, table
    with sqlite3.connect(work / 'stage.sqlite3') as conn:
        assert conn.execute('SELECT COUNT(*) FROM knowledge_passages').fetchone()[0] == 32


def test_experimental_descriptor_cannot_reach_sibling_owner_state(capacity_case, tmp_path):
    work, report, tool, definitions = capacity_case
    segments = tmp_path / 'segments'
    shutil.copytree(work / 'segments', segments)
    owner = tmp_path / 'owner.txt'
    owner.write_text('OWNER STATE', encoding='utf-8')
    manifest = json.loads((segments / 'manifest.json').read_text(encoding='utf-8'))
    manifest['segments'][0]['path'] = '../owner.txt'
    (segments / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    stage = tmp_path / 'refused.sqlite3'
    with pytest.raises(tool.CapacityError, match='descriptor'):
        tool.stage_segments(segments, stage, definitions, report['synthetic'])
    assert not stage.exists() and owner.read_text(encoding='utf-8') == 'OWNER STATE'


def test_experimental_record_budget_refuses_without_partial_stage(capacity_case, tmp_path):
    work, report, tool, definitions = capacity_case
    stage = tmp_path / 'bounded.sqlite3'
    limited = {**report['synthetic'], 'record_budget': 10}
    with pytest.raises(tool.CapacityError, match='record budget'):
        tool.stage_segments(work / 'segments', stage, definitions, limited)
    with sqlite3.connect(stage) as conn:
        assert conn.execute('SELECT COUNT(*) FROM content_case_versions').fetchone()[0] == 0


def test_existing_capacity_workspace_is_refused_before_runtime_access(tmp_path):
    sentinel = tmp_path / 'owner.txt'
    sentinel.write_text('OWNER STATE', encoding='utf-8')
    result = subprocess.run([sys.executable, '-B', str(SCRIPT),
        '--source-root', str(tmp_path / 'missing-runtime'), '--work-dir', str(tmp_path)],
        capture_output=True, text=True, timeout=20)
    assert result.returncode != 0 and 'already exists' in result.stderr
    assert sentinel.read_text(encoding='utf-8') == 'OWNER STATE'
    assert list(tmp_path.iterdir()) == [sentinel]
