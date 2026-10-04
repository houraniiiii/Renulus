"""Canonical learner facts, provenance, revisions and a reference-only outbox."""
import json

from renulus.contracts import ApiError, ContextScope, Scope, durable_id
from renulus.storage import utc_now

from .models import ManualFact, clean_text, digest, require_eligible


class MemoryRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db
        self.db.execute(
            "UPDATE memory_jobs SET state='queued',updated_at=? WHERE state='running'",
            (utc_now(),))

    def _fact(self, conn, identifier):
        row = conn.execute(
            "SELECT * FROM memory_facts f WHERE id=? AND NOT EXISTS (SELECT 1 FROM deletion_ledger "
            "WHERE entity_type='memory_fact' AND entity_id=f.id)", (identifier,)).fetchone()
        if not row:
            raise ApiError('memory_missing', 'This learning note has been removed', 404)
        return dict(row)

    def _view(self, row):
        result = dict(row)
        result.pop('text_hash', None)
        entry = self.db.fetch_one(
            'SELECT e.revision,s.state FROM memory_index_entries e CROSS JOIN memory_index_state s '
            'WHERE e.record_id=? AND e.generation=s.generation', (row['id'],))
        state = self.db.fetch_one('SELECT state FROM memory_index_state WHERE singleton=1')
        result['index_state'] = ('ready' if entry and entry['revision'] == row['revision'] and
                                  entry['state'] == 'ready' else
                                  'failed' if state['state'] == 'failed' else 'pending')
        return result

    def get(self, identifier):
        with self.db.transaction() as conn:
            row = self._fact(conn, identifier)
        return self._view(row)

    def list(self):
        rows = self.db.fetch_all(
            "SELECT * FROM memory_facts f WHERE NOT EXISTS (SELECT 1 FROM deletion_ledger "
            "WHERE entity_type='memory_fact' AND entity_id=f.id) ORDER BY updated_at DESC,id")
        return [self._view(row) for row in rows]

    @staticmethod
    def invalidate(conn):
        conn.execute("UPDATE memory_index_state SET epoch=epoch+1,state='dirty',error_code=NULL "
                     'WHERE singleton=1')

    def _insert(self, conn, text, kind, topic, scope, source_kind, source_id, source_key):
        text = clean_text(text)
        text_hash = digest(' '.join(text.casefold().split()))
        existing = conn.execute(
            'SELECT * FROM memory_facts WHERE text_hash=? AND kind=? AND topic_id IS ?',
            (text_hash, kind, topic)).fetchone()
        if existing and not conn.execute(
                "SELECT 1 FROM deletion_ledger WHERE entity_type='memory_fact' AND entity_id=?",
                (existing['id'],)).fetchone():
            identifier = existing['id']
        else:
            identifier, now = durable_id('memory'), utc_now()
            conn.execute('INSERT INTO memory_facts VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                         (identifier, text, text_hash, kind, topic, scope, 1, source_kind,
                          source_id, now, now))
            conn.execute('INSERT INTO memory_history VALUES(?,?,?,?,?)',
                         (identifier, 1, text, 'added', now))
            self.invalidate(conn)
        conn.execute('INSERT OR IGNORE INTO memory_sources VALUES(?,?)', (source_key, identifier))
        return identifier

    def add(self, request: ManualFact):
        require_eligible(request.scope)
        if request.scope.kind != Scope.STUDY:
            raise ApiError('manual_memory_scope', 'Manual learner notes use ordinary study scope', 409)
        text = clean_text(request.text)
        request_hash = digest(request.model_dump(mode='json', exclude={'idempotency_key'}))
        with self.db.transaction() as conn:
            previous = conn.execute('SELECT * FROM memory_requests WHERE idempotency_key=?',
                                    (request.idempotency_key,)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise ApiError('idempotency_conflict', 'This request key already names another note', 409)
                row = self._fact(conn, previous['record_id'])
                return self._view(row)
            identifier = self._insert(conn, text, request.kind, request.topic_id, 'study', 'manual',
                                      None, 'manual:' + request.idempotency_key)
            conn.execute('INSERT INTO memory_requests VALUES(?,?,?)',
                         (request.idempotency_key, request_hash, identifier))
        return self.get(identifier)

    def _suppress(self, conn, identifier):
        sources = conn.execute('SELECT source_key FROM memory_sources WHERE record_id=?',
                               (identifier,)).fetchall()
        now = utc_now()
        for row in sources:
            conn.execute('INSERT OR REPLACE INTO memory_suppression VALUES(?,?)', (row[0], now))
            if row[0].startswith('evidence:'):
                conn.execute("UPDATE memory_jobs SET state='cancelled',updated_at=? "
                             "WHERE evidence_id=? AND state IN ('queued','running','failed')",
                             (now, row[0][len('evidence:'):]))

    def edit(self, identifier, text, expected_revision):
        text, now = clean_text(text), utc_now()
        with self.db.transaction() as conn:
            old = self._fact(conn, identifier)
            if old['revision'] != expected_revision:
                raise ApiError('memory_revision_conflict', 'The note changed. Reload before editing it', 409)
            if old['text'] == text:
                return self._view(old)
            revision = old['revision'] + 1
            # A correction owns this record; the old source cannot regenerate it.
            self._suppress(conn, identifier)
            conn.execute('UPDATE memory_facts SET text=?,text_hash=?,revision=?,updated_at=? WHERE id=?',
                         (text, digest(' '.join(text.casefold().split())), revision, now, identifier))
            conn.execute('INSERT INTO memory_history VALUES(?,?,?,?,?)',
                         (identifier, revision, text, 'edited', now))
            self.invalidate(conn)
        return self.get(identifier)

    def delete(self, identifier, expected_revision):
        with self.db.transaction() as conn:
            marker = conn.execute(
                "SELECT 1 FROM deletion_ledger WHERE entity_type='memory_fact' AND entity_id=?",
                (identifier,)).fetchone()
            if marker:
                return {'deleted': True}
            row = self._fact(conn, identifier)
            if row['revision'] != expected_revision:
                raise ApiError('memory_revision_conflict', 'The note changed. Reload before removing it', 409)
            self._suppress(conn, identifier)
            self.db.mark_deleted('memory_fact', identifier, conn)
            conn.execute('DELETE FROM memory_facts WHERE id=?', (identifier,))
            self.invalidate(conn)
        return {'deleted': True}

    def history(self, identifier):
        self.get(identifier)
        return self.db.fetch_all(
            'SELECT revision,text,event,created_at FROM memory_history WHERE record_id=? ORDER BY revision',
            (identifier,))

    def purge_history(self, identifier):
        with self.db.transaction() as conn:
            self._fact(conn, identifier)
            conn.execute('DELETE FROM memory_history WHERE record_id=?', (identifier,))
            self.invalidate(conn)
        return {'purged': True}

    def material(self, evidence_id, scope: ContextScope):
        require_eligible(scope)
        row = self.db.fetch_one('SELECT * FROM learning_evidence WHERE id=?', (evidence_id,))
        if not row:
            raise ApiError('memory_evidence_missing', 'This learning evidence is no longer available', 404)
        try:
            payload = json.loads(row['payload_json'])
            if not isinstance(payload, dict):
                raise ValueError()
            declared = ContextScope.model_validate(payload['scope']) if 'scope' in payload else None
        except (ValueError, TypeError, KeyError):
            raise ApiError('memory_evidence_invalid', 'Learning evidence needs a classified scope', 409) from None
        if declared is not None:
            require_eligible(declared)
            if declared != scope:
                raise ApiError('memory_evidence_scope', 'Learning evidence must keep its original scope', 409)
        if self.db.is_deleted('learn_thread', row['entity_id']) or self.db.is_deleted(
                'learning_evidence', evidence_id):
            raise ApiError('memory_evidence_deleted', 'This learning evidence has been removed', 409)
        kind, infer = 'study-interest', False
        topic = row['topic_id']
        if row['kind'] == 'study-interest':
            # Learn emits only topic/activity metadata from committed ordinary study.
            if (scope.kind != Scope.STUDY or scope.entity_id != row['entity_id'] or
                    set(payload) - {'topic_id', 'activity', 'scope'} or payload.get('activity') != 'explain'):
                raise ApiError('memory_evidence_invalid', 'Only committed ordinary study is eligible', 409)
            if not topic:
                raise ApiError('memory_evidence_empty', 'This activity has no classified learning topic', 409)
            text = 'I explored ' + topic + ' in Explain.'
        elif row['kind'] == 'assessment-answer':
            if (declared is None or scope.kind != Scope.REVIEWED_ASSESSMENT or payload.get('mode') != 'reviewed' or
                    type(payload.get('correct')) is not bool or
                    payload.get('score_bucket') not in ('fresh', 'assisted', 'repeat')):
                raise ApiError('memory_evidence_invalid', 'Only committed reviewed assessment is eligible', 409)
            objective = payload.get('objective_id') or topic
            if not isinstance(objective, str) or not objective or len(objective) > 200:
                raise ApiError('memory_evidence_empty', 'This assessment has no learning objective', 409)
            kind = 'study-interest' if payload['correct'] else 'mistake'
            text = ('Answered correctly' if payload['correct'] else 'Review needed after an incorrect answer')
            text += ' on ' + objective + ' in reviewed assessment (' + payload['score_bucket'] + ').'
        elif row['kind'] == 'learning-point':
            if (declared is None or payload.get('general_learning') is not True or
                    set(payload) - {'scope', 'general_learning', 'text'}):
                raise ApiError('memory_evidence_invalid', 'Supply a general learning point without case material', 409)
            text, kind, infer = clean_text(payload.get('text')), 'learning-point', True
        else:
            raise ApiError('memory_evidence_ineligible', 'This evidence type is not eligible for learner memory', 409)
        fingerprint = digest({key: row[key] for key in ('id', 'kind', 'topic_id', 'entity_id', 'payload_json')})
        return {'text': text, 'kind': kind, 'topic_id': topic, 'infer': infer,
                'fingerprint': fingerprint, 'scope': scope, 'entity_id': row['entity_id']}

    def enqueue(self, evidence_id, scope: ContextScope):
        require_eligible(scope)
        material = self.material(evidence_id, scope)
        with self.db.transaction() as conn:
            if conn.execute('SELECT 1 FROM memory_suppression WHERE source_key=?',
                            ('evidence:' + evidence_id,)).fetchone():
                raise ApiError('memory_capture_suppressed', 'This source was removed or corrected in memory', 409)
            previous = conn.execute('SELECT * FROM memory_jobs WHERE evidence_id=? AND evidence_hash=?',
                                    (evidence_id, material['fingerprint'])).fetchone()
            if previous:
                return dict(previous)
            identifier, now = durable_id('memoryjob'), utc_now()
            conn.execute('INSERT INTO memory_jobs VALUES(?,?,?,?,?,?,?,?,?)',
                         (identifier, evidence_id, material['fingerprint'], scope.model_dump_json(),
                          'queued', 0, None, now, now))
        return self.job(identifier)

    def job(self, identifier):
        row = self.db.fetch_one('SELECT * FROM memory_jobs WHERE id=?', (identifier,))
        if not row:
            raise ApiError('memory_job_missing', 'This capture job is not available', 404)
        return row

    def jobs(self):
        return self.db.fetch_all('SELECT * FROM memory_jobs ORDER BY created_at DESC LIMIT 100')

    def scan(self):
        # Immutable producer records are the queue input, never a raw transcript.
        rows = self.db.fetch_all(
            "SELECT e.* FROM learning_evidence e WHERE e.kind IN ('study-interest','assessment-answer','learning-point') "
            'AND NOT EXISTS (SELECT 1 FROM memory_jobs j WHERE j.evidence_id=e.id) '
            "AND NOT EXISTS (SELECT 1 FROM memory_suppression s WHERE s.source_key='evidence:' || e.id) "
            'ORDER BY e.created_at LIMIT 100')
        for row in rows:
            try:
                payload = json.loads(row['payload_json'])
                scope = (ContextScope.model_validate(payload['scope']) if 'scope' in payload else
                         ContextScope(kind=Scope.STUDY, entity_id=row['entity_id']))
                self.enqueue(row['id'], scope)
            except (ApiError, ValueError, TypeError, KeyError):
                # Ineligible input produces no job, audit or error payload.
                continue

    def claim(self, identifier):
        with self.db.transaction() as conn:
            row = conn.execute('SELECT * FROM memory_jobs WHERE id=?', (identifier,)).fetchone()
            if not row or row['state'] != 'queued':
                return None
            conn.execute("UPDATE memory_jobs SET state='running',attempts=attempts+1,updated_at=?,error_code=NULL WHERE id=?",
                         (utc_now(), identifier))
        return self.job(identifier)

    def current(self, job):
        row = self.job(job['id'])
        if row['state'] != 'running' or self.db.fetch_one(
                'SELECT 1 FROM memory_suppression WHERE source_key=?', ('evidence:' + job['evidence_id'],)):
            return False
        try:
            return self.material(job['evidence_id'], ContextScope.model_validate_json(job['scope']))[
                'fingerprint'] == job['evidence_hash']
        except ApiError:
            return False

    def commit_capture(self, job, material, texts):
        with self.db.transaction() as conn:
            # Re-evaluate producer revision/scope and cancellation inside the commit transaction.
            if not self.current(job):
                conn.execute("UPDATE memory_jobs SET state='cancelled',updated_at=? WHERE id=? AND state='running'",
                             (utc_now(), job['id']))
                return []
            identifiers = []
            for text in texts:
                identifiers.append(self._insert(conn, text, material['kind'], material['topic_id'],
                    material['scope'].kind.value, 'learning-evidence', job['evidence_id'],
                    'evidence:' + job['evidence_id']))
            conn.execute("UPDATE memory_jobs SET state='completed',updated_at=? WHERE id=?",
                         (utc_now(), job['id']))
        return identifiers

    def cancel(self, identifier):
        self.db.execute("UPDATE memory_jobs SET state='cancelled',updated_at=? "
                        "WHERE id=? AND state IN ('queued','running','failed')", (utc_now(), identifier))
        return self.job(identifier)

    def fail(self, identifier, code):
        self.db.execute("UPDATE memory_jobs SET state='failed',error_code=?,updated_at=? "
                        "WHERE id=? AND state='running'", (code, utc_now(), identifier))

    def retry(self):
        return self.db.execute("UPDATE memory_jobs SET state='queued',error_code=NULL,updated_at=? "
                               "WHERE state='failed'", (utc_now(),))
