-- Design C saved-only conversation state; existing identities remain authoritative.
CREATE TABLE learn_conversations (
 thread_id TEXT PRIMARY KEY REFERENCES learn_threads(id) ON DELETE CASCADE,
 lifecycle TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle IN ('active','archived','deleted')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 draft_text TEXT NOT NULL DEFAULT '', draft_refs_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(draft_refs_json)),
 draft_revision INTEGER NOT NULL DEFAULT 0 CHECK(draft_revision >= 0), updated_at TEXT NOT NULL
);
INSERT INTO learn_conversations(thread_id,updated_at) SELECT id,updated_at FROM learn_threads;
CREATE TABLE conversation_commands (
 idempotency_key TEXT PRIMARY KEY, operation TEXT NOT NULL, target_type TEXT NOT NULL,
 target_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json TEXT NOT NULL CHECK(json_valid(result_json)), created_at TEXT NOT NULL
);
