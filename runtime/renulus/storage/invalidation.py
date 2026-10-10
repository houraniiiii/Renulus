# SPDX-License-Identifier: MIT
"""Local derived-context generation; excluded from canonical learning exports."""
from .database import utc_now

CONTEXT_EPOCH = "design_c.context_epoch"
LIBRARY_DIRTY = "knowledge.restore_dirty"
MEMORY_RESTORE_CAPTURE_PREFIX = "memory.restore_capture:"


def context_epoch(db):
    row = db.fetch_one("SELECT value FROM preferences WHERE key=?", (CONTEXT_EPOCH,))
    return int(row["value"]) if row else 0


def context_epoch_in(conn):
    """Capture the local generation in the caller's canonical transaction."""
    row = conn.execute("SELECT value FROM preferences WHERE key=?", (CONTEXT_EPOCH,)).fetchone()
    return int(row["value"]) if row else 0


def bump_context_epoch(conn):
    conn.execute("INSERT INTO preferences VALUES(?,'1',?) ON CONFLICT(key) DO UPDATE SET "
        "value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at",
        (CONTEXT_EPOCH, utc_now()))


def invalidate_restored_context(conn):
    # Do this in the canonical merge transaction before restored data can be
    # read. Recovery's later local rebuild is allowed to fail; old indexes must
    # not remain labelled ready in that interval. No provider work is queued.
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_index_state'").fetchone()
    if exists:
        conn.execute("UPDATE memory_index_state SET epoch=epoch+1,state='dirty',error_code=NULL WHERE singleton=1")
    conn.execute("INSERT INTO preferences VALUES(?,'true',?) ON CONFLICT(key) DO UPDATE SET "
        "value=excluded.value,updated_at=excluded.updated_at", (LIBRARY_DIRTY, utc_now()))
    bump_context_epoch(conn)
    # A restored immutable source is not new learning. Mark the complete merged
    # evidence set, including rows that never had a capture job. Memory decides
    # whether material needs inference; only an explicit capture may consume that
    # local barrier for inference work. New evidence created after this transaction
    # is unmarked. These identity/epoch markers are outside the export whitelist.
    conn.execute("INSERT INTO preferences(key,value,updated_at) "
        "SELECT ? || id,?,? FROM learning_evidence WHERE 1 "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at",
        (MEMORY_RESTORE_CAPTURE_PREFIX, str(context_epoch_in(conn)), utc_now()))
    # Epoch integers belong to one profile. An imported producer can coincidentally
    # carry the destination's next epoch, but its process/task cannot be restored.
    # Keep validated checkpoints; require an explicit retry rather than adopting
    # an orphan or allowing a pre-restore producer to publish into restored state.
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='assessment_test_jobs'").fetchone()
    if exists:
        conn.execute("UPDATE assessment_test_jobs SET state='failed',error_code='interrupted',updated_at=? "
            "WHERE state IN ('queued','running') AND operation IN ('generate_test','nightly_test','daily_suggestions')", (utc_now(),))
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='memory_jobs'").fetchone()
    imports = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='assessment_test_imports'").fetchone()
    if imports:
        conn.execute("UPDATE assessment_test_imports SET state='failed',error_code='interrupted',updated_at=? "
                     "WHERE state='running'", (utc_now(),))
    if exists:
        conn.execute("UPDATE memory_jobs SET state='cancelled',error_code='restore_interrupted',updated_at=? "
                     "WHERE state IN ('queued','running')", (utc_now(),))
