# SPDX-License-Identifier: MIT
"""Local derived-context generation; excluded from canonical learning exports."""
from .database import utc_now

CONTEXT_EPOCH = "design_c.context_epoch"
LIBRARY_DIRTY = "knowledge.restore_dirty"


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
