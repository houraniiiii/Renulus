-- Membership is the sole project association; both endpoints remain independent.
CREATE TABLE study_projects (
 id TEXT PRIMARY KEY, title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
 lifecycle TEXT NOT NULL DEFAULT 'active' CHECK(lifecycle IN ('active','archived','deleted')),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE study_project_chats (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES study_projects(id) ON DELETE CASCADE,
 chat_kind TEXT NOT NULL CHECK(chat_kind IN ('learning','case')), chat_id TEXT NOT NULL,
 position INTEGER NOT NULL DEFAULT 0 CHECK(position >= 0), revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 created_at TEXT NOT NULL, UNIQUE(chat_kind,chat_id)
);
CREATE TABLE study_project_documents (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES study_projects(id) ON DELETE CASCADE,
 revision_id TEXT NOT NULL REFERENCES knowledge_revisions(id) ON DELETE CASCADE,
 position INTEGER NOT NULL DEFAULT 0 CHECK(position >= 0), revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0),
 created_at TEXT NOT NULL, UNIQUE(project_id,revision_id)
);
CREATE TABLE study_project_goals (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES study_projects(id) ON DELETE CASCADE,
 title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 240), topic_id TEXT, target_date TEXT,
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed')),
 progress_json TEXT NOT NULL DEFAULT '{}' CHECK(json_valid(progress_json)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision > 0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX study_project_chats_order ON study_project_chats(project_id,position,id);
CREATE INDEX study_project_documents_order ON study_project_documents(project_id,position,id);
CREATE TABLE study_project_commands (
 idempotency_key TEXT PRIMARY KEY, operation TEXT NOT NULL, target_type TEXT NOT NULL,
 target_id TEXT NOT NULL, request_hash TEXT NOT NULL, result_json TEXT NOT NULL CHECK(json_valid(result_json)), created_at TEXT NOT NULL
);
