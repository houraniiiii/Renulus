-- SPDX-License-Identifier: MIT
-- Stable store identity is metadata; physical database substitution must fail.
CREATE TABLE harness_store_identity(
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    profile_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    snapshot_generation INTEGER NOT NULL CHECK(snapshot_generation>0),
    cohort_source TEXT NOT NULL
);
