-- Proposed module DDL; the server/integrator owns the checked migration ledger.
CREATE TABLE knowledge_documents (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, source_id TEXT NOT NULL,
    scope_kind TEXT NOT NULL, scope_entity TEXT, reserved INTEGER NOT NULL DEFAULT 0,
    active_revision TEXT, latest_revision TEXT, deleted_at TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE knowledge_revisions (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES knowledge_documents(id),
    ordinal INTEGER NOT NULL, status TEXT NOT NULL, sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL, bytes INTEGER NOT NULL, original_path TEXT,
    metadata_json TEXT NOT NULL, rights_json TEXT NOT NULL,
    extraction_json TEXT, embedding_model TEXT, chunk_tokens INTEGER,
    created_at TEXT NOT NULL, activated_at TEXT,
    UNIQUE(document_id, ordinal)
);
CREATE TABLE knowledge_jobs (
    id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES knowledge_revisions(id),
    idempotency_key TEXT UNIQUE NOT NULL, request_hash TEXT NOT NULL,
    state TEXT NOT NULL, phase TEXT NOT NULL, error_code TEXT, error_message TEXT,
    created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE knowledge_passages (
    id TEXT PRIMARY KEY, revision_id TEXT NOT NULL REFERENCES knowledge_revisions(id),
    ordinal INTEGER NOT NULL, text TEXT NOT NULL, context_text TEXT NOT NULL,
    locators_json TEXT NOT NULL, headings_json TEXT NOT NULL,
    UNIQUE(revision_id, ordinal)
);
CREATE TABLE knowledge_cleanup (
    revision_id TEXT PRIMARY KEY REFERENCES knowledge_revisions(id),
    remove_original INTEGER NOT NULL DEFAULT 0, error_code TEXT, created_at TEXT NOT NULL
);
CREATE INDEX knowledge_revision_document ON knowledge_revisions(document_id);
CREATE INDEX knowledge_passage_revision ON knowledge_passages(revision_id);
CREATE INDEX knowledge_job_state ON knowledge_jobs(state);
CREATE TABLE knowledge_catalogue (
    id TEXT PRIMARY KEY, collection_path TEXT NOT NULL, source_id TEXT NOT NULL,
    title TEXT NOT NULL, expected_sha256 TEXT, bytes INTEGER, reserved INTEGER NOT NULL,
    eligibility TEXT NOT NULL, metadata_json TEXT NOT NULL, rights_json TEXT NOT NULL,
    document_id TEXT, job_id TEXT, checked_at TEXT NOT NULL
);
