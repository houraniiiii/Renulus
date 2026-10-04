CREATE TABLE update_source_checks(
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    fingerprint TEXT,
    links_json TEXT NOT NULL DEFAULT '[]',
    snapshot_status TEXT NOT NULL,
    last_checked_at TEXT,
    last_success_at TEXT,
    state TEXT NOT NULL DEFAULT 'never-checked',
    error_code TEXT
);
CREATE TABLE update_entries(
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    external_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,
    publication_date TEXT,
    discovered_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewer TEXT,
    review_state TEXT NOT NULL CHECK(review_state IN ('pending','reviewed','dismissed')),
    summary TEXT NOT NULL,
    topic_ids_json TEXT NOT NULL DEFAULT '[]',
    source_metadata_json TEXT NOT NULL,
    read_at TEXT
);
CREATE INDEX update_review ON update_entries(review_state,discovered_at);
