-- Independent reviewed status and impact evidence; no applied DDL is rewritten.
CREATE TABLE update_reviews(
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES update_entries(id),
    target_json TEXT NOT NULL,
    changes_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    topic_ids_json TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reviewed','dismissed')),
    reviewed_at TEXT NOT NULL,
    library_sync_state TEXT NOT NULL DEFAULT 'not-requested',
    library_sync_error TEXT,
    library_result_json TEXT
);
CREATE TABLE update_review_heads(
    entry_id TEXT PRIMARY KEY REFERENCES update_entries(id),
    review_id TEXT NOT NULL REFERENCES update_reviews(id)
);
CREATE TABLE update_source_statuses(
    target_key TEXT PRIMARY KEY,
    target_json TEXT NOT NULL,
    status_json TEXT NOT NULL,
    review_id TEXT NOT NULL REFERENCES update_reviews(id)
);
CREATE TABLE update_affected_versions(
    entry_id TEXT NOT NULL REFERENCES update_entries(id),
    kind TEXT NOT NULL CHECK(kind IN ('question','case')),
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    pinned_source_id TEXT NOT NULL,
    register_id TEXT NOT NULL,
    locators_json TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    objective_ids_json TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    basis TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'needs-re-review' CHECK(state IN ('needs-re-review','dismissed')),
    PRIMARY KEY(entry_id,kind,entity_id,version,pinned_source_id)
);
CREATE INDEX update_affected_lookup ON update_affected_versions(kind,entity_id,version,state);
CREATE TABLE update_library_changes(
    id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES update_entries(id),
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    last_attempt_at TEXT,
    error_code TEXT,
    result_json TEXT
);
CREATE TABLE update_literature_records(
    external_id TEXT PRIMARY KEY,
    entry_id TEXT NOT NULL REFERENCES update_entries(id),
    fingerprint TEXT NOT NULL,
    observation INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL,
    last_checked_at TEXT,
    last_success_at TEXT,
    state TEXT NOT NULL,
    error_code TEXT
);
CREATE TABLE update_literature_checks(
    topic_id TEXT PRIMARY KEY,
    last_checked_at TEXT NOT NULL,
    last_success_at TEXT,
    state TEXT NOT NULL,
    error_code TEXT,
    result_count INTEGER
);
