CREATE TABLE learn_threads(
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    topic_id TEXT,
    teaching_style TEXT NOT NULL CHECK(teaching_style IN ('direct','guided')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE learn_messages(
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES learn_threads(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE learn_runs(
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL REFERENCES learn_threads(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL CHECK(state IN ('running','completed','cancelled','failed','interrupted')),
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX learn_messages_thread ON learn_messages(thread_id, created_at);
