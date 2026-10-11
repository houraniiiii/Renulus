"""Typed saved image admission; source bytes and transport are synthetic."""
from renulus.learn.conversation_models import Send
import base64
import json
import pytest
from pydantic import ValidationError
from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation
from renulus.server import create_app


PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg=="
IMAGE = {"type": "image", "media_type": "image/png", "data": PNG}


def test_saved_learning_images_preserve_text_receipt_shape_and_exact_inline_shape():
    expected = {"expected_revision": 1, "text": "Explain a synthetic study image.",
        "request_id": "synthetic-inline-image", "teaching_style": "direct",
        "topic_id": None, "model": None, "freshness": None, "content_refs": []}
    text = Send(expected_revision=1, text=expected["text"], request_id=expected["request_id"])
    assert text.model_dump(mode="json") == expected
    image = Send(expected_revision=1, text=expected["text"], request_id=expected["request_id"],
        images=(IMAGE,))
    assert image.model_dump(mode="json") == {**expected, "images": [IMAGE]}
    assert image.model_dump_json() != text.model_dump_json()


@pytest.mark.parametrize('data', ['!!!!', 'Zg', 'Zh==', 'Zg==\n',
    base64.b64encode(b'x' * (8 * 1024 * 1024 + 1)).decode('ascii')],
    ids=['invalid', 'missing-padding', 'noncanonical-padding', 'whitespace', 'oversized'])
def test_inline_images_reject_noncanonical_or_oversized_bytes(data):
    with pytest.raises(ValidationError):
        Send(expected_revision=1, text='Explain synthetic image.', request_id='image-boundary',
            images=({**IMAGE, 'data': data},))


def test_inline_images_enforce_aggregate_limit_and_exclude_case_preview():
    large = {**IMAGE, 'data': base64.b64encode(b'x' * (8 * 1024 * 1024)).decode('ascii')}
    fields = dict(expected_revision=1, text='Explain synthetic image.', request_id='image-aggregate')
    assert len(Send(**fields, images=(large, large)).images) == 2
    with pytest.raises(ValidationError):
        Send(**fields, images=(large, large, IMAGE))
    with pytest.raises(ValidationError):
        Send(**fields, images=(IMAGE,), image_preview_id='preview_synthetic',
            case_revision=1, model='mimo-v2.6-pro')


def test_inline_image_request_is_frozen_strict_and_preserves_case_preview_shape():
    fields = dict(expected_revision=1, text='Explain synthetic image.', request_id='strict-image-shape')
    for images in (({**IMAGE, 'detail': None},), ({**IMAGE, 'media_type': 'image/svg+xml'},), (IMAGE,) * 5):
        with pytest.raises(ValidationError):
            Send(**fields, images=images)
    admitted = Send(**fields, images=(IMAGE,))
    with pytest.raises(ValidationError):
        admitted.images[0].data = 'eA=='
    case = Send(**fields, image_preview_id='preview_synthetic', case_revision=1, model='mimo-v2.6-pro')
    assert case.model_dump(mode='json') == {**fields, 'teaching_style': 'direct', 'topic_id': None,
        'model': 'mimo-v2.6-pro', 'freshness': None, 'content_refs': [],
        'image_preview_id': 'preview_synthetic', 'case_revision': 1}


@pytest.mark.parametrize('kind,temporary', [('learning', False), ('learning', True), ('case', False)])
def test_inline_images_cannot_be_silently_dropped_by_legacy_or_case_consumers(tmp_path, kind, temporary):
    services = create_app(tmp_path / 'synthetic-image-denial').state.services
    repo = services.get('conversations')
    chat = repo.create(NewConversation(kind=kind, temporary=temporary))
    request = Send(expected_revision=chat['revision'], text='Explain synthetic image.',
        request_id='unsupported-image-owner', images=(IMAGE,))
    try:
        with pytest.raises(ApiError) as rejected:
            repo.streaming.begin(kind, chat['identity']['id'], request)
        assert rejected.value.code == 'learning_images_unavailable'
        assert repo.streaming.active == {}
        assert repo.draft(kind, chat['identity']['id'])['text'] == ''
    finally:
        services.get('helpers').startup.close()


async def test_saved_native_learning_forwards_exact_inline_images_and_binds_replay(tmp_path):
    from test_harness_bridge import ScriptedTransport, collect, native_at

    class ImageTransport(ScriptedTransport):
        async def request(self, command, payload, *args):
            if command == 'session.prompt':
                self.images = payload.get('images')
            return await super().request(command, payload, *args)

    transport = ImageTransport()
    services, repo, _, _, identifier, text = native_at(tmp_path, transport)
    request = Send(**text.model_dump(mode='json'), images=(IMAGE,))
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
        assert transport.images == [IMAGE]
        replay_entry, replay_receipt = repo.streaming.begin('learning', identifier, request)
        assert (await collect(repo.streaming, replay_entry, replay_receipt))[-1]['payload']['replayed']
        changed = Send(**text.model_dump(mode='json'), images=({**IMAGE, 'data': 'eA=='},))
        with pytest.raises(ApiError) as rejected:
            repo.streaming.begin('learning', identifier, changed)
        assert rejected.value.code == 'idempotency_conflict'
        assert len(transport.prompts) == 1
    finally:
        services.get('helpers').startup.close()


@pytest.mark.parametrize('capabilities,revoke', [(('text', 'tools'), False),
    (('text', 'tools', 'image'), True)])
def test_saved_image_admission_denies_missing_or_revoked_capability_atomically(tmp_path, capabilities, revoke):
    from test_harness_bridge import ScriptedTransport, active_shape
    from renulus.learn.harness_bridge import HarnessLearningBridge
    from renulus.runtime.harness_configuration import (ConfigurationAuthority, ConfigurationSpec,
        ConnectionReference, CandidateHealth, RestartBoundary)
    from renulus.runtime.harness_learning import HarnessLearningOwner
    from renulus.runtime.harness_process import HarnessProcessConfig

    root = tmp_path / 'synthetic-current-image'
    services = create_app(root).state.services
    authority = ConfigurationAuthority(services.db)
    spec = ConfigurationSpec(connection=ConnectionReference(provider='opencode-go',
        credential_reference='synthetic-image-connection', credential_revision=1,
        selected_model='mimo-v2.6-pro'), registry_hash='a' * 64, capabilities=capabilities)
    version = authority.stage(spec)
    assert authority.validate(version, lambda candidate: CandidateHealth(
        configuration_version=candidate.version, grant_epoch=candidate.grant_epoch,
        registry_hash=spec.registry_hash))
    authority.activate(version, RestartBoundary(admission_closed=True, runtime_stopped=True,
        domain_settled=True), expected_effective=None)  # Synthetic trusted boundary, no native process.
    authority.open_admission(version, registry_hash=spec.registry_hash, grant_epoch=0)
    if revoke:
        authority.revoke('image')
    config = HarnessProcessConfig(node_executable=root / 'unused.exe', host_entry=root / 'unused.mjs',
        profile_root=root, profile_id='synthetic-profile', store_id='synthetic-runtime',
        domain_store_id='synthetic-domain', domain_path='state/renulus.sqlite3')
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    repo = services.get('conversations')
    services.registry['learning_harness'] = HarnessLearningBridge(repo, ScriptedTransport(),
        active_manifest=active_shape, configuration_id=version, admit_run_in=owner.admit_run_in)
    chat = repo.create(NewConversation())
    identifier = chat['identity']['id']
    before = repo.draft('learning', identifier)
    try:
        with pytest.raises(ApiError) as rejected:
            repo.streaming.begin('learning', identifier, Send(expected_revision=chat['revision'],
                text='Explain synthetic image.', request_id='capability-image-admission', images=(IMAGE,)))
        assert rejected.value.code == 'capability_revoked'
        assert authority.activation_snapshot()['pinned_runs'] == []
        assert repo.streaming.active == {} and repo.learn.active == {}
        assert repo.draft('learning', identifier) == before
        assert repo.learn.get_thread(identifier)['messages'] == []
    finally:
        services.get('helpers').startup.close()


async def test_pending_image_references_exclude_bytes_and_recover_only_matching_native_files(tmp_path):
    from test_harness_bridge import collect, native_at
    from test_harness_reconciliation import LostAcknowledgement
    from renulus.storage.backup import export_records

    class ImageAcknowledgement(LostAcknowledgement):
        async def request(self, command, payload, *args):
            if command == 'session.prompt':
                self.files = [{'data': image['data'], 'mime': image['media_type'],
                    'source': {'type': 'inline'}} for image in payload['images']]
            result = await super().request(command, payload, *args)
            if command == 'session.messages':
                result['result']['messages'][0]['files'] = self.files
            return result

    services, repo, bridge, transport, identifier, text = native_at(tmp_path, ImageAcknowledgement())
    request = Send(**text.model_dump(mode='json'), images=(IMAGE,))
    try:
        entry, receipt = repo.streaming.begin('learning', identifier, request)
        assert (await collect(repo.streaming, entry, receipt))[-1]['payload']['code'] == 'harness_command_uncertain'
        assert PNG not in json.dumps(export_records(services))
        retained = transport.files
        transport.files = [{**retained[0], 'data': 'eA=='}]
        with pytest.raises(ApiError) as rejected:
            await bridge.messages(identifier)
        assert rejected.value.code == 'harness_input_conflict'
        assert bridge.completed(receipt['run_id']) is None
        transport.files = retained
        assert len((await bridge.messages(identifier))['items']) == 2
        assert bridge.completed(receipt['run_id']) is not None
        assert transport.prompts == [request.text]
        assert 'session.cancel' not in transport.calls
    finally:
        services.get('helpers').startup.close()
