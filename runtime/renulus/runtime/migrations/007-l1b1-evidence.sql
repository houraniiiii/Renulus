CREATE TABLE IF NOT EXISTS evidence_reservations (
    id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    day TEXT NOT NULL,
    requests INTEGER NOT NULL CHECK(requests >= 0),
    credits INTEGER NOT NULL CHECK(credits >= 0),
    started INTEGER NOT NULL DEFAULT 0 CHECK(started >= 0 AND started <= requests),
    state TEXT NOT NULL CHECK(state IN ('reserved','settled','uncertain'))
);
