# SPDX-License-Identifier: MIT
"""Canonical migration references and durable owner-independent purge obligations."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3

from renulus.contracts import ApiError, durable_id
from renulus.harness_contracts import PairedStoreManifest, SavedConversationMapping
from .harness_migration import MessageReference, MigrationPins, MigrationRecord


def _deny(code, status=409):
    raise ApiError(code, 'The saved migration metadata is unavailable or changed.', status)


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class NativePurge:
    purge_id: str
    profile_id: str
    store_id: str
    session_id: str
    operation_id: str
    attempt_id: str
    state: str = 'pending'


class HarnessMigrationJournal:
    def __init__(self, database):
        self.db = database
        migration = Path(__file__).with_name('migrations') / '004-harness-migration.sql'
        self.db.apply_migration('learn-004-harness-migration', migration.read_text(encoding='utf-8'))

    def _transaction(self, conn):
        try:
            active = conn.in_transaction
            path = next((row[2] for row in conn.execute('PRAGMA database_list') if row[1] == 'main'), None)
        except (sqlite3.Error, AttributeError):
            _deny('harness_migration_transaction_required')
        if not active:
            _deny('harness_migration_transaction_required')
        if not path or Path(path).resolve() != self.db.path:
            _deny('harness_migration_connection_mismatch')

    @staticmethod
    def _manifest(record):
        if type(record) is not MigrationRecord:
            _deny('harness_migration_record_invalid', 422)
        try:
            manifest = PairedStoreManifest.model_validate_json(record.manifest_json)
        except ValueError:
            _deny('harness_migration_record_invalid', 422)
        if manifest.state != 'active':
            _deny('harness_migration_record_invalid', 422)
        if (type(record.source_revision) is not int or record.source_revision <= 0
                or record.pins.owner_revision != record.source_revision
                or not isinstance(record.source_digest, str) or len(record.source_digest) != 64
                or any(char not in '0123456789abcdef' for char in record.source_digest)
                or len(record.message_refs) > 4096
                or any(type(item) is not MessageReference or item.ordinal != index
                    or item.lineage != 'unknown' or item.context_eligible is not False
                    or item.capture_eligible is not False for index, item in enumerate(record.message_refs))
                or len({item.native_id for item in record.message_refs}) != len(record.message_refs)
                or len({item.legacy_id for item in record.message_refs}) != len(record.message_refs)):
            _deny('harness_migration_record_invalid', 422)
        return manifest

    def _decode(self, row):
        if row is None:
            return None
        try:
            record = MigrationRecord(row['migration_id'], row['thread_id'], row['source_revision'],
                row['manifest_json'], MigrationPins(**json.loads(row['pins_json'])), row['session_id'],
                row['source_digest'], tuple(MessageReference(**item) for item in json.loads(row['message_refs_json'])),
                row['state'], row['readback_digest'])
            manifest = self._manifest(record)
        except (ValueError, TypeError, KeyError):
            _deny('harness_migration_journal_corrupt', 503)
        if (row['profile_id'], row['store_id']) != (manifest.profile_id, manifest.runtime_store.store_id):
            _deny('harness_migration_journal_corrupt', 503)
        return record

    def find_in(self, conn, *, thread_id=None, migration_id=None):
        self._transaction(conn)
        if (thread_id is None) == (migration_id is None):
            _deny('harness_migration_lookup_invalid', 422)
        column, value = ('thread_id', thread_id) if thread_id is not None else ('migration_id', migration_id)
        return self._decode(conn.execute(f'SELECT * FROM learn_harness_migrations WHERE {column}=?',
            (value,)).fetchone())

    def mapping_in(self, conn, thread_id):
        self._transaction(conn)
        row = conn.execute('SELECT mapping_json FROM learn_harness_mappings WHERE thread_id=?',
            (thread_id,)).fetchone()
        return SavedConversationMapping.model_validate_json(row['mapping_json']) if row and row['mapping_json'] else None

    def reserve_in(self, conn, record):
        self._transaction(conn)
        manifest = self._manifest(record)
        if record.state != 'reserved' or record.readback_digest is not None:
            _deny('harness_migration_record_invalid', 422)
        existing = self.find_in(conn, thread_id=record.thread_id)
        if existing is not None:
            if existing != record:
                _deny('harness_migration_conflict')
            return
        row = conn.execute('SELECT * FROM learn_harness_mappings WHERE thread_id=?', (record.thread_id,)).fetchone()
        if row is not None:
            _deny('harness_migration_owner_conflict')
        conn.execute('SAVEPOINT harness_migration_reserve')
        try:
            conn.execute('INSERT INTO learn_harness_migrations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (record.migration_id, record.thread_id, record.source_revision, manifest.profile_id,
                 manifest.runtime_store.store_id, record.session_id, record.source_digest, record.state,
                 record.manifest_json, _json(asdict(record.pins)),
                 _json([asdict(item) for item in record.message_refs]), None))
            conn.execute('INSERT INTO learn_harness_mappings(thread_id,profile_id,store_id,session_id,create_request_id) '
                'VALUES(?,?,?,?,?)', (record.thread_id, manifest.profile_id, manifest.runtime_store.store_id,
                 record.session_id, record.migration_id))
        except BaseException as error:
            conn.execute('ROLLBACK TO harness_migration_reserve')
            conn.execute('RELEASE harness_migration_reserve')
            if isinstance(error, sqlite3.IntegrityError):
                _deny('harness_migration_conflict')
            raise
        conn.execute('RELEASE harness_migration_reserve')

    def start_in(self, conn, record):
        self._transaction(conn)
        current = self.find_in(conn, migration_id=record.migration_id)
        if current != record or current.state != 'reserved':
            return False
        return conn.execute(
            "UPDATE learn_harness_migrations SET state='transferring' WHERE migration_id=? AND state='reserved'",
            (record.migration_id,)).rowcount == 1

    def activate_in(self, conn, record, *, mapping, readback_digest):
        self._transaction(conn)
        current = self.find_in(conn, migration_id=record.migration_id)
        manifest = self._manifest(record)
        if type(mapping) is not SavedConversationMapping:
            _deny('harness_migration_conflict')
        try:
            mapping = SavedConversationMapping.model_validate_json(mapping.model_dump_json())
        except ValueError:
            _deny('harness_migration_conflict')
        if (current != record or record.state not in {'reserved', 'transferring'}
                or readback_digest != record.source_digest
                or mapping.conversation.id != record.thread_id
                or mapping.conversation.type != 'learn_thread'
                or mapping.runtime.engine != manifest.runtime_store.engine
                or (mapping.runtime.profile_id, mapping.runtime.store_id, mapping.runtime.session_id) !=
                   (manifest.profile_id, manifest.runtime_store.store_id, record.session_id)):
            _deny('harness_migration_conflict')
        row = conn.execute('SELECT * FROM learn_harness_mappings WHERE thread_id=?', (record.thread_id,)).fetchone()
        if (row is None or row['mapping_json'] is not None
                or (row['profile_id'], row['store_id'], row['session_id'], row['create_request_id']) !=
                   (manifest.profile_id, manifest.runtime_store.store_id, record.session_id, record.migration_id)):
            _deny('harness_migration_owner_conflict')
        conn.execute('UPDATE learn_harness_mappings SET mapping_json=? WHERE thread_id=?',
            (mapping.model_dump_json(), record.thread_id))
        conn.execute("UPDATE learn_harness_migrations SET state='active',readback_digest=? WHERE migration_id=?",
            (readback_digest, record.migration_id))

    def capture_owner_in(self, conn, thread_id):
        """Persist every originating operation before its owner FKs cascade."""
        self._transaction(conn)
        row = conn.execute('SELECT profile_id,store_id,session_id FROM learn_harness_mappings WHERE thread_id=?',
            (thread_id,)).fetchone()
        if row is None:
            return
        if row['session_id'] is None:
            raise ApiError('harness_purge_identity_unavailable',
                'Reconcile the pending native session before deleting this saved owner.', 409, True)
        operations = {item['run_id'] for item in conn.execute(
            'SELECT run_id FROM learn_harness_answers WHERE thread_id=?', (thread_id,))}
        operations.update(item['migration_id'] for item in conn.execute(
            'SELECT migration_id FROM learn_harness_migrations WHERE thread_id=?', (thread_id,)))
        if not operations:
            _deny('harness_purge_identity_unavailable')
        for operation in sorted(operations):
            conn.execute('INSERT OR IGNORE INTO learn_harness_purges VALUES(?,?,?,?,?,?,?)',
                (durable_id('purge'), row['profile_id'], row['store_id'], row['session_id'], operation, '1', 'pending'))

    def pending_purges(self):
        with self.db.transaction() as conn:
            return tuple(NativePurge(**dict(row)) for row in conn.execute(
                "SELECT * FROM learn_harness_purges WHERE state='pending' ORDER BY purge_id"))

    def removed_purges(self):
        """Opaque originating identities that must stay retired on a new generation."""
        with self.db.transaction() as conn:
            return tuple(NativePurge(**dict(row)) for row in conn.execute(
                "SELECT * FROM learn_harness_purges WHERE state='removed' ORDER BY purge_id"))

    def mark_removed_in(self, conn, purge):
        self._transaction(conn)
        current = conn.execute('SELECT * FROM learn_harness_purges WHERE purge_id=?', (purge.purge_id,)).fetchone()
        if current is None or NativePurge(**dict(current)) != purge:
            _deny('harness_purge_identity_changed')
        conn.execute("UPDATE learn_harness_purges SET state='removed' WHERE purge_id=?", (purge.purge_id,))
