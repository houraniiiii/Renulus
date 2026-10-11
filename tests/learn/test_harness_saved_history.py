# SPDX-License-Identifier: MIT
"""Canonical migration snapshots over genuine legacy conversation publication."""
import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import ConversationDraft
from renulus.learn.conversation_models import NewConversation, Send
from renulus.server import create_app
from test_harness_bridge import LegacyProvider, active_shape, collect


async def test_canonical_history_snapshot_pins_exact_public_legacy_rows_and_current_draft(tmp_path):
    from renulus.learn.harness_saved_history import HarnessSavedHistory

    services = create_app(tmp_path / 'legacy-source').state.services
    services.registry['provider'] = LegacyProvider()
    repo = services.get('conversations')
    chat = repo.create(NewConversation(title='Synthetic transplant discussion'))
    identifier = chat['identity']['id']
    entry, receipt = repo.streaming.begin('learning', identifier, Send(
        expected_revision=chat['revision'], text='Explain transplant rejection.', request_id='legacy-source-turn'))
    assert (await collect(repo.streaming, entry, receipt))[-1]['type'] == 'completed'
    public = repo.learn.get_thread(identifier)
    revision = repo.get('learning', identifier)['revision']
    draft = repo.draft('learning', identifier)
    source = HarnessSavedHistory(repo, active_manifest=active_shape)
    with services.db.transaction() as conn:
        snapshot = source.snapshot_in(conn, identifier, expected_revision=revision)
        assert [(m.message_id, m.run_id, m.role, m.text, m.created_at) for m in snapshot.messages] == [
            (m['id'], m['run_id'], m['role'], m['content'], m['created_at']) for m in public['messages']]
        assert snapshot.messages[-1].run_outcome == 'completed'
        assert snapshot.messages[-1].completed_at == public['runs'][0]['updated_at']
        assert snapshot.pins.owner_revision == revision
        assert snapshot.pins.draft_revision == draft['revision']
        source.check_current_in(conn, snapshot)
    repo.save_draft('learning', identifier, ConversationDraft(text='Changed next question',
        content_refs=[], expected_revision=revision), 'changed-source-draft')
    with services.db.transaction() as conn:
        with pytest.raises(ApiError) as stale:
            source.check_current_in(conn, snapshot)
        assert stale.value.code == 'conversation_revision_conflict'
