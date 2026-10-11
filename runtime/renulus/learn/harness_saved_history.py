# SPDX-License-Identifier: MIT
"""Canonical saved-history snapshots; native transfer runs after this transaction."""
from pathlib import Path

from renulus.contracts import ApiError
from renulus.design_c_contracts import Conversation, canonical_digest
from renulus.harness_contracts import PairedStoreManifest
from renulus.storage.assessment_policy import require_assistance
from renulus.storage.invalidation import context_epoch_in
from .harness_migration import (MAX_MESSAGES, LegacyMessage, MigrationPins, SavedHistory)


class HarnessSavedHistory:
    def __init__(self, repository, *, active_manifest):
        self.repo, self.db = repository, repository.db
        self.active_manifest = active_manifest

    def snapshot_in(self, conn, thread_id, *, expected_revision):
        path = next((row[2] for row in conn.execute('PRAGMA database_list') if row[1] == 'main'), None)
        if not conn.in_transaction or not path or Path(path).resolve() != self.db.path:
            raise ApiError('harness_migration_transaction_required',
                'Read the saved owner in its canonical transaction.', 409)
        policy = require_assistance(conn)
        summary, metadata = self.repo._get(conn, 'learning', thread_id)
        if summary['retention'] != 'saved' or summary['lifecycle'] == 'deleted':
            raise ApiError('harness_migration_owner', 'Migration requires a retained saved learning owner.', 409)
        self.repo._expected(summary, expected_revision)
        if any(run.thread_id == thread_id for run in self.repo.learn.active.values()):
            raise ApiError('conversation_busy', 'Settle the saved response before migrating its history.', 409, True)
        runs = {row['id']: dict(row) for row in conn.execute(
            'SELECT * FROM learn_runs WHERE thread_id=?', (thread_id,))}
        if any(run['state'] not in {'completed', 'cancelled', 'failed', 'interrupted'} for run in runs.values()):
            raise ApiError('conversation_busy', 'Settle the saved response before migrating its history.', 409, True)
        rows = tuple(conn.execute('SELECT * FROM learn_messages WHERE thread_id=? ORDER BY created_at,id LIMIT ?',
            (thread_id, MAX_MESSAGES + 1)))
        if len(rows) > MAX_MESSAGES:
            raise ApiError('harness_migration_budget', 'Saved history exceeds the native message transfer bound.', 409)
        messages = []
        for row in rows:
            run = runs.get(row['run_id'])
            if run is None:
                raise ApiError('harness_migration_source', 'A retained message has no settled legacy run.', 409)
            assistant = row['role'] == 'assistant'
            messages.append(LegacyMessage(row['id'], row['run_id'], row['role'], row['content'],
                row['created_at'], run['updated_at'] if assistant else None,
                row['citations_json'], run['state'] if assistant else None))
        project_id = summary['project_id']
        project_revision = None
        if project_id is not None:
            project = conn.execute('SELECT revision FROM study_projects WHERE id=? AND lifecycle!=?',
                (project_id, 'deleted')).fetchone()
            if project is None:
                raise ApiError('project_missing', 'This project is no longer available.', 404)
            project_revision = project['revision']
        frontier = canonical_digest([list(row) for row in conn.execute(
            'SELECT entity_type,entity_id,deleted_at FROM deletion_ledger ORDER BY entity_type,entity_id')])
        pins = MigrationPins(summary['revision'], metadata['draft_revision'], project_id,
            project_revision, policy, context_epoch_in(conn), frontier)
        manifest = PairedStoreManifest.model_validate(self.active_manifest())
        if manifest.state != 'active':
            raise ApiError('harness_not_active', 'Activate validated paired stores first.', 409, True)
        return SavedHistory(Conversation.model_validate(summary), manifest, pins, tuple(messages))

    def check_current_in(self, conn, snapshot):
        current = self.snapshot_in(conn, snapshot.conversation.identity.id,
            expected_revision=snapshot.conversation.revision)
        if current != snapshot:
            raise ApiError('harness_migration_conflict', 'The frozen saved history or authority changed.', 409, True)
