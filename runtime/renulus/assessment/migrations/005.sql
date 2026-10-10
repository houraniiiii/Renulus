-- Explicit private originals and user-reviewed candidates; independent historical pins.
CREATE TABLE assessment_test_imports (
 id TEXT PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
 state TEXT NOT NULL CHECK(state IN ('draft','running','failed','cancelled','published')),
 revision INTEGER NOT NULL CHECK(revision > 0),
 source_kind TEXT NOT NULL CHECK(source_kind IN ('paste','library_revision')),
 source_revision_id TEXT, live_source_revision_id TEXT,
 original_text TEXT NOT NULL CHECK(length(original_text) BETWEEN 1 AND 96000),
 original_sha256 TEXT NOT NULL CHECK(length(original_sha256)=64 AND original_sha256 NOT GLOB '*[^a-f0-9]*'),
 original_json TEXT NOT NULL CHECK(json_valid(original_json) AND json_type(original_json)='object'),
 candidates_json TEXT NOT NULL CHECK(json_valid(candidates_json) AND json_type(candidates_json)='array' AND json_array_length(candidates_json)<=50),
 checkpoint_json TEXT NOT NULL CHECK(json_valid(checkpoint_json) AND json_type(checkpoint_json)='object'),
 policy_revision INTEGER NOT NULL CHECK(policy_revision > 0), context_epoch INTEGER NOT NULL CHECK(context_epoch >= 0),
 call_count INTEGER NOT NULL DEFAULT 0 CHECK(call_count BETWEEN 0 AND 3),
 idempotency_key TEXT NOT NULL UNIQUE,
 request_hash TEXT NOT NULL CHECK(length(request_hash)=64 AND request_hash NOT GLOB '*[^a-f0-9]*'),
 published_version_id TEXT, live_published_version_id TEXT, error_code TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK((source_kind='paste' AND source_revision_id IS NULL AND live_source_revision_id IS NULL) OR
       (source_kind='library_revision' AND source_revision_id IS NOT NULL)),
 CHECK(live_source_revision_id IS NULL OR live_source_revision_id=source_revision_id),
 CHECK(live_published_version_id IS NULL OR live_published_version_id=published_version_id),
 CHECK(state!='published' OR published_version_id IS NOT NULL)
);
CREATE INDEX assessment_imports_recent ON assessment_test_imports(updated_at,id);
