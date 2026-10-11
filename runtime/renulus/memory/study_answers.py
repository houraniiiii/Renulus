"""Resolve one immutable, completed ordinary Study answer without a transcript."""
from contextlib import closing
import hashlib
import json
import re

from pydantic import TypeAdapter

from renulus.contracts import ApiError, Scope
from renulus.design_c_contracts import ContentReference, Identifier, Locator
from renulus.harness_contracts import HarnessEngineReference, SavedConversationMapping

MAX_ANSWER_CHARS = 16000


def _native_reference_in(conn, evidence, reference, scope, *, publication):
    """Validate reference-only local receipts; only publication admits staging."""
    from .lineage import AnswerInputs
    try:
        if (set(reference) != {'version', 'run_id', 'thread_id', 'runtime', 'input_id',
                'message_ids', 'sha256', 'citations', 'inputs', 'dependencies'} or
                type(reference['version']) is not int or reference['version'] != 1 or
                not isinstance(reference['sha256'], str) or
                not re.fullmatch(r'[0-9a-f]{64}', reference['sha256']) or
                not isinstance(reference['message_ids'], list) or
                not 1 <= len(reference['message_ids']) <= 100 or
                not isinstance(reference['citations'], list) or len(reference['citations']) > 100 or
                not isinstance(reference['inputs'], list) or not isinstance(reference['dependencies'], list) or
                len(json.dumps(reference, allow_nan=False).encode('utf-8')) > 65536):
            raise ValueError()
        identifier = TypeAdapter(Identifier)
        for value in (reference['run_id'], reference['thread_id'], reference['input_id'], *reference['message_ids']):
            identifier.validate_python(value)
        if (len(set(reference['message_ids'])) != len(reference['message_ids']) or
                reference['input_id'] in reference['message_ids'] or
                reference['thread_id'] != scope.entity_id or
                evidence['id'] != 'learn-answer:' + reference['run_id']):
            raise ValueError()
        runtime = HarnessEngineReference.model_validate(reference['runtime'])
        AnswerInputs(inputs=reference['inputs'], dependencies=reference['dependencies'])
        for citation in reference['citations']:
            if not isinstance(citation, dict) or set(citation) - {'content_ref', 'passage_id', 'document_id', 'revision_id', 'locator'}:
                raise ValueError()
            for key in ('passage_id', 'document_id', 'revision_id'):
                if key in citation:
                    identifier.validate_python(citation[key])
            if 'content_ref' in citation:
                ContentReference.model_validate(citation['content_ref'])
            if 'locator' in citation:
                TypeAdapter(Locator).validate_python(citation['locator'])
    except (ValueError, TypeError, KeyError):
        raise ApiError('memory_answer_reference', 'Capture needs an exact bounded native answer reference', 409) from None
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='learn_harness_answers'").fetchone():
        raise ApiError('memory_answer_unavailable', 'The native answer receipt is unavailable', 409)
    row = conn.execute(
        'SELECT a.*,r.state AS run_state,r.thread_id AS run_thread,m.profile_id,m.store_id,m.session_id,m.mapping_json '
        'FROM learn_harness_answers a JOIN learn_runs r ON r.id=a.run_id '
        'JOIN learn_threads t ON t.id=a.thread_id JOIN learn_harness_mappings m ON m.thread_id=a.thread_id WHERE a.run_id=?',
        (reference['run_id'],)).fetchone()
    staged = (row is not None and publication and conn.in_transaction and row['state'] == 'submitted' and
              row['run_state'] == 'running' and row['publication_digest'] is None)
    if (not row or (not staged and (row['state'] != 'completed' or row['run_state'] != 'completed')) or
            row['thread_id'] != scope.entity_id or row['run_thread'] != scope.entity_id or
            row['input_id'] != reference['input_id'] or
            (row['profile_id'], row['store_id'], row['session_id']) != (runtime.profile_id, runtime.store_id, runtime.session_id)):
        raise ApiError('memory_answer_unavailable', 'The completed native answer is no longer eligible', 409)
    try:
        mapping = SavedConversationMapping.model_validate_json(row['mapping_json'])
        if (json.loads(row['reference_json']) != reference or mapping.runtime != runtime or
                mapping.conversation.type != 'learn_thread' or mapping.conversation.id != scope.entity_id):
            raise ValueError()
    except (ValueError, TypeError):
        raise ApiError('memory_answer_reference', 'The native answer does not match its exact staged receipt and mapping', 409) from None
    if not staged:
        lineage = conn.execute('SELECT publication_digest FROM memory_answer_lineage WHERE evidence_id=?', (evidence['id'],)).fetchone()
        if lineage is None or row['publication_digest'] != lineage['publication_digest']:
            raise ApiError('memory_answer_version', 'The native answer publication changed or has unknown lineage', 409)
    for message_id in reference['message_ids']:
        if conn.execute("SELECT 1 FROM deletion_ledger WHERE entity_type='learn_message' AND entity_id=?", (message_id,)).fetchone():
            raise ApiError('memory_evidence_deleted', 'This native answer message has been removed', 409)
    if conn.execute("SELECT 1 FROM deletion_ledger WHERE (entity_type='learn_thread' AND entity_id=?) OR "
        "(entity_type='learn_run' AND entity_id=?) OR (entity_type='learning_evidence' AND entity_id=?)",
        (scope.entity_id, reference['run_id'], evidence['id'])).fetchone():
        raise ApiError('memory_evidence_deleted', 'This native Study answer has been removed', 409)
    return reference


def answer_reference_in(conn, evidence, payload, scope, *, publication=False):
    reference = payload.get("answer_reference")
    if isinstance(reference, dict) and 'runtime' in reference:
        if (scope.kind != Scope.STUDY or scope.entity_id != evidence['entity_id'] or
                set(payload) != {'scope', 'answer_reference'}):
            raise ApiError('memory_answer_reference', 'Native answer capture needs its original ordinary Study scope', 409)
        if conn.execute('SELECT 1 FROM memory_suppression WHERE source_key=?', ('evidence:' + evidence['id'],)).fetchone():
            raise ApiError('memory_capture_suppressed', 'This source was removed or corrected in memory', 409)
        return _native_reference_in(conn, evidence, reference, scope, publication=publication)
    if (scope.kind != Scope.STUDY or scope.entity_id != evidence["entity_id"] or
            set(payload) != {"scope", "answer_reference"} or not isinstance(reference, dict) or
            set(reference) != {"message_id", "run_id", "sha256", "version"} or
            type(reference["version"]) is not int or reference["version"] != 1 or
            any(not isinstance(reference[key], str) for key in ("message_id", "run_id", "sha256")) or
            not re.fullmatch(r"message_[A-Za-z0-9_-]{1,100}", reference["message_id"]) or
            not re.fullmatch(r"run_[A-Za-z0-9_-]{1,100}", reference["run_id"]) or
            not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]) or
            evidence["id"] != "learn-answer:" + reference["run_id"]):
        raise ApiError("memory_answer_reference", "Capture needs an exact completed ordinary Study answer reference", 409)
    if conn.execute("SELECT 1 FROM memory_suppression WHERE source_key=?",
                    ("evidence:" + evidence["id"],)).fetchone():
        raise ApiError("memory_capture_suppressed", "This source was removed or corrected in memory", 409)
    # Only metadata is read until completion, ownership and deletion pass.
    row = conn.execute(
        "SELECT m.thread_id,m.run_id,m.role,r.state,r.thread_id AS run_thread "
        "FROM learn_messages m JOIN learn_runs r ON r.id=m.run_id "
        "JOIN learn_threads t ON t.id=m.thread_id WHERE m.id=?",
        (reference["message_id"],)).fetchone()
    if (not row or row["role"] != "assistant" or row["state"] != "completed" or
            row["run_id"] != reference["run_id"] or row["thread_id"] != scope.entity_id or
            row["run_thread"] != scope.entity_id):
        raise ApiError("memory_answer_unavailable", "The completed Study answer is no longer eligible", 409)
    if conn.execute(
            "SELECT 1 FROM deletion_ledger WHERE "
            "(entity_type='learn_thread' AND entity_id=?) OR "
            "(entity_type='learn_run' AND entity_id=?) OR "
            "(entity_type='learn_message' AND entity_id=?) OR "
            "(entity_type='learning_evidence' AND entity_id=?)",
            (scope.entity_id, reference["run_id"], reference["message_id"], evidence["id"])).fetchone():
        raise ApiError("memory_evidence_deleted", "This Study answer has been removed", 409)
    return reference


def answer_text(db, evidence, payload, scope):
    # No caller transaction or physical worker lock spans byte resolution.
    with closing(db.connect()) as conn:
        reference = answer_reference_in(conn, evidence, payload, scope)
        if 'runtime' in reference:
            raise ApiError('memory_answer_resolver_unavailable', 'Native answer bytes require the completed async resolver', 503, True)
        length = conn.execute("SELECT length(content) FROM learn_messages WHERE id=?",
                              (reference["message_id"],)).fetchone()[0]
        if not 0 < length <= MAX_ANSWER_CHARS:
            raise ApiError("memory_answer_budget", "Automatic capture accepts exact Study replies up to 16,000 characters", 409)
        text = conn.execute(
            "SELECT content FROM learn_messages WHERE id=? AND role='assistant' AND run_id=? AND thread_id=?",
            (reference["message_id"], reference["run_id"], scope.entity_id)).fetchone()[0]
        if not text.strip() or hashlib.sha256(text.encode("utf-8")).hexdigest() != reference["sha256"]:
            raise ApiError("memory_answer_version", "The referenced Study answer version has changed", 409)
        return text
