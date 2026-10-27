CREATE TABLE IF NOT EXISTS temporary_save_intents(
 id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('staged','copied','active','cancelled','retired')),
 cancellation_epoch INTEGER NOT NULL, plan_json TEXT NOT NULL CHECK(json_valid(plan_json)), graph_digest TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
