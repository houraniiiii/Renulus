-- Bounded machine-local original publication intent, never canonical export.
-- The index token in this table name uses the existing backup exclusion policy.
-- No changes to canonical records or the immutable 004/005 migrations.
CREATE TABLE knowledge_index_original_publications (
 revision_id TEXT PRIMARY KEY CHECK(length(revision_id) BETWEEN 1 AND 128),
 document_id TEXT NOT NULL CHECK(length(document_id) BETWEEN 1 AND 128),
 job_id TEXT NOT NULL CHECK(length(job_id) BETWEEN 1 AND 128),
 operation_id TEXT NOT NULL UNIQUE CHECK(length(operation_id)=64),
 request_sha256 TEXT NOT NULL CHECK(length(request_sha256)=64),
 root_path TEXT NOT NULL CHECK(length(root_path) BETWEEN 1 AND 4096),
 parent_path TEXT NOT NULL CHECK(length(parent_path) BETWEEN 1 AND 4096),
 original_path TEXT NOT NULL CHECK(length(original_path) BETWEEN 1 AND 4096),
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 expected_bytes INTEGER NOT NULL CHECK(expected_bytes BETWEEN 1 AND 67108864),
 identities_json TEXT NOT NULL CHECK(length(identities_json) BETWEEN 2 AND 32768),
 phase TEXT NOT NULL CHECK(phase IN ('prepared','creating','created','written','held',
     'held_missing','held_changed','held_uncertain','held_matching'))
);
CREATE TRIGGER knowledge_index_original_publications_cap BEFORE INSERT ON knowledge_index_original_publications
WHEN (SELECT COUNT(*) FROM knowledge_index_original_publications)>=64
BEGIN
 SELECT RAISE(ABORT,'Library original publication intent capacity is held');
END;
