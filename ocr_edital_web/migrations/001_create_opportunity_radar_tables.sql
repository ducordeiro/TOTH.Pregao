PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS etl_runs (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  run_type TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  filters_json TEXT NOT NULL DEFAULT '{}',
  total_fetched INTEGER NOT NULL DEFAULT 0,
  total_inserted INTEGER NOT NULL DEFAULT 0,
  total_updated INTEGER NOT NULL DEFAULT 0,
  total_skipped INTEGER NOT NULL DEFAULT 0,
  total_failed INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (json_valid(filters_json))
);

CREATE TABLE IF NOT EXISTS source_records (
  id TEXT PRIMARY KEY,
  etl_run_id TEXT REFERENCES etl_runs(id) ON DELETE SET NULL,
  opportunity_id TEXT REFERENCES opportunities(id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  source_endpoint TEXT NOT NULL,
  request_url TEXT NOT NULL,
  external_key TEXT,
  raw_payload_json TEXT NOT NULL,
  raw_payload_hash TEXT NOT NULL,
  normalized_payload_json TEXT,
  normalized_payload_hash TEXT,
  status TEXT NOT NULL,
  error_message TEXT,
  captured_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  CHECK (json_valid(raw_payload_json)),
  CHECK (normalized_payload_json IS NULL OR json_valid(normalized_payload_json))
);

CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  external_key TEXT NOT NULL UNIQUE,
  source TEXT NOT NULL,
  pncp_control_number TEXT,
  source_cnpj TEXT,
  year INTEGER,
  sequence INTEGER,
  process_number TEXT,
  title TEXT NOT NULL,
  description TEXT,
  buyer_name TEXT,
  buyer_cnpj TEXT,
  uf TEXT,
  city TEXT,
  uasg TEXT,
  modality TEXT,
  modality_code INTEGER,
  status TEXT,
  estimated_value REAL,
  currency TEXT NOT NULL DEFAULT 'BRL',
  published_at TEXT,
  proposal_start_at TEXT,
  proposal_end_at TEXT,
  source_url TEXT,
  detail_url TEXT,
  origin_url TEXT,
  record_hash TEXT NOT NULL,
  radar_status TEXT NOT NULL DEFAULT 'new'
    CHECK (radar_status IN ('new', 'triage', 'ignored', 'selected', 'converted_to_proposal')),
  converted_business_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_items (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  source_item_id TEXT,
  lot_number TEXT NOT NULL DEFAULT '',
  item_number TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  technical_object TEXT,
  quantity REAL,
  unit TEXT,
  estimated_unit_value REAL,
  estimated_total_value REAL,
  currency TEXT NOT NULL DEFAULT 'BRL',
  status TEXT,
  granularity TEXT NOT NULL DEFAULT 'item',
  confidence REAL NOT NULL DEFAULT 1.0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(opportunity_id, lot_number, item_number)
);

CREATE TABLE IF NOT EXISTS opportunity_documents (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  document_type TEXT NOT NULL,
  title TEXT,
  url TEXT NOT NULL,
  filename TEXT,
  mime_type TEXT,
  source TEXT NOT NULL,
  download_status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(opportunity_id, url)
);

CREATE TABLE IF NOT EXISTS opportunity_matches (
  id TEXT PRIMARY KEY,
  opportunity_id TEXT NOT NULL REFERENCES opportunities(id) ON DELETE CASCADE,
  company_profile_id TEXT NOT NULL DEFAULT 'default',
  score REAL NOT NULL DEFAULT 0,
  matched_keywords_json TEXT NOT NULL DEFAULT '[]',
  matched_items_json TEXT NOT NULL DEFAULT '[]',
  matched_regions_json TEXT NOT NULL DEFAULT '[]',
  matched_modalities_json TEXT NOT NULL DEFAULT '[]',
  reasons_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(opportunity_id, company_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_etl_runs_started_at
  ON etl_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_records_run
  ON source_records(etl_run_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_source_records_opportunity
  ON source_records(opportunity_id, captured_at);
CREATE INDEX IF NOT EXISTS idx_source_records_external_key
  ON source_records(source, external_key);
CREATE INDEX IF NOT EXISTS idx_opportunities_radar_status
  ON opportunities(radar_status);
CREATE INDEX IF NOT EXISTS idx_opportunities_dates
  ON opportunities(published_at, proposal_end_at);
CREATE INDEX IF NOT EXISTS idx_opportunities_region
  ON opportunities(uf, city);
CREATE INDEX IF NOT EXISTS idx_opportunities_pncp_identity
  ON opportunities(source_cnpj, year, sequence);
CREATE INDEX IF NOT EXISTS idx_opportunity_items_opportunity
  ON opportunity_items(opportunity_id, lot_number, item_number);
CREATE INDEX IF NOT EXISTS idx_opportunity_documents_opportunity
  ON opportunity_documents(opportunity_id, created_at, title);
CREATE INDEX IF NOT EXISTS idx_opportunities_modality
  ON opportunities(modality_code, modality);
CREATE INDEX IF NOT EXISTS idx_opportunities_buyer
  ON opportunities(buyer_cnpj, buyer_name);
CREATE INDEX IF NOT EXISTS idx_opportunities_converted_business
  ON opportunities(converted_business_id);
CREATE INDEX IF NOT EXISTS idx_matches_score
  ON opportunity_matches(score DESC);
