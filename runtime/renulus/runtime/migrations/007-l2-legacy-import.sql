-- SPDX-License-Identifier: MIT
CREATE TABLE legacy_history_imports (
 thread_id TEXT PRIMARY KEY,
 profile_id TEXT NOT NULL, store_id TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE,
 operation_id TEXT NOT NULL, source_digest TEXT NOT NULL, source_stamp TEXT NOT NULL,
 message_refs_json TEXT NOT NULL CHECK(json_valid(message_refs_json)),
 state TEXT NOT NULL CHECK(state IN ('reserved','active','deleted')),
 created_at TEXT NOT NULL
);
