-- SPDX-License-Identifier: MIT
-- Reference-only H07 journal. Reopening rows does not restore authorization.
CREATE TABLE harness_child_families(
    root_id TEXT PRIMARY KEY NOT NULL,
    profile_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    process_generation TEXT NOT NULL,
    configuration_version TEXT NOT NULL,
    grant_epoch INTEGER NOT NULL CHECK(grant_epoch >= 0),
    family_epoch INTEGER NOT NULL CHECK(family_epoch >= 0),
    state TEXT NOT NULL CHECK(state IN ('open','sealed','settled')),
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    CHECK(json_extract(metadata_json,'$.root_id') IS root_id
        AND json_extract(metadata_json,'$.root_binding.operation_id') IS root_id
        AND json_extract(metadata_json,'$.profile_id') IS profile_id
        AND json_extract(metadata_json,'$.store_id') IS store_id
        AND json_extract(metadata_json,'$.process_generation') IS process_generation
        AND json_extract(metadata_json,'$.configuration_version') IS configuration_version
        AND json_extract(metadata_json,'$.grant_epoch') IS grant_epoch
        AND json_extract(metadata_json,'$.family_epoch') IS family_epoch
        AND json_extract(metadata_json,'$.state') IS state)
);
CREATE TABLE harness_child_records(
    reservation_id TEXT PRIMARY KEY NOT NULL,
    root_id TEXT NOT NULL REFERENCES harness_child_families(root_id),
    invocation_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('reserved','admitted','reported','consumed','sealed','settled')),
    operation_id TEXT UNIQUE CHECK(operation_id IS NULL OR operation_id = reservation_id),
    session_id TEXT UNIQUE,
    input_id TEXT UNIQUE,
    job_id TEXT UNIQUE,
    notification_id TEXT UNIQUE,
    report_id TEXT UNIQUE,
    metadata_json TEXT NOT NULL CHECK(json_valid(metadata_json)),
    UNIQUE(root_id,invocation_key),
    CHECK(json_extract(metadata_json,'$.reservation_id') IS reservation_id
        AND json_extract(metadata_json,'$.root_id') IS root_id
        AND json_extract(metadata_json,'$.invocation_key') IS invocation_key
        AND json_extract(metadata_json,'$.state') IS state
        AND json_extract(metadata_json,'$.binding.operation_id') IS operation_id
        AND json_extract(metadata_json,'$.binding.session_id') IS session_id
        AND json_extract(metadata_json,'$.binding.input_id') IS input_id
        AND json_extract(metadata_json,'$.job_id') IS job_id
        AND json_extract(metadata_json,'$.notification_id') IS notification_id
        AND json_extract(metadata_json,'$.report_id') IS report_id)
);
