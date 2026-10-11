-- Reference-only learner support. The applied memory-001 checksum is unchanged.
CREATE TABLE memory_answer_lineage (
    evidence_id TEXT PRIMARY KEY,
    publication_digest TEXT NOT NULL,
    manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json)),
    state TEXT NOT NULL CHECK(state IN ('active','revoked')),
    project_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE memory_support_groups (
    group_id TEXT PRIMARY KEY, -- Globally unique, derived from record/revision/source/roots.
    record_id TEXT NOT NULL REFERENCES memory_facts(id) ON DELETE CASCADE,
    source_key TEXT NOT NULL,
    support_kind TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','revoked')),
    project_id TEXT
);
CREATE INDEX memory_support_record ON memory_support_groups(record_id,state);
CREATE TABLE memory_support_inputs (
    group_id TEXT NOT NULL REFERENCES memory_support_groups(group_id) ON DELETE CASCADE,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    expected_revision TEXT NOT NULL,
    PRIMARY KEY(group_id,target_type,target_id,expected_revision)
);
-- Existing facts retain their established profile-global ownership/support.
INSERT INTO memory_support_groups
SELECT 'legacy:' || id,id,'legacy:' || id,'retained','active',NULL FROM memory_facts;
