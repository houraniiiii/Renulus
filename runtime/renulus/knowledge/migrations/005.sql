-- Additive machine-local maintenance accounting only. Canonical export shapes
-- and the immutable 004 work table/migration remain unchanged.
ALTER TABLE knowledge_index_work ADD COLUMN pending_batches INTEGER NOT NULL DEFAULT 0 CHECK(pending_batches >= 0);
ALTER TABLE knowledge_index_work ADD COLUMN pending_bytes INTEGER NOT NULL DEFAULT 0 CHECK(pending_bytes >= 0);
ALTER TABLE knowledge_index_work ADD COLUMN measured_logical_bytes INTEGER NOT NULL DEFAULT 0 CHECK(measured_logical_bytes >= 0);
ALTER TABLE knowledge_index_work ADD COLUMN measured_allocated_bytes INTEGER NOT NULL DEFAULT 0 CHECK(measured_allocated_bytes >= 0);
ALTER TABLE knowledge_index_work ADD COLUMN forecast_peak_bytes INTEGER NOT NULL DEFAULT 0 CHECK(forecast_peak_bytes >= 0);
