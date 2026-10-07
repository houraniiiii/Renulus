-- Separate generated records. Temporary/unclassified/case derivatives never use these tables.
CREATE TABLE assessment_generated_sessions (
    id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK (scope = 'generated-practice'),
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'ended')),
    topic_id TEXT,
    source_verification TEXT NOT NULL CHECK (source_verification IN ('retrieved', 'not-verified')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE assessment_generated_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assessment_generated_sessions(id),
    ordinal INTEGER NOT NULL,
    snapshot_json TEXT NOT NULL,
    assisted INTEGER NOT NULL DEFAULT 0 CHECK (assisted IN (0, 1)),
    presented INTEGER NOT NULL DEFAULT 0 CHECK (presented IN (0, 1)),
    UNIQUE(session_id, ordinal)
);
CREATE TABLE assessment_generated_attempts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assessment_generated_sessions(id),
    item_id TEXT NOT NULL UNIQUE REFERENCES assessment_generated_items(id),
    answer_json TEXT NOT NULL,
    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
    assisted INTEGER NOT NULL CHECK (assisted IN (0, 1)),
    committed_at TEXT NOT NULL
);
CREATE TABLE assessment_generated_commands (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    target TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX assessment_generated_sessions_updated ON assessment_generated_sessions(updated_at);
