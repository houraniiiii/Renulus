-- SPDX-License-Identifier: MIT
-- Frozen reference metadata only; legacy/native transcript bytes stay with their owners.
CREATE TABLE learn_harness_migrations (
 migration_id TEXT PRIMARY KEY,
 thread_id TEXT NOT NULL UNIQUE REFERENCES learn_threads(id) ON DELETE CASCADE,
 source_revision INTEGER NOT NULL CHECK(source_revision > 0),
 profile_id TEXT NOT NULL, store_id TEXT NOT NULL, session_id TEXT NOT NULL UNIQUE,
 source_digest TEXT NOT NULL CHECK(length(source_digest)=64 AND source_digest NOT GLOB '*[^0-9a-f]*'),
 state TEXT NOT NULL DEFAULT 'reserved' CHECK(state IN ('reserved','transferring','active')),
 manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json) AND json_type(manifest_json)='object'),
 pins_json TEXT NOT NULL CHECK(json_valid(pins_json) AND json_type(pins_json)='object'),
 message_refs_json TEXT NOT NULL CHECK(json_valid(message_refs_json) AND json_type(message_refs_json)='array'),
 readback_digest TEXT,
 CHECK((state='active' AND readback_digest IS NOT NULL AND readback_digest=source_digest)
       OR (state!='active' AND readback_digest IS NULL))
);
-- Coordinates survive owner cascades. No deleted payload, manifest or source digest.
CREATE TABLE learn_harness_purges (
 purge_id TEXT PRIMARY KEY,
 profile_id TEXT NOT NULL, store_id TEXT NOT NULL, session_id TEXT NOT NULL,
 operation_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','removed')),
 UNIQUE(profile_id,store_id,session_id,operation_id,attempt_id)
);
