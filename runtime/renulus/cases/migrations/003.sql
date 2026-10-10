-- Only explicitly saved legacy cases exist in case_sessions; volatile cases are absent.
CREATE TABLE case_conversations (
 case_id TEXT PRIMARY KEY REFERENCES case_sessions(id) ON DELETE CASCADE,
 lifecycle TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle IN ('active','archived','deleted')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 draft_text TEXT NOT NULL DEFAULT '', draft_refs_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(draft_refs_json)),
 draft_revision INTEGER NOT NULL DEFAULT 0 CHECK(draft_revision >= 0), updated_at TEXT NOT NULL
);
INSERT INTO case_conversations(case_id,revision,updated_at) SELECT id,revision,updated_at FROM case_sessions;
