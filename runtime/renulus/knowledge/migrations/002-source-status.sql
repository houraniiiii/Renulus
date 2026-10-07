-- Journal exact-publication status evidence; preserve ordering for later imports.
CREATE TABLE knowledge_source_status_events (
    id TEXT PRIMARY KEY, source_id TEXT NOT NULL, request_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX knowledge_source_status_source ON knowledge_source_status_events(source_id);
