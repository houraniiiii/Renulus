CREATE TABLE assessment_sessions (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode = 'reviewed'),
    scope TEXT NOT NULL CHECK (scope = 'reviewed-assessment'),
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'ended')),
    selector_json TEXT NOT NULL,
    coverage_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ended_at TEXT
);
CREATE TABLE assessment_items (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assessment_sessions(id),
    ordinal INTEGER NOT NULL,
    question_id TEXT NOT NULL,
    question_version TEXT NOT NULL,
    key_version TEXT NOT NULL,
    family_id TEXT NOT NULL,
    family_version TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    snapshot_json TEXT NOT NULL,
    presented_at TEXT,
    assisted INTEGER NOT NULL DEFAULT 0 CHECK (assisted IN (0, 1)),
    UNIQUE (session_id, ordinal),
    UNIQUE (session_id, family_id)
);
CREATE TABLE assessment_attempts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES assessment_sessions(id),
    item_id TEXT NOT NULL UNIQUE REFERENCES assessment_items(id),
    question_id TEXT NOT NULL,
    question_version TEXT NOT NULL,
    key_version TEXT NOT NULL,
    family_id TEXT NOT NULL,
    family_version TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    answer_json TEXT NOT NULL,
    correct INTEGER NOT NULL CHECK (correct IN (0, 1)),
    assisted INTEGER NOT NULL CHECK (assisted IN (0, 1)),
    repeat INTEGER NOT NULL CHECK (repeat IN (0, 1)),
    score_bucket TEXT NOT NULL CHECK (score_bucket IN ('fresh', 'assisted', 'repeat')),
    committed_at TEXT NOT NULL
);
CREATE TABLE assessment_exposure (
    id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_version TEXT NOT NULL,
    item_id TEXT NOT NULL REFERENCES assessment_items(id),
    kind TEXT NOT NULL CHECK (kind IN ('presented', 'hint', 'sources', 'answered', 'reviewed')),
    created_at TEXT NOT NULL,
    UNIQUE (item_id, kind)
);
CREATE INDEX assessment_exposure_family ON assessment_exposure(family_id, item_id);
CREATE INDEX assessment_sessions_updated ON assessment_sessions(updated_at);
CREATE TABLE assessment_commands (
    idempotency_key TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    target TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
