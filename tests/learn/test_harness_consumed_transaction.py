# SPDX-License-Identifier: MIT
"""Canonical consumed closure with scripted native IO; no engines/providers."""
from contextlib import closing
import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, EligibleInput, canonical_digest
from renulus.storage import Database
from renulus.server import create_app
from test_harness_bridge import collect, native_at
from test_harness_reconciliation import LostAcknowledgement, install


PIN = EligibleInput(kind='memory', dependency=Dependency(
    target={'type': 'memory_revision', 'id': 'synthetic-fact:1'}, expected_revision='1'))
CITATION = {'content_ref': {'target': {'type': 'library_revision', 'id': 'synthetic-source'},
    'locator': {'kind': 'pdf', 'physical_page': 3}}, 'passage_id': 'synthetic-passage'}
SOURCE = Dependency(target={'type': 'library_revision', 'id': 'synthetic-source'},
    expected_revision='1' * 64)


async def test_rejected_wrapper_closure_cannot_poison_check_or_publication(tmp_path):
    published = []

    def validate(conn, *, inputs, dependencies):
        assert conn.in_transaction
        if PIN in inputs:
            raise ApiError('synthetic_pin_revoked', 'Synthetic local pin is revoked.', 409)

    def publish(conn, answer, entry):
        assert conn.in_transaction
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=validate, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        with pytest.raises(ApiError, match='Synthetic local pin'):
            bridge.record_consumed(receipt['run_id'], inputs=(PIN,), citations=(CITATION,))
        bridge.check(receipt['run_id'])
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert published[0].inputs == published[0].dependencies == ()
        assert published[0].citations == []
        assert bridge.completed(receipt['run_id'])['inputs'] == []
    finally:
        await services.finish_shutdown()


async def test_committed_child_closure_controls_check_checkpoint_and_final_publication(tmp_path):
    published, current = [], [True]

    def validate(conn, *, inputs, dependencies):
        assert conn.in_transaction
        if PIN in inputs and not current[0]:
            raise ApiError('synthetic_pin_revoked', 'Synthetic committed pin is revoked.', 409)

    def publish(conn, answer, entry):
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=validate, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        with services.db.transaction() as conn:
            bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,),
                dependencies=(SOURCE,), citations=(CITATION,))
        current[0] = False
        with pytest.raises(ApiError, match='Synthetic committed pin'):
            bridge.check(receipt['run_id'])
        current[0] = True
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert published[0].inputs == (PIN,)
        assert published[0].dependencies == (SOURCE, PIN.dependency)
        assert published[0].citations == [CITATION]
        assert bridge.completed(receipt['run_id'])['inputs'] == [PIN.model_dump(mode='json')]
    finally:
        await services.finish_shutdown()


async def test_supplied_transaction_rollback_drops_child_closure_before_publication(tmp_path):
    published, checked_connections = [], []

    def validate(conn, *, inputs, dependencies):
        assert conn.in_transaction
        checked_connections.append(conn)

    def publish(conn, answer, entry):
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=validate, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        with pytest.raises(RuntimeError, match='synthetic outer rollback'):
            with services.db.transaction() as conn:
                bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,),
                    dependencies=(SOURCE,), citations=(CITATION,))
                assert checked_connections and all(checked is conn for checked in checked_connections)
                raise RuntimeError('synthetic outer rollback')
        bridge.check(receipt['run_id'])
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert published[0].inputs == published[0].dependencies == ()
        assert published[0].citations == []
        assert bridge.completed(receipt['run_id'])['citations'] == []
    finally:
        await services.finish_shutdown()


async def test_final_publication_cannot_drop_closure_added_in_the_same_transaction(tmp_path):
    published = []

    def validate(conn, **closure):
        assert conn.in_transaction

    def publish(conn, answer, entry):
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=validate, publish_answer_in=publish)
    producer = None
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        producer = bridge.answer(entry)
        async for event in producer:
            if event.type == 'completed':
                break
        with services.db.transaction() as conn:
            bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,),
                dependencies=(SOURCE,), citations=(CITATION,))
            with pytest.raises(ApiError) as rejected:
                bridge.publish_in(conn, entry)
            assert rejected.value.code == 'harness_answer_conflict'
        assert published == []
        assert bridge.completed(receipt['run_id']) is None
    finally:
        if producer is not None:
            await producer.aclose()
        await services.finish_shutdown()


async def test_wrapper_encoding_failure_cannot_commit_pins_or_citations(tmp_path):
    published, revoked = [], [False]

    def validate(conn, *, inputs, dependencies):
        if PIN in inputs and revoked[0]:
            raise ApiError('synthetic_pin_revoked', 'Synthetic rolled-back pin is revoked.', 409)

    def publish(conn, answer, entry):
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=validate, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        with pytest.raises(ValueError):
            bridge.record_consumed(receipt['run_id'], inputs=(PIN,),
                citations=({**CITATION, 'text': float('nan')},))
        revoked[0] = True
        bridge.check(receipt['run_id'])
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert published[0].inputs == () and published[0].citations == []
    finally:
        await services.finish_shutdown()


async def test_retired_reservation_rejects_child_closure_before_native_submission(tmp_path):
    services, repo, bridge, transport, identifier, request = native_at(tmp_path,
        check_dependencies_in=lambda conn, **closure: None)
    try:
        _, receipt = repo.streaming.begin('learning', identifier, request)
        assert await bridge.cancel(receipt['run_id']) == {'state': 'not-submitted'}
        with services.db.transaction() as conn:
            with pytest.raises(ApiError) as rejected:
                bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,))
            assert rejected.value.code == 'harness_answer_conflict'
        assert transport.calls == []
        assert bridge.completed(receipt['run_id']) is None
    finally:
        await services.finish_shutdown()


async def test_closed_connection_denies_consumption_with_transaction_error(tmp_path):
    services, repo, bridge, _, identifier, request = native_at(tmp_path)
    conn = services.db.connect()
    conn.close()
    try:
        _, receipt = repo.streaming.begin('learning', identifier, request)
        with pytest.raises(ApiError) as rejected:
            bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,))
        assert rejected.value.code == 'harness_transaction_required'
        bridge.check(receipt['run_id'])
    finally:
        await services.finish_shutdown()


@pytest.mark.parametrize('conflict_kind', ['input', 'dependency'])
async def test_caught_conflicting_pin_preserves_root_and_child_merge(tmp_path, conflict_kind):
    published = []
    child = EligibleInput(kind='memory', dependency=Dependency(
        target={'type': 'memory_revision', 'id': 'synthetic-child-fact:2'}, expected_revision='2'))
    changed = PIN.dependency.model_copy(update={'expected_revision': '2'})
    root_citation = {**CITATION, 'text': 'Synthetic transient root passage.'}
    child_citation = {**CITATION, 'passage_id': 'synthetic-child-passage'}

    def publish(conn, answer, entry):
        published.append(answer)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=lambda conn, **closure: None, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        bridge.record_consumed(receipt['run_id'], inputs=(PIN,), citations=(root_citation,))
        with services.db.transaction() as conn:
            for _ in range(2):
                bridge.record_consumed_in(conn, receipt['run_id'], inputs=(child,),
                    dependencies=(SOURCE,), citations=(child_citation,))
            with pytest.raises(ApiError) as rejected:
                bridge.record_consumed_in(conn, receipt['run_id'],
                    **({'inputs': (PIN.model_copy(update={'dependency': changed}),)}
                        if conflict_kind == 'input' else {'dependencies': (changed,)}))
            assert rejected.value.code == 'harness_dependency_conflict'
            bridge.check(receipt['run_id'], conn=conn)
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert published[0].inputs == (PIN, child)
        assert published[0].dependencies == (PIN.dependency, SOURCE, child.dependency)
        assert published[0].citations == [CITATION, child_citation]
        assert bridge.completed(receipt['run_id'])['citations'] == [CITATION, child_citation]
    finally:
        await services.finish_shutdown()


@pytest.mark.parametrize(('connection', 'code'), [
    ('inactive', 'harness_transaction_required'), ('foreign', 'harness_connection_mismatch')])
async def test_consumption_requires_active_same_profile_transaction(tmp_path, connection, code):
    services, repo, bridge, _, identifier, request = native_at(tmp_path)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        scope = (closing(services.db.connect()) if connection == 'inactive'
            else Database(tmp_path / 'synthetic-other-profile.sqlite').transaction())
        with scope as conn:
            with pytest.raises(ApiError) as rejected:
                bridge.record_consumed_in(conn, receipt['run_id'], inputs=(PIN,))
            assert rejected.value.code == code
        bridge.check(receipt['run_id'])
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert bridge.completed(receipt['run_id'])['inputs'] == []
    finally:
        await services.finish_shutdown()


@pytest.mark.parametrize('committed', [False, True])
async def test_original_app_reopen_recovers_only_committed_child_closure(tmp_path, committed):
    published, revoked = [], [False]

    def validate(conn, *, inputs, dependencies):
        assert conn.in_transaction
        if PIN in inputs and revoked[0]:
            raise ApiError('synthetic_pin_revoked', 'Synthetic rolled-back recovery pin is revoked.', 409)

    def publish(conn, answer, entry):
        assert conn.in_transaction
        published.append(answer)
        return canonical_digest(answer.reference())

    transport = LostAcknowledgement()
    services, repo, bridge, _, identifier, request = native_at(tmp_path, transport,
        check_dependencies_in=validate)
    reopened = None
    try:
        def admitted(run_id, input_id):
            bridge.bind_input(run_id, session_id='ses_synthetic', input_id=input_id)
            if committed:
                with services.db.transaction() as conn:
                    bridge.record_consumed_in(conn, run_id, inputs=(PIN,),
                        dependencies=(SOURCE,), citations=(CITATION,))
            else:
                with pytest.raises(RuntimeError, match='synthetic report rollback'):
                    with services.db.transaction() as conn:
                        bridge.record_consumed_in(conn, run_id, inputs=(PIN,),
                            dependencies=(SOURCE,), citations=(CITATION,))
                        raise RuntimeError('synthetic report rollback')

        transport.on_input = admitted
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        events = await collect(repo.streaming, entry, receipt)
        assert events[-1]['payload']['code'] == 'harness_command_uncertain'
        await services.finish_shutdown()
        revoked[0] = not committed
        reopened = create_app(tmp_path / 'synthetic-bridge')
        _, recovered = install(reopened, transport,
            check_dependencies_in=validate, publish_answer_in=publish)
        assert [item['id'] for item in (await recovered.messages(identifier))['items']] == [
            'msg_user', 'msg_answer']
        assert len(published) == 1
        assert published[0].inputs == ((PIN,) if committed else ())
        assert published[0].dependencies == ((SOURCE, PIN.dependency) if committed else ())
        assert published[0].citations == ([CITATION] if committed else [])
        assert recovered.completed(receipt['run_id'])['inputs'] == (
            [PIN.model_dump(mode='json')] if committed else [])
        assert transport.prompts == [request.text]
        assert 'session.cancel' not in transport.calls
    finally:
        await services.finish_shutdown()
        if reopened is not None:
            await reopened.state.services.finish_shutdown()


async def test_publisher_cannot_overwrite_closure_added_by_its_local_callback(tmp_path):
    callbacks = []

    def publish(conn, answer, entry):
        bridge.record_consumed_in(conn, answer.run_id, inputs=(PIN,),
            dependencies=(SOURCE,), citations=(CITATION,))
        callbacks.append(answer.run_id)
        return canonical_digest(answer.reference())

    services, repo, bridge, _, identifier, request = native_at(tmp_path,
        check_dependencies_in=lambda conn, **closure: None, publish_answer_in=publish)
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        events = await collect(repo.streaming, entry, receipt)
        assert events[-1]['type'] == 'error'
        assert events[-1]['payload']['code'] == 'harness_answer_conflict'
        assert callbacks == [receipt['run_id']]
        assert bridge.completed(receipt['run_id']) is None
        assert repo.draft('learning', identifier)['text'] == request.text
    finally:
        await services.finish_shutdown()
