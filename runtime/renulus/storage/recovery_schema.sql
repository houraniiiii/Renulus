-- Recovery receipts are local operational state, never part of learner exports.
CREATE TABLE storage_recovery_runs (
    id TEXT PRIMARY KEY,
    completed_at TEXT NOT NULL,
    result_json TEXT NOT NULL CHECK(json_valid(result_json)),
    rebuild_json TEXT NOT NULL CHECK(json_valid(rebuild_json))
);
