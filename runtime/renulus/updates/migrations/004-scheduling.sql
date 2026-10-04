-- Opt-in local scheduling. Existing observation and review schemas are unchanged.
CREATE TABLE update_schedule(
    id INTEGER PRIMARY KEY CHECK(id=1),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
    cadence_hours INTEGER NOT NULL DEFAULT 24 CHECK(cadence_hours BETWEEN 24 AND 720),
    updated_at TEXT NOT NULL
);
INSERT INTO update_schedule(id,updated_at) VALUES(1,strftime('%Y-%m-%dT%H:%M:%f+00:00','now'));
CREATE TABLE update_schedule_jobs(
    kind TEXT NOT NULL CHECK(kind IN ('source','publication','literature')),
    target_id TEXT NOT NULL,
    next_due_at TEXT NOT NULL,
    last_attempt_at TEXT,
    last_success_at TEXT,
    state TEXT NOT NULL DEFAULT 'waiting',
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK(retry_count BETWEEN 0 AND 2),
    failure_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    PRIMARY KEY(kind,target_id)
);
CREATE TABLE update_schedule_runs(
    id TEXT PRIMARY KEY,
    trigger TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    state TEXT NOT NULL,
    checked INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error_code TEXT
);
