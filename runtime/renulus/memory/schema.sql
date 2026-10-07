CREATE TABLE memory_facts (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    kind TEXT NOT NULL,
    topic_id TEXT,
    scope TEXT NOT NULL CHECK(scope IN ('study','personal-library','generated-practice','reviewed-assessment')),
    revision INTEGER NOT NULL CHECK(revision > 0),
    source_kind TEXT NOT NULL,
    source_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX memory_fact_hash ON memory_facts(text_hash,kind,topic_id);
CREATE TABLE memory_history (
    record_id TEXT NOT NULL REFERENCES memory_facts(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    text TEXT NOT NULL,
    event TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(record_id,revision)
);
CREATE TABLE memory_sources (
    source_key TEXT NOT NULL,
    record_id TEXT NOT NULL REFERENCES memory_facts(id) ON DELETE CASCADE,
    PRIMARY KEY(source_key,record_id)
);
CREATE TABLE memory_suppression (
    source_key TEXT PRIMARY KEY,
    suppressed_at TEXT NOT NULL
);
CREATE TABLE memory_requests (
    idempotency_key TEXT PRIMARY KEY,
    request_hash TEXT NOT NULL,
    record_id TEXT NOT NULL
);
CREATE TABLE memory_jobs (
    id TEXT PRIMARY KEY,
    evidence_id TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    scope TEXT NOT NULL CHECK(json_extract(scope,'$.kind') IN ('study','personal-library','generated-practice','reviewed-assessment')),
    state TEXT NOT NULL CHECK(state IN ('queued','running','completed','failed','cancelled')),
    attempts INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(evidence_id,evidence_hash)
);
CREATE TABLE memory_index_state (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    epoch INTEGER NOT NULL DEFAULT 0,
    generation TEXT,
    fingerprint TEXT,
    state TEXT NOT NULL,
    error_code TEXT
);
INSERT INTO memory_index_state(singleton,state) VALUES(1,'empty');
CREATE TABLE memory_index_entries (
    record_id TEXT PRIMARY KEY REFERENCES memory_facts(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    engine_id TEXT NOT NULL,
    generation TEXT NOT NULL
);
