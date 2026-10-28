-- SPDX-License-Identifier: MIT
CREATE TABLE mcp_connections (
 name TEXT PRIMARY KEY, endpoint TEXT NOT NULL, credential_ref TEXT NOT NULL,
 endpoint_revision INTEGER NOT NULL, credential_revision INTEGER NOT NULL,
 enabled INTEGER NOT NULL CHECK(enabled IN (0,1)), granted_epoch INTEGER NOT NULL DEFAULT 0,
 approved INTEGER NOT NULL DEFAULT 0 CHECK(approved IN (0,1)), settings_json TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE mcp_connection_commands (
 idempotency_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, result_json TEXT NOT NULL
);
