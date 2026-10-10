# SPDX-License-Identifier: MIT
"""Request-bound publication guards also follow explicitly detached tasks."""
from contextlib import contextmanager
from contextvars import ContextVar
from contextlib import closing
import json

_guard = ContextVar('renulus_publication_guard', default=None)


@contextmanager
def bind_publication_guard(database, callback):
    token = _guard.set((database, callback))
    try:
        yield
    finally:
        _guard.reset(token)


def check_publication(database, connection):
    current = _guard.get()
    if current is not None and current[0] is database:
        current[1](connection)


def record_interrupted_conversation(database, kind, identifier, run_id):
    """Close an existing running receipt without publishing any assistance.

    This is deliberately a fixed SQL operation, not a general guard bypass. A
    stale Study receipt may prevent all normal transactions. Only the running
    command and its Learn run status change here; messages, drafts, sidecars and
    evidence never change. A deleted owner or a terminal winner is preserved.
    """
    from .database import utc_now
    identities = {"learning":("learn_thread", "learn_threads"), "case":("case", "case_sessions")}
    if kind not in identities:
        raise ValueError("Unknown conversation kind")
    target_type, owner = identities[kind]
    with closing(database.connect()) as conn:
        try:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute(f"SELECT 1 FROM {owner} WHERE id=?", (identifier,)).fetchone():
                conn.rollback()
                return None
            row = conn.execute("SELECT idempotency_key,result_json FROM conversation_commands "
                "WHERE operation='send' AND target_type=? AND target_id=? "
                "AND json_extract(result_json,'$.run_id')=?", (target_type, identifier, run_id)).fetchone()
            if row is None:
                conn.rollback()
                return None
            receipt = json.loads(row["result_json"])
            if receipt.get("state") == "running":
                receipt.update(state="interrupted", error={"code":"response_interrupted",
                    "message":"The response did not finish. Your draft is retained.", "retryable":True})
                conn.execute("UPDATE conversation_commands SET result_json=? WHERE idempotency_key=?",
                    (json.dumps(receipt), row["idempotency_key"]))
                if kind == "learning":
                    conn.execute("UPDATE learn_runs SET state='interrupted',error_code='response_interrupted',updated_at=? "
                        "WHERE id=? AND thread_id=? AND state='running'", (utc_now(), run_id, identifier))
            conn.commit()
            return receipt
        except BaseException:
            conn.rollback()
            raise
