"""Synthetic retained originals: authority, digest, no-replace and late bytes."""
import hashlib
from pathlib import Path
from threading import RLock

import pytest
from pydantic import ValidationError, TypeAdapter

from renulus.workers.artifacts import Refused
from renulus.workers.knowledge_io import KnowledgeIO, ProtectedHandles
from renulus.workers.native_contracts import NativePaths, NativeIntent, NativeInput


INPUT = TypeAdapter(NativeInput)
OUT = dict(artifact_handle='output_synthetic', artifact_revision=1, max_bytes=1024,
    expires_at_ms=9007199254740991, reservation_id='output_reservation', intent_id='output_intent')


class Budget:
    def __init__(self):
        self.reserved, self.settled = [], []

    def reserve(self, reservation_id, intent_id, peak_bytes):
        self.reserved.append((reservation_id, intent_id, peak_bytes))

    def settle(self, reservation_id, intent_id, **values):
        self.settled.append((reservation_id, intent_id, values))


def intent(body=b'synthetic kidney learning note', **changes):
    value = dict(intent_id='intent_synthetic', reservation_id='reservation_synthetic',
        revision_id='revision_synthetic', bytes=len(body), sha256=hashlib.sha256(body).hexdigest(),
        stamp='a' * 64, media_type='text/plain')
    value.update(changes)
    return NativeIntent(**value)


def operation(action, **values):
    return INPUT.validate_python(dict(action=action, output=OUT, **values))


def owned(tmp_path, *, selection=None):
    root = tmp_path / 'managed'
    root.mkdir()
    grants = tmp_path / 'grants'
    grants.mkdir()
    config = NativePaths(originals_root=str(root / 'originals'), budget_root=str(root),
        grants_root=str(grants), grant_token_sha256='0' * 64)
    budget = Budget()
    io = KnowledgeIO(config, handles=ProtectedHandles(config, selection=selection), storage=budget,
        opener=lambda path: (_ for _ in ()).throw(AssertionError('No physical OS handoff in tests')))
    return io, budget


def test_selected_handle_cannot_read_before_intent_or_rebind_and_read_verifies_digest(tmp_path):
    body = b'synthetic glomerular learning note'
    source = tmp_path / 'selected.txt'
    source.write_bytes(body)
    calls = []
    io, budget = owned(tmp_path, selection=lambda handle: calls.append(handle) or source)
    i = intent(body)
    selection = operation('read_selection', handle='selected_synthetic', intent=i)
    try:
        with pytest.raises(Refused):
            io.execute(selection, None, lambda: True, RLock())
        assert not calls and not budget.reserved
        io.execute(operation('reserve', intent=i), None, lambda: True, RLock())
        assert io.execute(selection, None, lambda: True, RLock()) == body
        assert calls == ['selected_synthetic']
        # Selection remains pinned to this intent, not a caller-supplied path.
        with pytest.raises(OSError):
            source.write_bytes(b'changed')
        bad = i.model_copy(update={'sha256': 'f' * 64})
        with pytest.raises(Refused):
            io.execute(operation('read_selection', handle='selected_synthetic', intent=bad), None, lambda: True, RLock())
        io.execute(operation('settle', intent=i.model_copy(update={'stamp': 'b' * 64}), state='failed'), None, lambda: True, RLock())
        assert budget.settled[-1][2]['cleanup_debt_bytes'] == 0
    finally:
        io.close()


def test_late_publication_retains_native_lease_and_debt_and_never_replaces(tmp_path, monkeypatch):
    from renulus.knowledge.original_io import RetainedOriginalIO
    io, budget = owned(tmp_path)
    body = b'synthetic transplant learning note'
    i = intent(body)
    live = [True]
    original_publish = RetainedOriginalIO.publish

    def publish_and_cancel(self, data):
        original_publish(self, data)
        live[0] = False

    io.execute(operation('reserve', intent=i), None, lambda: True, RLock())
    monkeypatch.setattr(RetainedOriginalIO, 'publish', publish_and_cancel)
    publish = operation('publish', intent=i, artifact_handle='body', artifact_revision=1, offset=0, length=len(body))
    try:
        with pytest.raises(Refused) as error:
            io.execute(publish, body, lambda: live[0], RLock())
        assert error.value.code == 'stale_revision'
        record = io.intents[i.intent_id]
        assert record['claimed'] and record['original']
        path = io.root / (record['original'] + '.txt')
        assert path.exists()
        with pytest.raises(OSError):
            path.write_bytes(b'overwrite')
        # Cancellation at return does not dispose the original or reservation.
        assert not budget.settled
        io.execute(operation('settle', intent=i.model_copy(update={'stamp': 'c' * 64}), state='failed'), None, lambda: True, RLock())
        assert budget.settled[-1][2]['cleanup_debt_bytes'] == len(body)
        assert path.read_bytes() == body
        monkeypatch.setattr(RetainedOriginalIO, 'publish', original_publish)
        second = i.model_copy(update={'intent_id': 'other_intent', 'reservation_id': 'other_reservation'})
        io.execute(operation('reserve', intent=second), None, lambda: True, RLock())
        with pytest.raises(OSError):
            io.execute(publish.model_copy(update={'intent': second}), body, lambda: True, RLock())
    finally:
        io.close()


def test_bad_digest_never_claims_original_and_native_schema_forbids_paths(tmp_path):
    io, budget = owned(tmp_path)
    body = b'synthetic AKI note'
    i = intent(body)
    try:
        io.execute(operation('reserve', intent=i), None, lambda: True, RLock())
        with pytest.raises(Refused) as error:
            io.execute(operation('publish', intent=i, artifact_handle='body', artifact_revision=1,
                offset=0, length=len(body)), b'wrong', lambda: True, RLock())
        assert error.value.code == 'digest_mismatch'
        assert not io.intents[i.intent_id]['claimed']
        assert not list(io.root.glob('original_*'))
        with pytest.raises(ValidationError):
            operation('read_selection', handle='selected_synthetic', intent=i, path=str(tmp_path))
    finally:
        io.close()
