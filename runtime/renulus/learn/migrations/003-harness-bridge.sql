-- SPDX-License-Identifier: MIT
-- Saved native transcripts stay in OpenCode. These are identities and receipts.
CREATE TABLE learn_harness_mappings (
 thread_id TEXT PRIMARY KEY REFERENCES learn_threads(id) ON DELETE CASCADE,
 profile_id TEXT NOT NULL, store_id TEXT NOT NULL, session_id TEXT UNIQUE,
 mapping_json TEXT CHECK(mapping_json IS NULL OR json_valid(mapping_json)),
 create_request_id TEXT, process_generation TEXT
);
CREATE TABLE learn_harness_answers (
 run_id TEXT PRIMARY KEY REFERENCES learn_runs(id) ON DELETE CASCADE,
 thread_id TEXT NOT NULL REFERENCES learn_threads(id) ON DELETE CASCADE,
 request_digest TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN ('reserved','submitted','completed','uncertain','cancelled','failed')),
 input_id TEXT UNIQUE, reference_json TEXT CHECK(reference_json IS NULL OR json_valid(reference_json)),
 publication_digest TEXT, command_request_id TEXT, process_generation TEXT
);
CREATE INDEX learn_harness_answers_thread ON learn_harness_answers(thread_id);
