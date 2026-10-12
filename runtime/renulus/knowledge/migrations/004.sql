-- Machine-local derivative work. The index token excludes this table from
-- canonical export/restore eligibility; canonical job/cleanup shapes stay fixed.
CREATE TABLE knowledge_index_work (
 kind TEXT NOT NULL CHECK(kind IN ('removal','maintenance','retirement','publication')),
 target TEXT NOT NULL,
 generation TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
 retry_after REAL NOT NULL DEFAULT 0,
 error_code TEXT,
 dirty_sequence INTEGER NOT NULL DEFAULT 0 CHECK(dirty_sequence >= 0),
 completed_sequence INTEGER NOT NULL DEFAULT 0 CHECK(completed_sequence >= 0),
 passages INTEGER CHECK(passages IS NULL OR passages >= 0),
 PRIMARY KEY(kind,target,generation)
);
CREATE INDEX knowledge_index_work_due ON knowledge_index_work(kind,retry_after);
