# SPDX-License-Identifier: MIT
"""One profile-wide assistance boundary, checked again before publication.

The attempt owner reconciles expiry/finalisation before request dispatch. Reads
and writes inside this module use the caller's transaction, so help producers
cannot publish against a stale start/end policy revision. This local generation
is deliberately excluded from canonical exports.
"""
from ..contracts import ApiError
from .database import utc_now

POLICY_REVISION = "design_c.assessment_policy_revision"


def policy_snapshot(conn):
    row = conn.execute("SELECT value FROM preferences WHERE key=?", (POLICY_REVISION,)).fetchone()
    revision = int(row["value"]) if row else 1
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='assessment_test_attempts'").fetchone()
    active = conn.execute("SELECT id FROM assessment_test_attempts WHERE mode='test' AND status='active' LIMIT 1").fetchone() if exists else None
    return {"revision": revision, "active_test_id": active["id"] if active else None,
            "assistance_allowed": active is None}


def require_assistance(conn, *, expected_revision=None):
    snapshot = policy_snapshot(conn)
    if not snapshot["assistance_allowed"]:
        raise ApiError("assistance_restricted", "Submit the active Test before opening learning help.", 409)
    if expected_revision is not None and snapshot["revision"] != expected_revision:
        raise ApiError("assistance_changed", "The assessment policy changed. Retry this learning action.", 409, True)
    return snapshot["revision"]


def advance_policy(conn):
    """Attempt start/finalisation calls this in the same canonical transaction."""
    conn.execute("INSERT INTO preferences VALUES(?,'2',?) ON CONFLICT(key) DO UPDATE SET "
                 "value=CAST(CAST(preferences.value AS INTEGER)+1 AS TEXT),updated_at=excluded.updated_at",
                 (POLICY_REVISION, utc_now()))
    return policy_snapshot(conn)["revision"]
