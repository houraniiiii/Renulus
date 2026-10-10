-- Historical original pins have no pruning foreign key; live availability is independent.
CREATE TABLE assessment_test_attempts (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL, live_version_id TEXT,
 version_snapshot_json TEXT NOT NULL CHECK(json_valid(version_snapshot_json)),
 mode TEXT NOT NULL CHECK(mode IN ('study','test')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','paused','timer_expired','submitted','ended')),
 draft_revision INTEGER NOT NULL DEFAULT 0 CHECK(draft_revision >= 0),
 timing_kind TEXT NOT NULL DEFAULT 'untimed' CHECK(timing_kind IN ('untimed','timed')),
 duration_seconds INTEGER CHECK(duration_seconds BETWEEN 1 AND 86400), started_at TEXT, deadline_at TEXT,
 paused_seconds INTEGER NOT NULL DEFAULT 0 CHECK(paused_seconds >= 0),
 committed_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(committed_json)),
 result_json TEXT CHECK(result_json IS NULL OR json_valid(result_json)),
 clock_high_water_at TEXT NOT NULL, paused_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finalized_at TEXT,
 CHECK(mode != 'test' OR (status IN ('active','submitted') AND paused_seconds = 0 AND paused_at IS NULL)),
 CHECK(timing_kind != 'timed' OR (duration_seconds IS NOT NULL AND started_at IS NOT NULL AND deadline_at IS NOT NULL))
);
CREATE UNIQUE INDEX assessment_one_active_test ON assessment_test_attempts((1)) WHERE mode='test' AND status='active';
CREATE TABLE assessment_attempt_drafts (
 attempt_id TEXT PRIMARY KEY REFERENCES assessment_test_attempts(id) ON DELETE CASCADE,
 revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0), position INTEGER NOT NULL DEFAULT 0 CHECK(position BETWEEN 0 AND 49),
 answers_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(answers_json)), updated_at TEXT NOT NULL
);
CREATE TABLE assessment_attempt_exposure (
 id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES assessment_test_attempts(id) ON DELETE CASCADE,
 item_id TEXT NOT NULL, question_id TEXT NOT NULL, question_version TEXT NOT NULL, key_version TEXT,
 family_id TEXT NOT NULL, family_version TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('presented','hint','sources','notes','chat','answered','reviewed')), created_at TEXT NOT NULL,
 UNIQUE(attempt_id,item_id,kind)
);
CREATE INDEX assessment_attempts_recent ON assessment_test_attempts(updated_at,id);
CREATE TABLE assessment_attempt_commands (
 idempotency_key TEXT PRIMARY KEY, operation TEXT NOT NULL, target_type TEXT NOT NULL,
 target_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json TEXT NOT NULL CHECK(json_valid(result_json)), created_at TEXT NOT NULL
);
