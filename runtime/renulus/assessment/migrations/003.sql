-- Saved collections/immutable versions are distinct from all legacy sessions and answers.
CREATE TABLE assessment_tests (
 id TEXT PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
 lifecycle TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle IN ('active','archived','deleted')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE assessment_test_versions (
 id TEXT PRIMARY KEY, test_id TEXT NOT NULL REFERENCES assessment_tests(id) ON DELETE CASCADE,
 ordinal INTEGER NOT NULL CHECK(ordinal > 0), origin TEXT NOT NULL CHECK(origin IN ('reviewed_bank','generated','imported','nightly')),
 review_quality TEXT NOT NULL CHECK(review_quality IN ('reviewed','personal','needs_review')),
 status TEXT NOT NULL CHECK(status IN ('ready','needs_review')),
 items_json TEXT NOT NULL CHECK(json_valid(items_json)), source_refs_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(source_refs_json)),
 terms TEXT NOT NULL, sha256 TEXT NOT NULL,
 provenance_json TEXT NOT NULL DEFAULT '{"schema":"saved-test-provenance/1"}' CHECK(json_valid(provenance_json)), created_at TEXT NOT NULL,
 UNIQUE(test_id,ordinal), CHECK(review_quality != 'reviewed' OR origin = 'reviewed_bank')
);
CREATE TABLE assessment_test_commands (
 idempotency_key TEXT PRIMARY KEY, operation TEXT NOT NULL, target_type TEXT NOT NULL,
 target_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json TEXT NOT NULL CHECK(json_valid(result_json)), created_at TEXT NOT NULL
);
CREATE TABLE assessment_question_reports (
 id TEXT PRIMARY KEY, version_id TEXT NOT NULL, live_version_id TEXT,
 attempt_id TEXT, live_attempt_id TEXT, item_id TEXT NOT NULL, question_id TEXT NOT NULL,
 question_version TEXT NOT NULL, key_version TEXT, family_id TEXT NOT NULL, family_version TEXT NOT NULL,
 report_text TEXT NOT NULL CHECK(length(report_text) BETWEEN 1 AND 2000), idempotency_key TEXT NOT NULL UNIQUE,
 request_hash TEXT NOT NULL, question_snapshot_json TEXT NOT NULL CHECK(json_valid(question_snapshot_json)), created_at TEXT NOT NULL
);
CREATE TABLE assessment_test_jobs (
 id TEXT PRIMARY KEY, operation TEXT NOT NULL CHECK(operation IN ('daily_suggestions','generate_test','nightly_test')),
 state TEXT NOT NULL CHECK(state IN ('queued','running','needs_review','failed','cancelled','published')),
 idempotency_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 inputs_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(inputs_json)),
 checkpoint_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(checkpoint_json)),
 settings_revision INTEGER NOT NULL CHECK(settings_revision > 0), policy_revision INTEGER NOT NULL CHECK(policy_revision > 0),
 context_epoch INTEGER NOT NULL CHECK(context_epoch >= 0), requested_count INTEGER CHECK(requested_count IN (5,10,20)),
 validated_count INTEGER NOT NULL DEFAULT 0 CHECK(validated_count >= 0), accepted_count INTEGER,
 published_version_id TEXT, live_published_version_id TEXT, error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(requested_count IS NULL OR validated_count <= requested_count),
 CHECK(accepted_count IS NULL OR (accepted_count > 0 AND accepted_count <= validated_count AND accepted_count <= requested_count))
);
CREATE INDEX assessment_tests_recent ON assessment_tests(lifecycle,updated_at,id);
CREATE UNIQUE INDEX assessment_legacy_mapping ON assessment_test_versions(
 json_extract(provenance_json,'$.legacy.kind'), json_extract(provenance_json,'$.legacy.session_id'))
 WHERE ordinal=1 AND json_extract(provenance_json,'$.legacy.kind') IS NOT NULL;
CREATE INDEX assessment_reports_version ON assessment_question_reports(version_id,created_at);
