CREATE TABLE IF NOT EXISTS capability_effects (
 id TEXT PRIMARY KEY, root_id TEXT NOT NULL, run_id TEXT NOT NULL, call_id TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL, envelope_json TEXT NOT NULL, action TEXT NOT NULL, grant_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('admitted','closed','settled','uncertain')),
 used_bytes INTEGER NOT NULL DEFAULT 0 CHECK(used_bytes>=0), effect_reference TEXT);
 CREATE INDEX IF NOT EXISTS capability_effects_root ON capability_effects(root_id,state);
 CREATE TABLE IF NOT EXISTS capability_closed_roots(root_id TEXT PRIMARY KEY);
