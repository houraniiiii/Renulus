"""Canonical learner facts, provenance, revisions and a reference-only outbox."""
import json
import hashlib

from renulus.contracts import ApiError, ContextScope, Scope, durable_id
from renulus.design_c_contracts import Identity
from renulus.storage import utc_now
from renulus.storage.assessment_policy import policy_snapshot, require_assistance
from renulus.storage.invalidation import MEMORY_RESTORE_CAPTURE_PREFIX, context_epoch_in

from .models import ManualFact, clean_text, digest, require_eligible
from .study_answers import answer_text, answer_reference_in
from .lineage import AnswerInputs, AnswerLineage, INELIGIBLE_LINEAGE_CODES
from .capture import _local_result


BOUNDARY_CANCELLATIONS = ('boundary_policy_changed', 'boundary_context_changed', 'restore_interrupted')
CAPTURE_REFUSAL_CODES = INELIGIBLE_LINEAGE_CODES | frozenset({
    'assistance_restricted', 'assistance_changed', 'memory_evidence_ineligible',
    'memory_evidence_invalid', 'memory_evidence_scope', 'memory_evidence_empty',
    'memory_evidence_missing', 'invalid_memory_text',
})


def capture_fingerprint(conn, source_revision):
    # Keep source authority separate from disposable local generations so an
    # interrupted boundary never hides a changed source. Only hashes/scalars
    # are retained in the existing outbox column, never producer text.
    return ('memory/2:' + source_revision + ':' + str(require_assistance(conn)) +
            ':' + str(context_epoch_in(conn)))


def fingerprint_parts(value):
    parts = value.split(':') if isinstance(value, str) else []
    if (len(parts) != 4 or parts[0] != 'memory/2' or len(parts[1]) != 64 or
            any(char not in '0123456789abcdef' for char in parts[1]) or
            not 1 <= len(parts[2]) <= 20 or not 1 <= len(parts[3]) <= 20 or
            not parts[2].isdigit() or not parts[3].isdigit()):
        return None
    return parts[1], int(parts[2]), int(parts[3])


class MemoryRepository:
    def __init__(self, services):
        self.services, self.db = services, services.db
        # Bind trusted local dependency adapters before opening restored memory.
        self.lineage = AnswerLineage(self.db, services.registry.setdefault('memory_dependency_resolvers', {}))
        self.db.execute(
            "UPDATE memory_jobs SET state='queued',updated_at=? WHERE state='running'",
            (utc_now(),))
        self.reconcile_deletions()

    def reconcile_deletions(self):
        # A restore may bring older canonical rows alongside newer markers.
        # Remove them and suppress their producer sources before rebuilding.
        with self.db.transaction() as conn:
            rows = conn.execute(
                "SELECT f.id FROM memory_facts f JOIN deletion_ledger d ON d.entity_id=f.id "
                "WHERE d.entity_type='memory_fact'").fetchall()
            for row in rows:
                self._suppress(conn, row['id'])
                conn.execute('DELETE FROM memory_facts WHERE id=?', (row['id'],))
            revoked = self.lineage.revoke_in(conn, self._suppress)
            if rows or revoked:
                self.invalidate(conn)

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
        ownership = self.db.fetch_one('SELECT project_id FROM memory_support_groups WHERE record_id=? LIMIT 1', (row['id'],))
        result['project_id'] = ownership['project_id'] if ownership else None
        result['visibility'] = 'project' if result['project_id'] else 'profile-global'
        entry = self.db.fetch_one(
            'SELECT e.revision,s.state FROM memory_index_entries e CROSS JOIN memory_index_state s '
            'WHERE e.record_id=? AND e.generation=s.generation', (row['id'],))
        state = self.db.fetch_one('SELECT state FROM memory_index_state WHERE singleton=1')
        result['index_state'] = ('ready' if entry and entry['revision'] == row['revision'] and
                                  entry['state'] == 'ready' else
                                  'failed' if state['state'] == 'failed' else 'pending')
        result['sources'] = self.db.fetch_all(
            'SELECT source_key FROM memory_sources WHERE record_id=? ORDER BY source_key', (row['id'],))
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

    def _insert(self, conn, text, kind, topic, scope, source_kind, source_id, source_key, *, project_id=None):
        text = clean_text(text)
        text_hash = digest(' '.join(text.casefold().split()))
        existing = conn.execute(
            'SELECT * FROM memory_facts f WHERE text_hash=? AND kind=? AND topic_id IS ? '
            "AND COALESCE((SELECT project_id FROM memory_support_groups g WHERE g.record_id=f.id LIMIT 1),'')=?",
            (text_hash, kind, topic, project_id or '')).fetchone()
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

    def add(self, request: ManualFact, *, project_id=None):
        require_eligible(request.scope)
        if request.scope.kind != Scope.STUDY:
            raise ApiError('manual_memory_scope', 'Manual learner notes use ordinary study scope', 409)
        text = clean_text(request.text)
        if project_id is not None:
            Identity(type='project', id=project_id)
        request_data = request.model_dump(mode='json', exclude={'idempotency_key'})
        request_hash = digest(request_data if project_id is None else {'request': request_data, 'project_id': project_id})
        with self.db.transaction() as conn:
            previous = conn.execute('SELECT * FROM memory_requests WHERE idempotency_key=?',
                                    (request.idempotency_key,)).fetchone()
            if previous:
                if previous['request_hash'] != request_hash:
                    raise ApiError('idempotency_conflict', 'This request key already names another note', 409)
                row = self._fact(conn, previous['record_id'])
                return self._view(row)
            identifier = self._insert(conn, text, request.kind, request.topic_id, 'study', 'manual',
                                      None, 'manual:' + request.idempotency_key, project_id=project_id)
            self.lineage.add_support_in(conn, identifier, 'manual:' + request.idempotency_key, project_id=project_id)
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
                conn.execute("UPDATE memory_jobs SET state='cancelled',error_code='memory_capture_suppressed',updated_at=? "
                             "WHERE evidence_id=? AND state IN ('queued','running','failed','cancelled')",
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
            ownership = conn.execute('SELECT project_id FROM memory_support_groups WHERE record_id=? LIMIT 1', (identifier,)).fetchone()
            project_id = ownership[0] if ownership else None
            # A correction owns this record; the old source cannot regenerate it.
            self._suppress(conn, identifier)
            conn.execute("UPDATE memory_support_groups SET state='revoked' WHERE record_id=?", (identifier,))
            conn.execute('UPDATE memory_facts SET text=?,text_hash=?,revision=?,updated_at=? WHERE id=?',
                         (text, digest(' '.join(text.casefold().split())), revision, now, identifier))
            conn.execute('INSERT INTO memory_history VALUES(?,?,?,?,?)',
                         (identifier, revision, text, 'edited', now))
            self.lineage.add_support_in(conn, identifier, f'edited:{identifier}:{revision}', project_id=project_id)
            self.lineage.revoke_in(conn, self._suppress)
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
            self.lineage.revoke_in(conn, self._suppress)
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

    @staticmethod
    def _whole_scope(metadata):
        return ContextScope(kind=Scope.REVIEWED_ASSESSMENT if metadata['payload']['bank_cohort_eligible']
                            else Scope.GENERATED_PRACTICE, entity_id=metadata['entity_id'])

    def _whole_material_in(self, conn, evidence_id, scope):
        resolver = self.services.registry.get('whole_attempts')
        if resolver is None:
            raise ApiError('memory_evidence_ineligible', 'Whole-attempt evidence is not available', 409)
        metadata = resolver.committed_evidence_in(conn, evidence_id)
        if metadata is None:
            raise ApiError('memory_evidence_invalid', 'This answer has no current eligible commitment', 409)
        expected = self._whole_scope(metadata)
        if scope != expected:
            raise ApiError('memory_evidence_scope', 'Answer memory must retain its original practice cohort', 409)
        if conn.execute('SELECT 1 FROM memory_suppression WHERE source_key=?', ('evidence:' + evidence_id,)).fetchone():
            raise ApiError('memory_capture_suppressed', 'This source was removed or corrected in memory', 409)
        payload = metadata['payload']
        topic = metadata['topic_id']
        if not isinstance(topic, str) or not topic or len(topic) > 200:
            raise ApiError('memory_evidence_empty', 'This answer has no bounded learning topic', 409)
        eligible = payload['bank_cohort_eligible']
        if eligible:
            text = ('Answered correctly' if payload['correct'] else 'Review needed after an incorrect answer')
            text += ' on ' + topic + ' in reviewed practice.'
            kind = 'study-interest' if payload['correct'] else 'mistake'
        else:
            text = 'Personal unreviewed practice on ' + topic + ': '
            text += 'matched the saved key.' if payload['correct'] else 'did not match the saved key.'
            kind = 'study-interest'
        text += (' Mode: ' + payload['mode'] + '; origin: ' + payload['origin'] +
                 '; review quality: ' + payload['review_quality'] + '; cohort: ' + payload['score_bucket'] +
                 '; assisted: ' + ('yes' if payload['assisted'] else 'no') +
                 '; repeat: ' + ('yes' if payload['repeat'] else 'no') + '.')
        return {'text': text, 'kind': kind, 'topic_id': topic, 'infer': False,
                'fingerprint': capture_fingerprint(conn, metadata['revision']),
                'scope': expected, 'entity_id': metadata['entity_id'],
                'assessment': {field: payload[field] for field in ('mode', 'origin', 'review_quality', 'reviewed',
                    'bank_cohort_eligible', 'assisted', 'repeat', 'score_bucket', 'outcome', 'correct')}}

    def material(self, evidence_id, scope: ContextScope, *, conn=None, resolve_answer=True):
        require_eligible(scope)
        if conn is None:
            with self.db.transaction() as current:
                material = self.material(evidence_id, scope, conn=current, resolve_answer=False)
            if resolve_answer and material.get('_answer'):
                evidence, payload = material['_answer']
                material['text'] = answer_text(self.db, evidence, payload, scope)
            return material
        require_assistance(conn)
        select = lambda sql, args: conn.execute(sql, args).fetchone()
        if select('SELECT 1 FROM memory_suppression WHERE source_key=?', ('evidence:' + evidence_id,)):
            raise ApiError('memory_capture_suppressed', 'This source was removed or corrected in memory', 409)
        metadata = select(
            'SELECT kind,json_valid(payload_json) AS payload_valid, CASE WHEN json_valid(payload_json) THEN '
            "json_extract(payload_json,'$.scope.kind') END AS scope_kind, "
            "CASE WHEN json_valid(payload_json) THEN json_type(payload_json,'$.scope') END AS scope_type "
            'FROM learning_evidence WHERE id=?', (evidence_id,))
        if not metadata:
            raise ApiError('memory_evidence_missing', 'This learning evidence is no longer available', 404)
        if metadata['kind'] == 'assessment-test-answer':
            return self._whole_material_in(conn, evidence_id, scope)
        if metadata['kind'] not in ('study-interest', 'assessment-answer', 'learning-point', 'study-answer'):
            raise ApiError('memory_evidence_ineligible', 'This evidence type is not eligible for learner memory', 409)
        if metadata['kind'] == 'study-answer' and (scope.kind != Scope.STUDY or metadata['scope_kind'] != 'study'):
            raise ApiError('memory_scope_excluded', 'Answer capture requires ordinary Study scope', 409)
        if (not metadata['payload_valid'] or (metadata['scope_kind'] is None and
                (metadata['kind'] != 'study-interest' or metadata['scope_type'] is not None))):
            raise ApiError('memory_evidence_invalid', 'Learning evidence needs a classified scope', 409)
        if metadata['scope_kind'] is not None:
            try:
                require_eligible(ContextScope(kind=metadata['scope_kind']))
            except ValueError:
                raise ApiError('memory_evidence_invalid', 'Learning evidence needs a classified scope', 409) from None
        # Inspect classification metadata before fetching any producer text. A
        # caller cannot relabel a stored case reference by supplying study scope.
        row = select('SELECT * FROM learning_evidence WHERE id=?', (evidence_id,))
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
        if select("SELECT 1 FROM deletion_ledger WHERE (entity_type='learn_thread' AND entity_id=?) "
                  "OR (entity_type='learning_evidence' AND entity_id=?)", (row['entity_id'], evidence_id)):
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
        elif row['kind'] == 'study-answer':
            if declared is None:
                raise ApiError('memory_evidence_invalid', 'Study answers need their original classified scope', 409)
            answer_reference_in(conn, row, payload, scope)
            self.lineage.check_in(conn, evidence_id)
            text, kind, infer = '', 'learning-point', True
        elif row['kind'] == 'learning-point':
            if (declared is None or payload.get('general_learning') is not True or
                    set(payload) - {'scope', 'general_learning', 'text'}):
                raise ApiError('memory_evidence_invalid', 'Supply a general learning point without case material', 409)
            text, kind, infer = clean_text(payload.get('text')), 'learning-point', True
        else:
            raise ApiError('memory_evidence_ineligible', 'This evidence type is not eligible for learner memory', 409)
        source_revision = digest({key: row[key] for key in ('id', 'kind', 'topic_id', 'entity_id', 'payload_json')})
        material = {'text': text, 'kind': kind, 'topic_id': topic, 'infer': infer,
                'fingerprint': capture_fingerprint(conn, source_revision), 'scope': scope, 'entity_id': row['entity_id']}
        if row['kind'] == 'study-answer':
            material['_answer'] = (dict(row), payload)
            material['lineage'] = self.lineage.check_in(conn, evidence_id)
        return material

    @staticmethod
    def _restore_capture_required_in(conn, evidence_id, material):
        return material['infer'] and conn.execute('SELECT 1 FROM preferences WHERE key=?',
            (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,)).fetchone() is not None

    def enqueue(self, evidence_id, scope: ContextScope, *, automatic=False):
        require_eligible(scope)
        with self.db.transaction() as conn:
            material = self.material(evidence_id, scope, conn=conn)
            if automatic and material.get('_answer') and 'runtime' in material['_answer'][1]['answer_reference']:
                # H05 connected resolver/host acceptance has not activated
                # migrated automatic capture. Explicit capture uses this seam.
                return None
            if conn.execute('SELECT 1 FROM memory_suppression WHERE source_key=?',
                            ('evidence:' + evidence_id,)).fetchone():
                raise ApiError('memory_capture_suppressed', 'This source was removed or corrected in memory', 409)
            if automatic and self._restore_capture_required_in(conn, evidence_id, material):
                return None
            previous = conn.execute('SELECT * FROM memory_jobs WHERE evidence_id=? AND evidence_hash=?',
                                    (evidence_id, material['fingerprint'])).fetchone()
            if previous:
                if automatic:
                    return None
                try:
                    if ContextScope.model_validate_json(previous['scope']) != scope:
                        raise ValueError()
                except (ValueError, TypeError):
                    raise ApiError('memory_job_invalid', 'This capture receipt has a different source scope', 409) from None
                if previous['state'] == 'cancelled' and previous['error_code'] == 'restore_interrupted':
                    # Equal integers from an imported profile do not revive its
                    # execution. Only deliberate capture requeues this receipt;
                    # claim increments attempts to fence the foreign execution.
                    conn.execute(
                        "UPDATE memory_jobs SET state='queued',error_code=NULL,updated_at=? WHERE id=?",
                        (utc_now(), previous['id']))
                    previous = conn.execute('SELECT * FROM memory_jobs WHERE id=?', (previous['id'],)).fetchone()
                if previous['state'] in ('queued', 'running', 'completed'):
                    conn.execute('DELETE FROM preferences WHERE key=?', (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,))
                return dict(previous)
            if automatic:
                history = conn.execute('SELECT * FROM memory_jobs WHERE evidence_id=?', (evidence_id,)).fetchall()
                if (conn.execute('SELECT 1 FROM memory_sources WHERE source_key=?',
                        ('evidence:' + evidence_id,)).fetchone() or
                        any(row['state'] != 'cancelled' or row['error_code'] not in BOUNDARY_CANCELLATIONS
                            for row in history)):
                    return None
                source_revision = fingerprint_parts(material['fingerprint'])[0]
                for row in history:
                    prior = fingerprint_parts(row['evidence_hash'])
                    if prior is None and row['error_code'] != 'restore_interrupted':
                        conn.execute("UPDATE memory_jobs SET error_code='memory_fingerprint_unversioned',updated_at=? WHERE id=?",
                                     (utc_now(), row['id']))
                        return None
                    if prior is not None and prior[0] != source_revision:
                        conn.execute("UPDATE memory_jobs SET error_code='memory_source_changed',updated_at=? WHERE id=?",
                                     (utc_now(), row['id']))
                        return None
            identifier, now = durable_id('memoryjob'), utc_now()
            conn.execute('INSERT INTO memory_jobs VALUES(?,?,?,?,?,?,?,?,?)',
                         (identifier, evidence_id, material['fingerprint'], scope.model_dump_json(),
                          'queued', 0, None, now, now))
            if not automatic:
                conn.execute('DELETE FROM preferences WHERE key=?', (MEMORY_RESTORE_CAPTURE_PREFIX + evidence_id,))
        return self.job(identifier)

    def job(self, identifier):
        row = self.db.fetch_one('SELECT * FROM memory_jobs WHERE id=?', (identifier,))
        if not row:
            raise ApiError('memory_job_missing', 'This capture job is not available', 404)
        return row

    def jobs(self):
        return self.db.fetch_all('SELECT * FROM memory_jobs ORDER BY created_at DESC LIMIT 100')

    def _retire_invalid_recovery(self, evidence_id, code):
        if code in ('assistance_restricted', 'assistance_changed'):
            return
        self.db.execute("UPDATE memory_jobs SET error_code=?,updated_at=? WHERE evidence_id=? "
            "AND state='cancelled' AND error_code IN "
            "('boundary_policy_changed','boundary_context_changed','restore_interrupted')",
            (code, utc_now(), evidence_id))

    def scan(self):
        # Immutable producer records are the queue input, never a raw transcript.
        # Local source/history adapters can revoke dependencies independently
        # of a Memory edit. Retire support before any boundary can requeue it.
        self.reconcile_deletions()
        with self.db.transaction() as conn:
            if not policy_snapshot(conn)['assistance_allowed']:
                return
        cursor, queued = '', 0
        while queued < 100:
            rows = self.db.fetch_all(
                "SELECT e.id,e.kind,e.entity_id,json_extract(e.payload_json,'$.scope') AS declared_scope "
                "FROM learning_evidence e WHERE e.id>? AND json_valid(e.payload_json) "
                "AND e.kind IN ('study-interest','assessment-answer','learning-point','study-answer','assessment-test-answer') "
                "AND (e.kind='assessment-test-answer' OR json_extract(e.payload_json,'$.scope.kind') IN ('study','personal-library','generated-practice','reviewed-assessment') "
                "OR (e.kind='study-interest' AND json_extract(e.payload_json,'$.scope') IS NULL)) "
                "AND NOT EXISTS (SELECT 1 FROM memory_jobs j WHERE j.evidence_id=e.id AND "
                "(j.state<>'cancelled' OR j.error_code IS NULL OR j.error_code NOT IN "
                "('boundary_policy_changed','boundary_context_changed','restore_interrupted'))) "
                "AND NOT EXISTS (SELECT 1 FROM memory_sources s WHERE s.source_key='evidence:' || e.id) "
                "AND NOT EXISTS (SELECT 1 FROM memory_suppression s WHERE s.source_key='evidence:' || e.id) "
                'ORDER BY e.id LIMIT 100', (cursor,))
            if not rows:
                break
            for row in rows:
                cursor = row['id']
                try:
                    if row['kind'] == 'assessment-test-answer':
                        resolver = self.services.registry.get('whole_attempts')
                        if resolver is None:
                            continue
                        with self.db.transaction() as conn:
                            require_assistance(conn)
                            metadata = resolver.committed_evidence_in(conn, row['id'])
                            if metadata is None:
                                raise ApiError('memory_evidence_invalid', 'This answer has no eligible commitment', 409)
                            scope = self._whole_scope(metadata)
                    else:
                        scope = (ContextScope.model_validate_json(row['declared_scope']) if row['declared_scope'] else
                                 ContextScope(kind=Scope.STUDY, entity_id=row['entity_id']))
                    if self.enqueue(row['id'], scope, automatic=True) is not None:
                        queued += 1
                except ApiError as error:
                    if error.code not in CAPTURE_REFUSAL_CODES:
                        raise
                    # A permanent invalidation closes recovery; another policy
                    # boundary merely waits for the next safe scan.
                    self._retire_invalid_recovery(row['id'], error.code)
                    continue
                except (ValueError, TypeError, KeyError):
                    # Ineligible input produces no job, audit or error payload.
                    self._retire_invalid_recovery(row['id'], 'memory_evidence_invalid')
                    continue
                if queued == 100:
                    break

    def claim(self, identifier):
        with self.db.transaction() as conn:
            row = conn.execute('SELECT * FROM memory_jobs WHERE id=?', (identifier,)).fetchone()
            if not row or row['state'] != 'queued':
                return None
            conn.execute("UPDATE memory_jobs SET state='running',attempts=attempts+1,updated_at=?,error_code=NULL WHERE id=?",
                         (utc_now(), identifier))
        return self.job(identifier)

    def _capture_error_in(self, conn, job):
        select = lambda sql, args: conn.execute(sql, args).fetchone()
        row = select('SELECT * FROM memory_jobs WHERE id=?', (job['id'],))
        if row is None or row['state'] != 'running':
            return 'memory_capture_stopped'
        if any(row[field] != job.get(field) for field in ('evidence_id', 'evidence_hash', 'scope', 'attempts')):
            return 'memory_job_invalid'
        if select('SELECT 1 FROM memory_suppression WHERE source_key=?', ('evidence:' + job['evidence_id'],)):
            return 'memory_capture_suppressed'
        if not policy_snapshot(conn)['assistance_allowed']:
            return 'boundary_policy_changed'
        try:
            material = self.material(job['evidence_id'], ContextScope.model_validate_json(job['scope']), conn=conn)
            # Retry and startup may claim an existing row without enqueue. The
            # same canonical guard must refuse inference before provider work or
            # publication until deliberate capture consumes the local barrier.
            if self._restore_capture_required_in(conn, job['evidence_id'], material):
                return 'restore_interrupted'
            current = material['fingerprint']
        except ApiError as error:
            if error.code not in CAPTURE_REFUSAL_CODES:
                raise
            return error.code
        except (ValueError, TypeError, KeyError):
            return 'memory_evidence_invalid'
        if current == job['evidence_hash']:
            return None
        prior, fresh = fingerprint_parts(job['evidence_hash']), fingerprint_parts(current)
        if prior is None:
            source = select('SELECT kind FROM learning_evidence WHERE id=?', (job['evidence_id'],))
            # The earlier whole-attempt hash already pinned both generations.
            # Honor it only when exact current source and boundaries reproduce it.
            if source and source['kind'] == 'assessment-test-answer' and job['evidence_hash'] == digest({
                    'evidence': fresh[0], 'policy_revision': fresh[1], 'context_epoch': fresh[2]}):
                return None
            return 'memory_fingerprint_unversioned'
        if prior[0] != fresh[0]:
            return 'memory_source_changed'
        if prior[1] != fresh[1]:
            return 'boundary_policy_changed'
        return 'boundary_context_changed'

    def current(self, job, *, conn=None):
        if conn is not None:
            return self._capture_error_in(conn, job) is None
        with self.db.transaction() as current:
            return self._capture_error_in(current, job) is None

    @staticmethod
    def _cancel_stale_in(conn, job, code):
        # A forged/stopped caller cannot cancel another canonical execution or
        # overwrite an explicit cancellation, completed capture or restore code.
        conn.execute("UPDATE memory_jobs SET state='cancelled',error_code=?,updated_at=? "
                     "WHERE id=? AND state='running' AND evidence_id=? AND evidence_hash=? AND scope=? AND attempts=?",
                     (code, utc_now(), job['id'], job['evidence_id'], job['evidence_hash'], job['scope'], job['attempts']))

    def cancel_stale(self, job):
        with self.db.transaction() as conn:
            code = self._capture_error_in(conn, job)
            if code is not None:
                self._cancel_stale_in(conn, job, code)
        return self.job(job['id'])

    def commit_capture(self, job, material, texts, *, publication_guard=None):
        # Hash resolved immutable bytes before entering the canonical write.
        answer_digest = (hashlib.sha256(material['text'].encode('utf-8')).hexdigest()
                         if material.get('_answer') else None)
        with self.db.transaction() as conn:
            # Re-evaluate producer revision/scope and cancellation inside the commit transaction.
            code = self._capture_error_in(conn, job)
            if code is not None:
                self._cancel_stale_in(conn, job, code)
                return []
            if material.get('_answer'):
                reference = material['_answer'][1]['answer_reference']
                if 'runtime' in reference:
                    current = self.material(job['evidence_id'], ContextScope.model_validate_json(job['scope']),
                                            conn=conn, resolve_answer=False)
                    same = (current['_answer'][1]['answer_reference'] == reference and
                            current['lineage'] == material['lineage'] and reference['sha256'] == answer_digest)
                else:
                    # Legacy bytes use a local equality recheck without
                    # resolving remotely or returning transcript content.
                    row = conn.execute("SELECT content=? FROM learn_messages WHERE id=?",
                        (material['text'], reference['message_id'])).fetchone()
                    same = row is not None and row[0]
                if not same:
                    self._cancel_stale_in(conn, job, 'memory_answer_version')
                    return []
            source = conn.execute('SELECT kind FROM learning_evidence WHERE id=?', (job['evidence_id'],)).fetchone()
            if source and source['kind'] == 'assessment-test-answer':
                # Structured commitments never accept generated or caller-supplied
                # text. Resolve the exact current scalar material in this write.
                material = self.material(job['evidence_id'], ContextScope.model_validate_json(job['scope']), conn=conn)
                texts = [material['text']]
            if publication_guard is not None:
                _local_result(publication_guard(conn))
            identifiers = []
            for text in texts:
                lineage = material.get('lineage')
                identifier = self._insert(conn, text, material['kind'], material['topic_id'],
                    material['scope'].kind.value, 'learning-evidence', job['evidence_id'],
                    'evidence:' + job['evidence_id'], project_id=lineage['project_id'] if lineage else None)
                self.lineage.add_support_in(conn, identifier, 'evidence:' + job['evidence_id'],
                    manifest=AnswerInputs.model_validate_json(lineage['manifest_json']) if lineage else None,
                    project_id=lineage['project_id'] if lineage else None, kind='generated' if lineage else 'activity')
                identifiers.append(identifier)
            conn.execute("UPDATE memory_jobs SET state='completed',updated_at=? WHERE id=?",
                         (utc_now(), job['id']))
        return identifiers

    def cancel(self, identifier):
        self.db.execute("UPDATE memory_jobs SET state='cancelled',error_code='explicit_cancelled',updated_at=? "
                        "WHERE id=? AND state IN ('queued','running','failed','cancelled')", (utc_now(), identifier))
        return self.job(identifier)

    def fail(self, identifier, code):
        self.db.execute("UPDATE memory_jobs SET state='failed',error_code=?,updated_at=? "
                        "WHERE id=? AND state='running'", (code, utc_now(), identifier))

    def retry(self):
        return self.db.execute("UPDATE memory_jobs SET state='queued',error_code=NULL,updated_at=? "
                               "WHERE state='failed'", (utc_now(),))
