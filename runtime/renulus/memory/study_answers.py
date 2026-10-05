"""Resolve one immutable, completed ordinary Study answer without a transcript."""
from contextlib import closing
import hashlib
import re

from renulus.contracts import ApiError, Scope

MAX_ANSWER_CHARS = 16000


def answer_text(db, evidence, payload, scope):
    reference = payload.get("answer_reference")
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
    with closing(db.connect()) as conn:
        conn.execute("BEGIN")
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
