-- Additive Updates-owned records; updates-001 remains immutable.
CREATE TABLE update_publications(
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES update_source_checks(source_id),
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    permission_reference TEXT NOT NULL,
    max_bytes INTEGER NOT NULL CHECK(max_bytes BETWEEN 1024 AND 20000000),
    tracked_at TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
    digest TEXT,
    observation INTEGER NOT NULL DEFAULT 0,
    fetch_metadata_json TEXT NOT NULL DEFAULT '{}',
    last_checked_at TEXT,
    last_success_at TEXT,
    state TEXT NOT NULL DEFAULT 'never-checked',
    error_code TEXT,
    UNIQUE(source_id,url)
);
CREATE INDEX update_entry_order ON update_entries(discovered_at DESC,id DESC);
