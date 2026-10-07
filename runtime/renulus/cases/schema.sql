-- M3 proposed DDL. The integration owner applies it through the checked ledger.
-- Unsaved sessions, runs, handoffs and tool messages have no durable table.
CREATE TABLE IF NOT EXISTS case_sessions (
    id TEXT PRIMARY KEY,
    revision INTEGER NOT NULL CHECK (revision > 0),
    kind TEXT NOT NULL CHECK (kind IN ('daily', 'teaching')),
    title TEXT NOT NULL,
    case_text TEXT NOT NULL,
    messages_json TEXT NOT NULL CHECK (json_valid(messages_json)),
    teaching_json TEXT CHECK (teaching_json IS NULL OR json_valid(teaching_json)),
    revealed_count INTEGER NOT NULL CHECK (revealed_count >= 0),
    debriefed INTEGER NOT NULL CHECK (debriefed IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    saved_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS case_refuse_deleted_insert BEFORE INSERT ON case_sessions
WHEN EXISTS (SELECT 1 FROM deletion_ledger WHERE entity_type = 'case' AND entity_id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'deleted cases cannot be restored'); END;
CREATE TRIGGER IF NOT EXISTS case_refuse_deleted_update BEFORE UPDATE ON case_sessions
WHEN EXISTS (SELECT 1 FROM deletion_ledger WHERE entity_type = 'case' AND entity_id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'deleted cases cannot be updated'); END;
