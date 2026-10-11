-- SPDX-License-Identifier: MIT
-- Payload-bearing receipts are deleted; this frontier contains only opaque IDs.
CREATE TABLE learn_command_tombstones (
 ledger TEXT NOT NULL CHECK(ledger IN ('conversation_commands','study_project_commands')),
 idempotency_key TEXT NOT NULL, retired_at TEXT NOT NULL,
 PRIMARY KEY(ledger,idempotency_key)
);
