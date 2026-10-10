-- Saved chat attachments own their bytes; Library/project documents remain links.
CREATE TABLE knowledge_attachments (
 id TEXT PRIMARY KEY, chat_kind TEXT NOT NULL CHECK(chat_kind IN ('learning','case')),
 chat_id TEXT NOT NULL, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 500),
 media_type TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 extraction_state TEXT NOT NULL DEFAULT 'not_requested', index_state TEXT NOT NULL DEFAULT 'not_requested',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX knowledge_attachment_chat ON knowledge_attachments(chat_kind,chat_id);
CREATE TABLE knowledge_attachment_originals (
 id TEXT PRIMARY KEY, attachment_id TEXT NOT NULL REFERENCES knowledge_attachments(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('original','preview')), original_path TEXT,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64), bytes INTEGER NOT NULL CHECK(bytes >= 0), created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX knowledge_attachment_one_original ON knowledge_attachment_originals(attachment_id) WHERE role='original';
CREATE TABLE knowledge_attachment_metadata (
 attachment_id TEXT PRIMARY KEY REFERENCES knowledge_attachments(id) ON DELETE CASCADE,
 filename TEXT NOT NULL CHECK(length(filename) BETWEEN 1 AND 500), source_id TEXT NOT NULL,
 metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json) AND json_type(metadata_json)='object'),
 rights_json TEXT NOT NULL CHECK(json_valid(rights_json) AND json_type(rights_json)='object'),
 preview_state TEXT NOT NULL DEFAULT 'not_requested' CHECK(preview_state IN ('not_requested','ready','failed','unsupported')),
 preview_revision INTEGER NOT NULL DEFAULT 0 CHECK(preview_revision >= 0),
 preview_json TEXT DEFAULT NULL CHECK(preview_json IS NULL OR (json_valid(preview_json) AND json_type(preview_json)='object')),
 extraction_revision INTEGER NOT NULL DEFAULT 0 CHECK(extraction_revision >= 0),
 extraction_json TEXT DEFAULT NULL CHECK(extraction_json IS NULL OR (json_valid(extraction_json) AND json_type(extraction_json)='object')),
 processing_json TEXT DEFAULT NULL CHECK(processing_json IS NULL OR (json_valid(processing_json) AND json_type(processing_json)='object'))
);
CREATE TRIGGER knowledge_attachment_refuse_deleted BEFORE INSERT ON knowledge_attachments
WHEN EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='attachment' AND entity_id=NEW.id)
BEGIN SELECT RAISE(ABORT,'deleted attachment cannot be restored'); END;
CREATE TRIGGER knowledge_attachment_original_refuse_deleted BEFORE INSERT ON knowledge_attachment_originals
WHEN EXISTS(SELECT 1 FROM deletion_ledger WHERE entity_type='attachment_original' AND entity_id=NEW.id)
BEGIN SELECT RAISE(ABORT,'deleted attachment original cannot be restored'); END;
