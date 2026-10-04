CREATE TABLE IF NOT EXISTS retrieval_usage (
    provider TEXT NOT NULL,
    day TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0 CHECK(requests >= 0),
    credits INTEGER NOT NULL DEFAULT 0 CHECK(credits >= 0),
    PRIMARY KEY(provider, day)
);
CREATE TABLE IF NOT EXISTS retrieval_health (
    provider TEXT PRIMARY KEY,
    last_attempt_at TEXT,
    last_success_at TEXT,
    error_code TEXT
);
-- Only explicit, rights-checked public article imports have replay records.
-- Keep identifiers, not another copy of article text or submitted case data.
CREATE TABLE IF NOT EXISTS retrieval_imports (
    key_hash TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    pmcid TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    xml_sha256 TEXT,
    document_id TEXT,
    revision_id TEXT,
    job_id TEXT
);
