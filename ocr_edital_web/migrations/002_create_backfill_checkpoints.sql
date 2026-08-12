CREATE TABLE IF NOT EXISTS backfill_checkpoints (
  scope_key TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  date_from TEXT NOT NULL,
  date_to TEXT NOT NULL,
  modality_code INTEGER NOT NULL,
  next_page INTEGER NOT NULL DEFAULT 1,
  completed INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backfill_checkpoints_lookup
  ON backfill_checkpoints(source, endpoint, date_from, date_to, modality_code);

CREATE INDEX IF NOT EXISTS idx_source_records_backfill_dedupe
  ON source_records(source, source_endpoint, request_url, external_key, raw_payload_hash);

CREATE INDEX IF NOT EXISTS idx_source_records_backfill_payload
  ON source_records(source, source_endpoint, external_key, raw_payload_hash);
