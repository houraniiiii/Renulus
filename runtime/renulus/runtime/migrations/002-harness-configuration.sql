-- H04 immutable configuration inputs; mutable readiness is a separate record.
CREATE TABLE harness_configuration_versions(
    version TEXT PRIMARY KEY,
    predecessor TEXT REFERENCES harness_configuration_versions(version),
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TRIGGER harness_configuration_immutable_update
BEFORE UPDATE ON harness_configuration_versions BEGIN
    SELECT RAISE(ABORT, 'immutable configuration');
END;
CREATE TRIGGER harness_configuration_immutable_delete
BEFORE DELETE ON harness_configuration_versions BEGIN
    SELECT RAISE(ABORT, 'immutable configuration');
END;
CREATE TABLE harness_configuration_health(
    version TEXT PRIMARY KEY REFERENCES harness_configuration_versions(version),
    state TEXT NOT NULL CHECK(state IN ('staged','ready','failed')),
    registry_hash TEXT,
    grant_epoch INTEGER,
    failure_code TEXT
);
CREATE TABLE harness_configuration_pointer(
    id INTEGER PRIMARY KEY CHECK(id=1),
    requested TEXT REFERENCES harness_configuration_versions(version),
    effective TEXT REFERENCES harness_configuration_versions(version),
    previous TEXT REFERENCES harness_configuration_versions(version),
    activating TEXT REFERENCES harness_configuration_versions(version),
    failed TEXT REFERENCES harness_configuration_versions(version),
    failure_code TEXT,
    admission_open INTEGER NOT NULL DEFAULT 0 CHECK(admission_open IN (0,1))
);
INSERT INTO harness_configuration_pointer(id) VALUES(1);
CREATE TABLE harness_configuration_grants(
    id INTEGER PRIMARY KEY CHECK(id=1), epoch INTEGER NOT NULL DEFAULT 0
);
INSERT INTO harness_configuration_grants(id) VALUES(1);
CREATE TABLE harness_configuration_revocations(
    capability TEXT PRIMARY KEY, epoch INTEGER NOT NULL, revoked_at TEXT NOT NULL
);
CREATE TABLE harness_configuration_runs(
    run_id TEXT PRIMARY KEY,
    version TEXT NOT NULL REFERENCES harness_configuration_versions(version),
    root_id TEXT NOT NULL REFERENCES harness_configuration_runs(run_id),
    parent_id TEXT REFERENCES harness_configuration_runs(run_id),
    purpose TEXT NOT NULL,
    depth INTEGER NOT NULL,
    dispatch_limit INTEGER NOT NULL,
    capabilities_json TEXT NOT NULL,
    route_json TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('active','settled')),
    created_at TEXT NOT NULL
);
CREATE TABLE harness_configuration_attempts(
    permit_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES harness_configuration_runs(run_id),
    root_id TEXT NOT NULL REFERENCES harness_configuration_runs(run_id),
    step_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    required_capabilities_json TEXT NOT NULL,
    retry_number INTEGER NOT NULL DEFAULT 0,
    grant_epoch INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','dispatched','confirmed','failed','uncertain','cancelled_before_send')),
    result_reference TEXT,
    failure_code TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(run_id,step_id,retry_number)
);
CREATE INDEX harness_configuration_attempts_root ON harness_configuration_attempts(root_id);
