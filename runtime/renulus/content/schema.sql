-- M8 proposal: integrator assigns migration order and executes this DDL.
-- No user cases, conversations, learner answers or credentials belong here.
CREATE TABLE IF NOT EXISTS content_packs (
    pack_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    installed_at TEXT NOT NULL,
    PRIMARY KEY (pack_id, version)
);
CREATE TABLE IF NOT EXISTS content_topics (
    topic_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    body_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (topic_id, version)
);
CREATE TABLE IF NOT EXISTS content_case_versions (
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    body_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (case_id, version)
);
CREATE TABLE IF NOT EXISTS content_question_versions (
    question_id TEXT NOT NULL,
    version INTEGER NOT NULL CHECK (version > 0),
    family_id TEXT NOT NULL,
    body_json TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY (question_id, version)
);
CREATE TABLE IF NOT EXISTS content_pack_topics (
    pack_id TEXT NOT NULL, pack_version TEXT NOT NULL,
    topic_id TEXT NOT NULL, topic_version INTEGER NOT NULL,
    PRIMARY KEY (pack_id, pack_version, topic_id),
    FOREIGN KEY (pack_id, pack_version) REFERENCES content_packs(pack_id, version),
    FOREIGN KEY (topic_id, topic_version) REFERENCES content_topics(topic_id, version)
);
CREATE TABLE IF NOT EXISTS content_pack_cases (
    pack_id TEXT NOT NULL, pack_version TEXT NOT NULL,
    case_id TEXT NOT NULL, case_version INTEGER NOT NULL,
    PRIMARY KEY (pack_id, pack_version, case_id),
    FOREIGN KEY (pack_id, pack_version) REFERENCES content_packs(pack_id, version),
    FOREIGN KEY (case_id, case_version) REFERENCES content_case_versions(case_id, version)
);
CREATE TABLE IF NOT EXISTS content_pack_questions (
    pack_id TEXT NOT NULL, pack_version TEXT NOT NULL,
    question_id TEXT NOT NULL, question_version INTEGER NOT NULL,
    PRIMARY KEY (pack_id, pack_version, question_id),
    FOREIGN KEY (pack_id, pack_version) REFERENCES content_packs(pack_id, version),
    FOREIGN KEY (question_id, question_version) REFERENCES content_question_versions(question_id, version)
);
CREATE TABLE IF NOT EXISTS content_active_pack (
    slot INTEGER PRIMARY KEY CHECK (slot = 1),
    pack_id TEXT NOT NULL, pack_version TEXT NOT NULL,
    FOREIGN KEY (pack_id, pack_version) REFERENCES content_packs(pack_id, version)
);
CREATE TABLE IF NOT EXISTS content_question_withdrawals (
    question_id TEXT NOT NULL, version INTEGER NOT NULL,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    withdrawn_at TEXT NOT NULL, replacement_version INTEGER,
    PRIMARY KEY (question_id, version),
    FOREIGN KEY (question_id, version) REFERENCES content_question_versions(question_id, version),
    FOREIGN KEY (question_id, replacement_version) REFERENCES content_question_versions(question_id, version)
);
CREATE TABLE IF NOT EXISTS content_pack_withdrawals (
    pack_id TEXT NOT NULL, version TEXT NOT NULL,
    reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
    withdrawn_at TEXT NOT NULL,
    PRIMARY KEY (pack_id, version),
    FOREIGN KEY (pack_id, version) REFERENCES content_packs(pack_id, version)
);
-- Canonical published records are append only, even for callers using SQL.
CREATE TRIGGER IF NOT EXISTS content_question_no_update BEFORE UPDATE ON content_question_versions
BEGIN SELECT RAISE(ABORT, 'published question versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS content_question_no_delete BEFORE DELETE ON content_question_versions
BEGIN SELECT RAISE(ABORT, 'retain historical question versions'); END;
CREATE TRIGGER IF NOT EXISTS content_case_no_update BEFORE UPDATE ON content_case_versions
BEGIN SELECT RAISE(ABORT, 'published case versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS content_case_no_delete BEFORE DELETE ON content_case_versions
BEGIN SELECT RAISE(ABORT, 'retain historical case versions'); END;
CREATE TRIGGER IF NOT EXISTS content_topic_no_update BEFORE UPDATE ON content_topics
BEGIN SELECT RAISE(ABORT, 'published topic versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS content_topic_no_delete BEFORE DELETE ON content_topics
BEGIN SELECT RAISE(ABORT, 'retain historical topic versions'); END;
CREATE TRIGGER IF NOT EXISTS content_pack_no_update BEFORE UPDATE ON content_packs
BEGIN SELECT RAISE(ABORT, 'published pack versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS content_pack_no_delete BEFORE DELETE ON content_packs
BEGIN SELECT RAISE(ABORT, 'retain historical pack versions'); END;
CREATE TRIGGER IF NOT EXISTS content_withdrawal_no_update BEFORE UPDATE ON content_question_withdrawals
BEGIN SELECT RAISE(ABORT, 'withdrawals are permanent'); END;
CREATE TRIGGER IF NOT EXISTS content_withdrawal_no_delete BEFORE DELETE ON content_question_withdrawals
BEGIN SELECT RAISE(ABORT, 'withdrawals are permanent'); END;
CREATE TRIGGER IF NOT EXISTS content_pack_withdrawal_no_update BEFORE UPDATE ON content_pack_withdrawals
BEGIN SELECT RAISE(ABORT, 'pack withdrawals are permanent'); END;
CREATE TRIGGER IF NOT EXISTS content_pack_withdrawal_no_delete BEFORE DELETE ON content_pack_withdrawals
BEGIN SELECT RAISE(ABORT, 'pack withdrawals are permanent'); END;
