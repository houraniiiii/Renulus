CREATE TABLE study_activities(
    id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    objective_id TEXT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    due_date TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    reason_json TEXT NOT NULL,
    evidence_id TEXT,
    state TEXT NOT NULL CHECK(state IN ('planned','completed','skipped')),
    manual_override INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX study_due ON study_activities(state, due_date);
