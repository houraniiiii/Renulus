-- Explicit Save atomically retains accepted originals with the case snapshot.
-- Parts are ordinary bounded canonical scalars, so full recovery uses the
-- existing segmented exporter and deletion reconciliation without file staging.
CREATE TABLE case_attachments (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES case_sessions(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    title TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK (media_type IN ('application/pdf','image/png','image/jpeg')),
    bytes INTEGER NOT NULL CHECK (bytes > 0 AND bytes <= 10485760),
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64)
);
CREATE TABLE case_attachment_parts (
    attachment_id TEXT NOT NULL REFERENCES case_attachments(id) ON DELETE CASCADE,
    part INTEGER NOT NULL CHECK (part >= 0),
    data TEXT NOT NULL CHECK (length(data) > 0 AND length(data) <= 65536),
    PRIMARY KEY (attachment_id, part)
);
